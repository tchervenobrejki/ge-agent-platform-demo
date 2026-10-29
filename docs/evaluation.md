# Evaluation

How the orchestrator is evaluated: locally with `agents-cli eval`, and optionally with the console's managed
Agent Evaluation. [Notebook 07](../notebooks/07_evaluation.ipynb) runs the guardrail cases.

## Local evaluation with agents-cli

### Datasets

All in [`growth-risk-agent/tests/eval/`](../growth-risk-agent/tests/eval/). Every case has a prompt and its own
pass/fail rubric (`rubric_groups.case_criteria`).

| File | Cases | Used for |
|---|---|---|
| `datasets/task-cases.json` | the golden-path investigation | development |
| `guardrails/guardrail-cases.json` | vague request, policy violation, prompt injection | development |
| `holdout/task-cases.json` | a direct, compliant action | a final check only |
| `holdout/guardrail-cases.json` | two guardrail variants | a final check only |

Grade the held-out sets once, at the end. Fixing the agent against them turns them into development data: this
happened once here (F26), so add fresh held-out cases when the agent changes again.

### Metrics

| Metric | Kind | What it checks |
|---|---|---|
| `final_response_quality` | LLM judge | The case's own rubric |
| `multi_turn_task_success` | LLM judge | Did the agent achieve the user's goal? |
| `multi_turn_tool_use_quality` | LLM judge | Were the right tools called, with the right arguments? |
| `hallucination` | LLM judge | Is every claim supported by the trace? |
| `compliance_gate_respected` | **deterministic** ([`compliance_gate.py`](../growth-risk-agent/tests/eval/compliance_gate.py)) | 0 for any write without `compliant=true` *and* human confirmation |

**Task cases and guardrail cases use different configs.** `multi_turn_task_success` and
`multi_turn_tool_use_quality` derive the user's goal from the literal request ("get the discount approved"), so
they score a correct refusal as a failure. Guardrail cases use only their own rubric, `hallucination` and the
compliance gate (`eval_config_guardrails.yaml`); task cases use all five (`eval_config.yaml`).

### Running

```bash
cd growth-risk-agent
tests/eval/run_eval.sh tests/eval/guardrails/guardrail-cases.json tests/eval/eval_config_guardrails.yaml
tests/eval/run_eval.sh tests/eval/datasets/task-cases.json         tests/eval/eval_config.yaml
```

The script runs three steps rather than `agents-cli eval run`:

1. `agents-cli eval generate` runs each case against the agent code locally and records the traces. The Compliance
   Agent it calls is the one at `COMPLIANCE_AGENT_URL` (from `.env`: the deployed one).
2. `enrich_traces.py` adds the definitions of all agents and tools to the traces. ADK's `/app-info` only describes an
   `LlmAgent` root, so with a `SequentialAgent` root the tool-use judge would see no tools (F22).
3. `agents-cli eval grade` scores the traces. Traces and results land in `artifacts/` (gitignored).

### What the evaluations caught

