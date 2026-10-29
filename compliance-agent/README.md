# compliance-agent

The Compliance Agent: a single ADK agent on **Cloud Run** that checks a proposed remediation action against
campaign policy and answers over **A2A**. The [orchestrator](../growth-risk-agent/) calls it before proposing any
action. Scaffolded with `agents-cli` 1.10 (`-d cloud_run --bq-analytics`).

It is a separate service on purpose: the agent that proposes an action can't change the rules it is judged by. The
verdict comes from code, `check_action_compliance` in [`app/tools/action_tools.py`](app/tools/action_tools.py),
and unknown actions fail closed.

## Layout

```
app/
├── agent.py                 the agent and its instruction
├── tools/action_tools.py    the policy rules (same file as in growth-risk-agent)
├── fast_api_app.py          scaffold: FastAPI server with the A2A routes at /a2a/app
└── app_utils/               scaffold: A2A card and routes, services
deployment/terraform/single-project/
├── service.tf               private Cloud Run service, its service account
├── custom_iam.tf            roles/run.invoker for the orchestrator's caller service account
├── custom_registry.tf       Agent Registry entry (type A2A)
└── compliance_agent_card.json   the card registered in Agent Registry
```

## Run locally

```bash
uv sync
uv run uvicorn app.fast_api_app:app --port 8001
curl -s http://localhost:8001/a2a/app/.well-known/agent-card.json
```

## Deploy

```bash
agents-cli infra single-project --project YOUR_PROJECT_ID --apply
agents-cli deploy --project YOUR_PROJECT_ID --region europe-west3 \
  --service-account compliance-agent-app@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --memory 2Gi --cpu 1 --min-instances 0 --max-instances 3 --concurrency 4
```

The sizing flags match `service.tf`, so `terraform plan` stays clean after a deploy. The service is private: calls
need an ID token for a principal with `roles/run.invoker` (see [notebook 04](../notebooks/04_deploy.ipynb)).

When you change the agent's name, description or tools, refresh `compliance_agent_card.json` with the command in
`custom_registry.tf` and re-apply.
