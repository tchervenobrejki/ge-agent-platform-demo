# Design decisions

Why the system is built the way it is. Code comments point here by fix number, for example *F27*. For the
reusable lessons in short form, see [lessons-learned.md](lessons-learned.md).

Versions at the time of writing (October 2026): agents-cli 1.10, ADK 2.11, a2a-sdk 1.2, MCP SDK 2.3,
`gemini-3.5-flash`. Re-check anything version-specific against current release notes.

## Architecture

**Two independently deployed agents.** The orchestrator (Agent Runtime) investigates and proposes; the Compliance
Agent (Cloud Run) judges. They are separate services with separate identities, Terraform states and deploys, so
the agent proposing an action can't change the rules it is judged by. They talk over A2A, the protocol for
independently built and deployed agents.

**One write, behind two independent gates.** The only action that changes anything is the MCP tool
`create_remediation_action_mcp`. It runs only if the Compliance Agent returned `compliant=true` *and* a human
approved it (`require_confirmation=True`). Neither gate is enough on its own. Unknown action types fail closed.

**Deterministic orchestration, LLMs inside the steps.** The root is a `SequentialAgent`: triage → parallel
investigation → synthesis → action pipeline. The order is code, not a model decision. Each LLM step has a narrow
job and writes a named key into session state.

**Exactly one recommended action.** The synthesizer ends with one "Primary recommended action" line, and the
Compliance Agent checks only that one (F24). The approver summary relies on internal evidence only; web-search
findings go in their own section (F25).

**Guardrails in layers.** A code check before the model (`before_model_callback`, regex patterns), triage
instructions for phrasings the patterns miss, the deterministic compliance check, human approval, and optionally
Model Armor outside the model.

**Explicit RAG function tools** instead of ADK's built-in `VertexAiRagRetrieval` (F20), so every retrieval is
visible in the trace and the agents can be told to quote only what came back.

## Platform and deployment

**Agent Identity for the orchestrator.** The engine runs as its own principal, and the agents-cli 1.10 Terraform
grants it the roles it needs, including the ones telemetry requires. Always pass `--agent-identity` to
`agents-cli deploy`: without it a *newly created* engine gets no Agent Identity.

**Terraform owns the engine, `agents-cli deploy` owns the code.** `infra single-project --apply` creates the
engine, IAM and telemetry first; `deploy --update-only` then replaces only the code. The engine's
`lifecycle.ignore_changes` lists `container_spec`, `source_code_spec`, `deployment_spec` and `class_methods`
(F19). Without `class_methods` there, a re-apply deleted the method contract the console playground and
`:streamQuery` use.

**Env vars come from `.env` at deploy time.** `agents-cli deploy` uses the project's `.env` as the base layer of
the engine's environment, keeps values set outside the deploy, and lets `--env-vars` override. Terraform's `env`
blocks only apply when the engine is created.

**Scale to zero.** Both agents: `min_instances=0`, `max_instances=3`, `container_concurrency=4`. The orchestrator
has 2 CPU / 4 GiB (its four-way parallel fan-out fits at concurrency 4), the Compliance Agent 1 CPU / 2 GiB. The
first request after idle is a cold start.

**Gemini in-region.** `GOOGLE_CLOUD_LOCATION=europe-west3` rather than `global`: the same structured-output triage
call took 56 s on `global` and 6.6 s in-region (F23).

**Values in `terraform.tfvars`, not in defaults.** `agents-cli infra single-project` only passes `project_id`, so
the project-specific inputs (corpora, URLs, the caller account) live in a gitignored `terraform.tfvars` per stack,
written by `setup/05_write_config.py` from the `vars/env.tfvars` template.

**Remote Terraform state** in a versioned GCS bucket, one prefix per stack; `terraform plan` after every apply
must say *No changes*.

**A static `COMPLIANCE_AGENT_URL`.** Cloud Run URLs are deterministic (`https://SERVICE-PROJECT_NUMBER.REGION.run.app`),
so the orchestrator reads the URL from an env var. The Compliance Agent is registered in Agent Registry as A2A, so
a registry lookup would work too, but it adds a runtime dependency for no benefit here.

**`action_tools.py` duplicated** in both projects (F8). They are separately scaffolded and share no package; a
unit test asserts the two copies are identical.

**BigQuery Agent Analytics only when deployed** (F18): enabled when `BQ_ANALYTICS_DATASET_ID` is set, which
Terraform does. Locally it created a stray US dataset and its retries pushed calls past timeouts.

## How it was built

1. **A first demo**, deployed with the raw `adk` and `gcloud` CLIs and scripts. It worked, but IAM, env vars and
   telemetry were wired by hand and drifted, and its dashboards stayed empty: OpenTelemetry exporters got 401s under
   Agent Identity.
2. **A port to agents-cli 1.0**, keeping the agent code. By the time it was ready to deploy, agents-cli 1.10 had
   changed telemetry, identity and A2A in most generated files.
3. **A fresh 1.10 scaffold** (not `scaffold upgrade`), and first a **canary**: the *unmodified* scaffold was
   deployed and checked for traces, sessions and logs before any agent code was ported. It passed.
4. **Port and fix** the agent code into the new scaffold (F1–F18), then **evaluate locally** until the rubrics
   passed (F20–F26), then **deploy and verify live** (F27–F29), then **register** the Compliance Agent as A2A (F30).

## Fix log

