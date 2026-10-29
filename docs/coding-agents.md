# Building this with a coding agent

This project was built with an AI coding agent working alongside a human, guided by **skills**: folders with a
`SKILL.md` file of instructions, reference docs and scripts that teach an agent one job, such as scaffolding an ADK
project or deploying to Agent Runtime. Google publishes skills for exactly the workflow in this repo.

Skills are plain Markdown, so they work with any coding agent: Claude Code, Antigravity, Gemini CLI, Codex,
Cursor or another. Agents that support the Agent Skills format load the folders automatically. With any other
agent, point it at a skill's `SKILL.md` (the raw GitHub URL works) and ask it to follow that file.

## Start here

**[`google-agents-cli-onboarding`](https://github.com/google/skills/blob/main/skills/cloud/google-agents-cli-onboarding/SKILL.md)**
is the entry point. It maps the agent lifecycle to seven specialised skills and is the one to give your agent first.
Raw file: <https://raw.githubusercontent.com/google/skills/main/skills/cloud/google-agents-cli-onboarding/SKILL.md>

## The agents-cli skills, one per lifecycle phase

They live in [`google/agents-cli`, under `skills/`](https://github.com/google/agents-cli/tree/main/skills).

| Phase | Skill | What it covers | Used here for |
|---|---|---|---|
| 0–1 Understand, study | [`google-agents-cli-workflow`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-workflow) | The end-to-end workflow, the spec, studying samples | [`.agents-cli-spec.md`](../.agents-cli-spec.md), the build order |
| 2 Scaffold | [`google-agents-cli-scaffold`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-scaffold) | `agents-cli scaffold create / enhance / upgrade` | Both projects ([notebook 01](../notebooks/01_scaffold_and_code_tour.ipynb)) |
| 3 Build | [`google-agents-cli-adk-code`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-adk-code) | ADK agents, tools, callbacks, state | Everything in `app/` |
| 4 Evaluate | [`google-agents-cli-eval`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-eval) | Eval datasets, metrics, LLM-as-judge | `tests/eval/` ([evaluation](evaluation.md)) |
| 5 Deploy | [`google-agents-cli-deploy`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-deploy) | Agent Runtime, Cloud Run, Terraform, IAM | [Notebook 04](../notebooks/04_deploy.ipynb) |
| 6 Publish | [`google-agents-cli-publish`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-publish) | Agent Registry, Gemini Enterprise | The Compliance Agent's registry entry |
| 7 Observe | [`google-agents-cli-observability`](https://github.com/google/agents-cli/tree/main/skills/google-agents-cli-observability) | Cloud Trace, logging, BigQuery Agent Analytics | [Notebook 06](../notebooks/06_observability.ipynb) |

## Google Cloud skills that helped

From [`google/skills`](https://github.com/google/skills) (see its
[README](https://github.com/google/skills/blob/main/README.md) for the full catalogue):

| Skill | Useful for |
|---|---|
| [`agent-platform-rag-engine-management`](https://github.com/google/skills/tree/main/skills/cloud/agent-platform-rag-engine-management) | Listing and querying RAG corpora |
| [`agent-platform-eval-flywheel`](https://github.com/google/skills/tree/main/skills/cloud/agent-platform-eval-flywheel) | Evaluation methodology, failure analysis |
| [`agent-platform-troubleshooting`](https://github.com/google/skills/tree/main/skills/cloud/agent-platform-troubleshooting) | Agent Runtime 500s, Agent Identity, Agent Registry, 403s |
| [`iam-helper-for-troubleshooting`](https://github.com/google/skills/tree/main/skills/cloud/iam-helper-for-troubleshooting) | Diagnosing access denials, finding the least-privileged role |
| [`google-cloud-recipe-auth`](https://github.com/google/skills/tree/main/skills/cloud/google-cloud-recipe-auth) | Service identities, Application Default Credentials, impersonation |
| [`cloud-run-basics`](https://github.com/google/skills/tree/main/skills/cloud/cloud-run-basics) | Deploying and securing the Compliance Agent and MCP server |
| [`cloud-trace-querying`](https://github.com/google/skills/tree/main/skills/cloud/cloud-trace-querying) | Checking spans and trace trees after a deploy |
| [`cloud-logging-query-generation`](https://github.com/google/skills/tree/main/skills/cloud/cloud-logging-query-generation) | Finding errors in the agents' logs |
| [`agent-platform-alert-configuration`](https://github.com/google/skills/tree/main/skills/cloud/agent-platform-alert-configuration) | Latency, error and token alerts as Terraform (not set up here) |
| [`google-cloud-solution-multi-agent-security`](https://github.com/google/skills/tree/main/skills/cloud/google-cloud-solution-multi-agent-security) | Agent Gateway, Model Armor and IAP for multi-agent traffic (not set up here) |

## Installing them

- **The agents-cli skills:** `uvx google-agents-cli setup` installs the CLI and its skills. It uses `npx`, so it
  needs Node.js.
- **Everything in google/skills:** `npx skills add google/skills`. That is more than a hundred skills; most
  agents only load a skill when it is relevant, but a smaller set keeps things focused.
- **Single skills:** copy the skill's folder (not just `SKILL.md`: many have `references/` and `scripts/`) into
  your agent's skills directory, or link the raw `SKILL.md` in your prompt.

**Read a skill before installing it.** Skills are instructions your agent will follow and may include scripts it
will run. Several here call `gcloud` with your credentials; that is their job, but you should know what they do.

## How the skills were used on this project

The agents-cli workflow skill shaped the order of work, and most of the lessons in
[lessons-learned.md](lessons-learned.md) came from following it:

1. **Spec first.** [`.agents-cli-spec.md`](../.agents-cli-spec.md) states the use cases, tools, constraints and
   success criteria before any code.
2. **Prove the platform with the unmodified scaffold.** Deploy it as generated and check that traces, sessions and
   logs arrive before porting any agent code.
3. **Build, then evaluate locally** until the rubrics pass, with a held-out set graded once at the end.
4. **Deploy, then verify live**, because several bugs only appeared on the deployed engine.

Ask your agent to confirm every billable or destructive step before running it. The skills say so too.
