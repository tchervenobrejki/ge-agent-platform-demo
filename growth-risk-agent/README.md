# growth-risk-agent

The orchestrator: an ADK multi-agent pipeline on **Agent Runtime** that investigates a campaign's conversion drop,
asks the [Compliance Agent](../compliance-agent/) over A2A whether its recommended action is allowed, and proposes a
remediation ticket that a human must approve. Scaffolded with `agents-cli` 1.10 (`-d agent_runtime --bq-analytics`).

See the [main README](../README.md) for the full walkthrough; this page is a map of the project.

## Layout

```
app/
├── agent.py                 root SequentialAgent and the App (plugins, resumability)
├── schemas.py               TriageContext: the structured output of triage
├── sub_agents/
│   ├── triage.py            request → structured fields; clarification and injection gates
│   ├── investigation.py     ParallelAgent: metrics, support RAG, policy RAG, Google Search
│   ├── metrics.py           LoopAgent: generate SQL → run → retry on error; KPIs
│   ├── synthesizer.py       evidence-based report with one recommended action
│   └── action_pipeline.py   Compliance Agent (A2A) → remediation (MCP, human approval)
├── tools/
│   ├── bigquery_tools.py    read-only SQL, KPI maths
│   ├── rag_tools.py         search_support_docs / search_policy_docs (RAG Engine)
│   ├── callbacks.py         guardrails and the gates between steps
│   ├── gcp_auth.py          ID tokens for the private Cloud Run services
│   ├── a2a_auth.py          the A2A client for the Compliance Agent
│   ├── a2a_callbacks.py     reading the compliance verdict into session state
│   ├── memory_tools.py      Memory Bank writes
│   ├── artifact_tools.py    saves the report to Cloud Storage
│   └── action_tools.py      the compliance schema (same file as in compliance-agent)
├── app_utils/               scaffold: services, A2A routes, the Agent Runtime adapter
└── extras/                  illustrative only: a graph Workflow variant, an Agent Registry discovery example
deployment/terraform/single-project/   the engine, Agent Identity, IAM, telemetry
tests/unit, tests/integration, tests/eval
```

## Run

```bash
uv sync
cp .env.example .env        # or run ../setup/05_write_config.py, which fills it in
uv run adk web .            # developer UI at http://localhost:8000/dev-ui/
uv run pytest tests/unit    # unit tests
```

To call a locally run Compliance Agent instead of the deployed one, set the URL on the command line, not in
`.env` (`agents-cli deploy` copies `.env` to the deployed agent):

```bash
COMPLIANCE_AGENT_URL=http://localhost:8001/a2a/app uv run adk web .
```

## Deploy

```bash
agents-cli infra single-project --project YOUR_PROJECT_ID --apply   # Terraform: engine, identity, IAM, telemetry
agents-cli deploy --project YOUR_PROJECT_ID --region europe-west3 --agent-identity --update-only
```

Terraform creates the engine and `deploy` updates its code; see [design decisions](../docs/design-decisions.md)
for why, and [notebook 04](../notebooks/04_deploy.ipynb) for the walkthrough.

## Evaluate

```bash
tests/eval/run_eval.sh tests/eval/guardrails/guardrail-cases.json tests/eval/eval_config_guardrails.yaml
```

See [docs/evaluation.md](../docs/evaluation.md).
