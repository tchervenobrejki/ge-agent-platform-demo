# Lessons learned: building ADK agents on Google Cloud

Reusable findings from building this multi-agent system (October 2026: agents-cli 1.10, ADK 2.11,
Agent Runtime, Cloud Run, Terraform). Each lesson says what happens and what to do. `F<n>` points to the
fix with that number in [design-decisions.md](design-decisions.md#fix-log).

Versions move fast: re-check anything version-specific against the current release notes before relying on it.

## How to work

- **Prove the platform before porting code.** Deploy the *unmodified* scaffold first and confirm traces,
  sessions and logs arrive. Debugging telemetry on a 2-tool agent is easy; on a 15-agent
  pipeline it is not.
- **Re-scaffold rather than upgrade across many versions.** agents-cli 1.0 → 1.10 changed telemetry,
  identity and A2A in most generated files; a fresh scaffold plus ported agent code was cleaner.
- **When something fails, isolate it against a working baseline.** The console-evaluation failure was solved
  by deploying a one-agent *control* with the same container (it passed) and logging which methods the
  service called. Change one thing at a time; don't stack guesses.
- **Verify live, not just locally.** Several bugs only appeared on the deployed engine (RAG 401 under Agent
  Identity F27, duplicate memory writes F28). Each deploy gets a smoke test of the golden path.
- **Keep Terraform drift at zero.** After every apply, `terraform plan` must say *No changes*. Remote state in a
  versioned GCS bucket, one prefix per project.
- **Confirm every billable or destructive step** before running it; look at a resource before deleting it.
- **Deleting an engine leaves its Agent Identity IAM grants behind.** Remove them explicitly
  (`gcloud projects get-iam-policy … | grep <engine-id>`).

## agents-cli and Agent Runtime deployment

- **`agents-cli deploy` picks its target engine from `deployment_metadata.json`,** and without that file it
  looks for an engine whose display name is the project name (the one Terraform created). It has no flag for
  the target engine. To deploy a second copy, deploy from a scratch copy of the project folder with
  `--service-name` and metadata that names the copy. Never edit the main deployment's metadata file.
- **`agents-cli deploy` copies `.env` into the deployed environment,** and `.env` values win over what is
  already set. Point a local run at `localhost` with a process env var (`COMPLIANCE_AGENT_URL=… adk web`), never
  in `.env`, or the next deploy ships the `localhost` URL.
- **`agents-cli infra single-project` passes no `-var-file`:** it runs `terraform plan -var project_id=…` and
  nothing else, so every other variable needs a default or a `terraform.tfvars` (which Terraform loads
  automatically). Values in `vars/env.tfvars` are ignored.
- **The scaffold's `terraform destroy` stops at the first non-empty resource.** The logs bucket and the
  telemetry dataset need `force_destroy` / `delete_contents_on_destroy` (set here), and an engine with sessions or
  memories only deletes with `force=true`, which its Terraform resource can't send: delete it first with
  `agent_engines.delete(force=True)`. Both settings are read from state, so add them before the first apply.
- **Always pass `--agent-identity` explicitly.** Without it a newly created engine gets no Agent Identity.
- **Terraform owns the engine; deploy owns the code.** Put `deployment_spec`, `source_code_spec` and
  `class_methods` in `lifecycle.ignore_changes` (F19): otherwise a re-apply deletes the method contract the
  console playground and `:streamQuery` rely on. Consequence: env var changes in `service.tf` only apply at
  creation; later changes go through `agents-cli deploy` (from `.env` or `--update-env-vars`).
- **`GOOGLE_CLOUD_PROJECT` is reserved** on Agent Runtime (rejected in `deployment_spec.env`);
  `GOOGLE_CLOUD_LOCATION` is allowed.
- **Scale to zero has cold starts.** Fine for demos; for bursts (e.g. 10 parallel evaluation conversations)
  raise `min_instances` temporarily, then set it back. `min_instances` can be patched through the API
  without a rebuild (`updateMask=spec.deployment_spec.min_instances`).
- **Size memory with concurrency.** A parallel fan-out of 4 branches fit in 4 GiB at `container_concurrency=4`.
- **Two Terraform states can share project-level resources** (API enablement, service-agent roles). Destroying
  one stack removes those bindings for both: `terraform state rm` them first.

## Models and regions

- **Model availability is per region.** `gemini-3.5-flash` existed in europe-west3 and `global` but not in
  europe-west1/europe-west4. Check with a free `:countTokens` call before choosing a region.
- **The agent's region and the model's region can differ.** `GOOGLE_CLOUD_LOCATION` sets where Gemini is
  called; the engine runs elsewhere. Keep other location-dependent clients (e.g. BigQuery Analytics) on their
  own variable.
- **Prefer a regional endpoint over `global` for structured output.** The same triage call took 56 s on
  `global` vs 6.6 s in-region (F23).

## Identity and authentication

- **Agent Identity uses mTLS certificate-bound tokens.** Clients that hard-code a regional `api_endpoint` skip
  the library's mTLS host selection and get 401. Pick the `-aiplatform.mtls` host via
  `google.auth.transport.mtls.should_use_mtls_endpoint()`, falling back to the plain host on 401 (F27).
- **Calling private Cloud Run services from an agent:** impersonate a dedicated caller service account to mint
  ID tokens (Token Creator on that SA for the agent's principal; `run.invoker` for the SA on the service).
  Disable ADK's MCP mTLS auto-config for these calls (F4).
- **MCP SDK 2.x uses `httpx2`,** so it needs an `httpx2.Auth`; an `httpx.Auth` is silently rejected and the tools
  never load (symptom: `MALFORMED_FUNCTION_CALL`) (F12).
- **`load_dotenv()` must run before the agent is imported** (`app/__init__.py`), or module-level config reads
  empty values locally (F11).
- **Secrets go to Secret Manager, never `.env` in git** (`agents-cli deploy --secrets ENV=SECRET`).

## ADK agent design

- **Each downstream step needs its own gate.** In ADK 2.11 a sub-agent runs on a copied context, so
  `end_invocation` from one step never stops the parent `SequentialAgent`. Use a `before_agent_callback` on
  every later step; returning `Content` with no parts skips silently (F14).
- **Callbacks on agents with `output_schema` must return schema-valid JSON**, or the run crashes (F15).
- **Code guardrails need patterns, not exact phrases.** "Ignore *all your* previous instructions" slipped past
  four fixed strings. Use regexes *and* a model-level instruction for phrasings the patterns miss.
- **Out-of-scope requests need an explicit path.** If triage extracts "the user's own wording" as an action,
  anything becomes an action and goes to the compliance check.
- **Ask for exactly one recommended action.** With several, the compliance step picked an arbitrary one,
  including a past change cited as evidence (F24).
- **Keep root causes on internal evidence;** put web-search findings in a separate section (F25).
- **Human-in-the-loop (`require_confirmation=True`) needs `ResumabilityConfig(is_resumable=True)`** on the App,
  otherwise approval starts a new run. Approval must come back as a `FunctionResponse` with a
  `ToolConfirmation`; typed "yes" starts a new turn. After the tool returns, tell the agent to report the outcome.
- **Resumable apps write content-less checkpoint events** (about a third of a session). Our own code must
  tolerate `content=None`; some Google tooling doesn't (see Evaluation).
- **Memory Bank must be wired into every runner** (FastAPI app, A2A runner, `AdkApp`), or `preload_memory`
  silently does nothing (F1). Write explicit facts once per session (F28).
- **Never fabricate fallback data in tools.** Return errors; the model reports them honestly (F17).
- **`SequentialAgent`/`ParallelAgent`/`LoopAgent` are deprecated in ADK 2.11** in favour of the graph Workflow API;
  they still work.

## RAG

- **Use an explicit retrieval function tool, not `VertexAiRagRetrieval`.** The built-in tool lets Gemini skip
  retrieval invisibly; the agents fabricated ticket IDs and policy sections, and `hallucination` scored 1.0
  blind (F20). With `RetrieveContexts` in a function tool, every retrieval shows in the trace, and the
  instruction can say "quote only returned chunks".
- **Pin the embedding model** (`text-embedding-005`); the SDK default failed corpus indexing with code 13.

## A2A and MCP

- **A2A answers can arrive as a Task with status updates;** extract the result from the relayed tool call too,
  and fail closed (F13).
- **Agent Registry rejects cards that carry both A2A 0.3 and 1.0 shapes** ("ambiguous Agent Card"); register a
  1.0-only copy (F30). Cloud Run agents aren't auto-registered; Agent Runtime agents are (as type `CUSTOM`).
- **MCP calls aren't traced under MCP SDK 2.x** (no httpx2 instrumentor yet); the `execute_tool` span remains.

## Observability

- **The 1.10 scaffold's telemetry works as generated** (`otel_to_cloud`, Terraform-configured). Don't add
  custom exporters or SSL workarounds (F2).
- **`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT` doesn't disable prompt logging:** content
  still goes to GCS via the completion hook and the BigQuery `completions_view`; only spans stay content-free.
- **Enable BigQuery Agent Analytics only when deployed** (`BQ_ANALYTICS_DATASET_ID` set); locally it created a
  US dataset and its retries slowed calls past timeouts (F18).
- **Expected noise:** `gcsfs` "Could not determine bucket type … 401" under Agent Identity is harmless (F29);
  the Analytics plugin's BigQuery calls appear as separate root traces.

## Evaluation

- **Local (`agents-cli eval`):** keep a held-out set and grade it only at the end; split task cases from guardrail
  cases, because `multi_turn_*` metrics invent a user goal and fail correct refusals. Add a deterministic metric
  for the safety rule (e.g. "no write without compliance + approval").
- **Console Agent Evaluation, constraints found:**
  - runs only in europe-west1/europe-west4 and only reaches agents in its own region;
  - replace the **Agent config** placeholder (a travel agent) or scenarios are generated from it; the field is a
    top-level map keyed by agent ID (no `"agents"` wrapper);
  - list only real function tools there: built-in Google Search and `preload_memory` get marked "never called";
  - it calls `async_stream_query` and then `async_get_session` on every turn and fails on content-less events
    ("'NoneType' object has no attribute 'get'"): filter them from the stream and from session reads;
  - **Rerun** re-grades stored answers without calling the agent: start a new run instead;
  - scenarios are regenerated each run, so runs aren't comparable unless the scenario set is fixed;
  - the simulated user types approvals, so HITL scenarios loop at the approval step;
  - 10 parallel conversations exceeded the 300 session-event appends/min quota: use 3–5 scenarios;
  - judges mark conditional rubrics that don't apply as failures: read the reasoning, not just the score.

## Consoles and tooling

- **The console playground shows a HITL pause but can't approve it;** approve in `adk web` or via the API.
- **`adk web` behind a proxy** (e.g. Vertex AI Workbench) needs `--url_prefix /proxy/absolute/<port>` and
  `--allow_origins https://<proxy-host>`, or its DNS-rebinding guard returns "Forbidden: host not allowed".
- **Hosted notebooks (Workbench):** build a dedicated Jupyter kernel from the project's locked dependencies; upgrading
  packages in the base kernel broke `google-auth`.
- **Engine clients should use `async_stream_query`,** not the deprecated `stream_query` (F7).
- **zsh treats `$var:` as a modifier.** In `"…/models/$m:countTokens"`, zsh parses `:c` as a history modifier and
  mangles the URL (every call returned an HTML 404). Write `${m}:countTokens`.