| # | Problem | Fix |
|---|---|---|
| F1 | Memory Bank wasn't wired: the scaffold passes session and artifact services to every runner, but not memory, so `preload_memory` silently did nothing on the A2A and API paths. | `get_memory_service()` in `app_utils/services.py`, passed to the FastAPI app, the A2A runner and `AdkApp`. |
| F2 | The first demo patched OpenTelemetry exporters by hand (an SSL workaround). | Keep the 1.10 scaffold's `otel_to_cloud` telemetry exactly as generated; no custom exporters. |
| F3 | A2A SDK 1.0 changed types. | Updated `a2a_auth.py` / `a2a_callbacks.py`; kept `CompactRemoteA2aAgent`'s summary-only payload and fresh HTTP client per invocation. |
| F4 | ADK's MCP toolset auto-configures mTLS and then sends an access token instead of the audience-scoped ID token Cloud Run requires: 401s. | `gcp_auth.py` mints ID tokens by impersonating the caller service account and disables the MCP mTLS auto-config. |
| F5 | Config was scattered across scripts. | All service URLs, corpora and the caller account are env vars in `service.tf` / `.env`. |
| F6 | The first demo hit an upstream pyOpenSSL/urllib3 SSL-context bug when saving artifacts to GCS. | A retry-once guard in `artifact_tools.py`; it did not reproduce with the 1.10 dependencies. |
| F7 | `stream_query` is deprecated. | Every client uses `async_stream_query`. |
| F8 | Two projects, one compliance schema. | `action_tools.py` duplicated; `test_action_tools_sync.py` fails on drift. |
| F9 | Telemetry agent names didn't match. | The manifest's `root_agent_name` equals the root agent's `name`. |
| F10 | `ComplianceDecision.action_type` was a `Literal` of two actions, so a violation couldn't be expressed. | A `str`; `check_action_compliance` still fails closed on unknown actions. |
| F11 | Locally, `app/__init__.py` imported the agent before `load_dotenv()` ran, so module-level config was empty. | `load_dotenv()` runs first in `app/__init__.py`. |
| F12 | MCP SDK 2.x uses `httpx2` and silently rejected an `httpx.Auth`, so the MCP tools never loaded (`MALFORMED_FUNCTION_CALL`). | `gcp_auth.py` builds an `httpx2.Auth` for MCP and keeps the `httpx` one for A2A. |
| F13 | Sometimes the A2A answer arrived as a Task with status updates and the final JSON never reached the session. | `extract_compliance_result` falls back to the relayed tool call and response, and otherwise fails closed. |
| F14 | Vague requests ran the whole pipeline. In ADK 2.11 a sub-agent's `end_invocation` doesn't stop the parent `SequentialAgent`. | A clarification gate (`before_agent_callback`) on every downstream step. |
| F15 | The injection refusal was plain text and failed `TriageContext` validation, crashing the run. | The refusal is valid `TriageContext` JSON and goes through the same gate. |
| F16 | A direct action request ("approve a 35% discount") ran a full investigation. | `TriageContext.requested_action`: investigation and synthesis are skipped, and exactly that action is checked. |
| F17 | The BigQuery tool returned invented fallback rows when a query failed. | Errors are returned as errors; the agents report them. |
| F18 | Locally, the Analytics plugin created a US dataset and slowed calls past timeouts. | Enabled only when `BQ_ANALYTICS_DATASET_ID` is set (deployed). |
| F19 | A Terraform re-apply wanted to delete the engine's `class_methods`, written by `agents-cli deploy`. | `spec[0].class_methods` in `lifecycle.ignore_changes`. |
| F20 | The RAG agents cited tickets, runbooks and policy sections that don't exist; the built-in retrieval tool let Gemini skip retrieval invisibly, so `hallucination` scored 1.0 blind. | Explicit `search_support_docs` / `search_policy_docs` function tools; quote only returned chunks. |
| F21 | The golden path ended on raw compliance JSON. | The remediation agent writes an approver summary before the approval request and lists violations when blocked. |
| F22 | The tool-use judge saw no tools: ADK's `/app-info` only describes an `LlmAgent` root. | `tests/eval/enrich_traces.py` adds all agent and tool definitions before grading. |
| F23 | Structured output was 9× slower on the `global` endpoint, and evals timed out. | `GOOGLE_CLOUD_LOCATION=europe-west3`. |
| F24 | With several recommended actions, the Compliance Agent checked them all, including a past change cited as evidence, and returned the non-compliant one. | One "Primary recommended action"; the Compliance Agent checks only that. |
| F25 | A web-search result kept appearing as the root cause. | External signals in their own section; root cause and approver summary use internal evidence only. |
| F26 | Direct requests got no approver summary (found by the held-out set). | The summary is unconditional, with a variant for direct requests. |
| F27 | On the engine, the RAG tools got 401: a hard-coded regional `api_endpoint` bypassed the library's mTLS host selection, so Agent Identity's certificate-bound tokens hit the plain host. | Pick the `-aiplatform.mtls` host via `should_use_mtls_endpoint()`, with a one-time fallback on 401. |
| F28 | The explicit Memory Bank fact was written twice per session (the callback runs after each turn). | Written once per session and incident. |
| F29 | `gcsfs` logged a harmless 401 warning on every upload (same mTLS cause), hundreds per run. | Its logger is set to errors only. |
| F30 | Agent Registry rejected the Compliance Agent's card: it carries both A2A 0.3 and 1.0 shapes ("ambiguous Agent Card", then "duplicate interface url"). | Terraform registers a 1.0-only copy; the served card is unchanged. |
