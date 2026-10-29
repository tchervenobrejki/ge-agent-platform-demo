# Setup: the resources the agents depend on

The two agents deploy with Terraform (`agents-cli infra` / `agents-cli deploy`), but they also rely on
resources that exist before any agent does: demo data to investigate, documents to search, a
ticketing tool to call, and an identity to call it with. These scripts create them in your project.

| Step | Script | Creates |
|---|---|---|
| 1 | `01_project.sh` | APIs, Terraform state bucket, the caller service account, IAM for local runs and source deploys |
| 2 | `02_bigquery.sh` | BigQuery dataset `demo_growth` with three small tables from [`data/bigquery/`](../data/bigquery/) |
| 3 | `03_rag_corpora.py` | Two RAG Engine corpora from [`data/policies/`](../data/policies/) and [`data/support/`](../data/support/) |
| 4 | `04_mcp_server.sh` | The remediation MCP server on Cloud Run (private) |
| 5 | `05_write_config.py` | Nothing in the cloud: writes a `terraform.tfvars` per Terraform stack, the state bucket into each backend, and each agent's `.env` |
| – | `99_teardown.sh` | Deletes all of the above and switches off RAG Engine billing |

## Before you start

- A Google Cloud project with billing enabled, where you have the **Owner** role.
- [`gcloud`](https://cloud.google.com/sdk/docs/install) (includes `bq`) and [`uv`](https://docs.astral.sh/uv/).
- Signed in, with your project selected:

```bash
gcloud auth login
gcloud auth application-default login   # the Python scripts and the agents use these credentials
gcloud config set project YOUR_PROJECT_ID
```

Everything regional goes to `europe-west3` by default. To use another region, `export REGION=...` before
running the scripts. Pick one where Gemini, Agent Runtime and RAG Engine are all available.

## Run

From the repository root:

```bash
./setup/01_project.sh
./setup/02_bigquery.sh
uv run setup/03_rag_corpora.py
./setup/04_mcp_server.sh
uv run setup/05_write_config.py
```

Each script is safe to run again if something fails partway. Step 4 takes a few minutes, because
Cloud Build builds the server's container image.

## What each piece is for

**The caller service account** (`growth-risk-mcp-caller`). The compliance agent and the MCP server are
private Cloud Run services: a request needs an ID token for a principal holding `roles/run.invoker`
on that service. The orchestrator runs as its own Agent Identity, which can't mint those tokens
directly, so it *impersonates* this service account (see `growth-risk-agent/app/tools/gcp_auth.py`).
Step 1 lets you impersonate it too, so the agent works the same way on your machine.

**BigQuery.** The metrics branch of the investigation writes SQL against these tables, runs it and
retries on errors. The data is synthetic: campaign `CAMP-2025-042` loses conversions on 2025-06-26,
and the funnel shows 57.1% drop-off at checkout.

**RAG Engine.** Two corpora, so policy and support content stay separate: the agent cites runbooks as
evidence and checks proposed actions against policy. Each document is chunked, embedded with
`text-embedding-005` and stored in RAG Engine's managed vector database.

**The MCP server.** The one tool that *changes* something: it creates a remediation ticket. The agent
only calls it after the compliance agent approves the action *and* a human confirms it.

## Cost

Small for a demo, with one exception. **RAG Engine's default Basic tier runs on Spanner and is
billed for as long as it is provisioned, even with no queries.** When you're done, run
`./setup/99_teardown.sh`, or delete the project.

## Cleaning up

Destroy the deployed agents with Terraform first (see the main README): their state lives in the
bucket that teardown deletes. Then:

```bash
./setup/99_teardown.sh
```

Or delete the whole project: `gcloud projects delete YOUR_PROJECT_ID`.
