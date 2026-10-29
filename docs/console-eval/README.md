# Console Agent Evaluation settings

Copy-paste inputs for **Agent Platform → Agents → Deployments → workshop-growth-risk-agent → Evaluation**.

| Field | Value |
|---|---|
| Region | `europe-west1` (console evaluation runs only in europe-west1/europe-west4, and only reaches agents in its own region) |
| Agent | `workshop-growth-risk-agent` (its engine ID is printed by `agents-cli deploy`) |
| Output location | `gs://YOUR_PROJECT_ID-eval` |
| Scenarios | 3–5 (the 300 session-event appends/minute quota fails larger parallel batches with 429s) |
| Metrics | `multi_turn_task_success`, `multi_turn_tool_use_quality`, `multi_turn_trajectory_quality` |
| Generation guidance | [generation_guidance.txt](generation_guidance.txt) |
| Agent config | [agent_config.json](agent_config.json): a top-level map of agents, no `"agents"` wrapper |

Start a **new** run each time: "Rerun" re-grades the previous run's stored answers without calling the agent.
Before a run, scale the copy up (`--min-instances 3`) so parallel conversations don't hit a cold start; scale back to 0 afterwards.

Built-in model tools (Google Search grounding, `preload_memory`) are not function calls, so they are described in
the agent text rather than listed as tools; otherwise the judge marks them "never called".