The first baseline scored 0.81 on `final_response_quality` and 0.33 on tool use, and `hallucination` scored a blind
1.0 while the agent was inventing evidence. Fixing that took six changes: F20 (fabricated RAG sources), F21 (raw
JSON as the final answer), F22 (judge saw no tools), F23 (timeouts from the `global` endpoint), F24 (arbitrary
action picked for compliance), F25 (web search as root cause). The held-out set then found F26. See the
[fix log](design-decisions.md#fix-log).

| Set | final_response_quality | task_success | tool_use | hallucination | compliance_gate |
|---|---|---|---|---|---|
| Golden path ×3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Guardrails ×3 | 1.00 | — | — | 1.00 | 1.00 |
| Held-out direct action | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 |
| Held-out guardrails ×2 | 1.00 | — | — | 1.00 | 1.00 |

The 0.75: `multi_turn_task_success` expects the ticket to be created in a single turn, but the design requires a
human approval first, so the run correctly stops at the approval request.

## Console Agent Evaluation

The console's **Agent Evaluation** generates scenarios from a short brief, lets an LLM play the user for up to five
turns against a *deployed* agent, and scores the conversations. It is optional, and it has constraints worth
knowing before you start.

### Constraints

- It runs only in **europe-west1 / europe-west4**, and only reaches agents **in its own region**. The orchestrator
  runs in europe-west3, so evaluating it needs a copy in europe-west1. `gemini-3.5-flash` isn't offered in
  europe-west1, so the copy still calls Gemini in europe-west3.
- Replace the **Agent config** placeholder (a travel agent) with [`console-eval/agent_config.json`](console-eval/agent_config.json),
  or the scenarios are generated from the placeholder. The field is a top-level map keyed by agent ID.
- List only real function tools there. Built-in tools (Google Search grounding, `preload_memory`) aren't function
  calls, so the judge marks them "never called".
- It calls `async_stream_query` and then `async_get_session` on every turn, and fails on the content-less checkpoint
  events resumable ADK apps write ("'NoneType' object has no attribute 'get'"). The copy sets
  `STREAM_SKIP_EMPTY_EVENTS=true`, and the adapter drops those events from both reads.
- Use **3–5 scenarios**: 10 parallel conversations exceeded the 300 session-event appends per minute quota (429s).
  Scale the copy up first (`min_instances` 3) to avoid cold-start 500s, and back to 0 afterwards.
- **Rerun** re-grades the stored answers without calling the agent. Start a new run instead.
- Scenarios are regenerated each run, so runs aren't comparable unless the scenario set is fixed.
- The simulated user *types* approvals, so human-in-the-loop scenarios loop at the approval step.
- Judges mark conditional rubrics that don't apply as failures: read the reasoning, not just the score.

### Getting it to work

Each attempt failed for a different reason; changing one thing at a time against a working baseline found them.

| Attempt | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | every item: *location ID doesn't match the endpoint* | evaluation in europe-west1, agent in europe-west3 | a copy in europe-west1 |
| 1 | flight and hotel scenarios | the travel-agent placeholder left in **Agent config** | this project's agent config |
| 2 | *'NoneType' object has no attribute 'get'* | content-less checkpoint events in the session reads | `STREAM_SKIP_EMPTY_EVENTS` |
| 2 | 429 RESOURCE_EXHAUSTED, 500 | 10 parallel conversations; a cold start | 3–5 scenarios, warm instances |
| 3 | the same errors again | **Rerun** never calls the agent | a new run |
| 4 | ✅ scored | — | found a missed prompt injection ("Ignore **all your** previous instructions") and a missing confirmation after approval; both fixed |

What found the empty-event problem: a one-agent control ([`app/eval_control_agent.py`](../growth-risk-agent/app/eval_control_agent.py),
served when `EVAL_CONTROL_AGENT=true`) deployed with the same container passed, and request logging
(`LOG_REASONING_ENGINE_CALLS=true`) showed which methods the console called.

The scored run: task success 0.69, tool use 0.85, trajectory 0.73.

### Deploying the europe-west1 copy

The copy uses the same Terraform module with [`vars/workshop-eval.tfvars`](../growth-risk-agent/deployment/terraform/single-project/vars/workshop-eval.tfvars)
and its own state, and reuses the same data, corpora, MCP server and Compliance Agent.

```bash
cd growth-risk-agent/deployment/terraform/single-project
TF_DATA_DIR=.terraform-workshop terraform init -reconfigure \
  -backend-config="prefix=workshop-growth-risk-agent/europe-west1"
TF_DATA_DIR=.terraform-workshop terraform apply -var-file=vars/workshop-eval.tfvars
```

`agents-cli deploy` targets the engine named in `deployment_metadata.json`, so deploy the copy from a scratch copy
of `growth-risk-agent/` without that file:

```bash
agents-cli deploy --project YOUR_PROJECT_ID --region europe-west1 \
  --service-name workshop-growth-risk-agent --agent-identity --update-only \
  --update-env-vars GOOGLE_CLOUD_LOCATION=europe-west3,BQ_ANALYTICS_LOCATION=europe-west1,STREAM_SKIP_EMPTY_EVENTS=true
```

Set `enable_console_eval = true` in `platform/terraform/terraform.tfvars` and apply it, for the bucket the console
writes results to. The copy's settings for the console form are in [`console-eval/`](console-eval/).

**Before destroying the copy's state:** it also holds project-wide entries the main deployment relies on (the API
enablements, the Vertex AI service identity and its roles, the default compute service account's build role).
`terraform state rm` those first, or the destroy removes them for both.
