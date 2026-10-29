"""Graph-based Workflow rebuild of sub_agents.metrics.sql_refinement_loop.

Illustrative only, NOT wired into the deployed app: ADK 2.11 deprecates
SequentialAgent/ParallelAgent/LoopAgent in favour of the graph Workflow API,
and this shows what the SQL retry loop looks like in that style.

Run locally, side by side with the main app, for comparison:
    adk web app/extras --port 8502
(from inside growth-risk-agent/, with the venv active -- bypasses
`agents-cli playground` deliberately, since this is local-only/illustrative.)
"""

from __future__ import annotations

from google.adk import Agent, Context, Workflow

from ..tools.bigquery_tools import (
    DATASET,
    PROJECT_ID,
    calculate_kpi,
    execute_metrics_query,
)

MODEL = "gemini-3.5-flash"

triage_agent = Agent(
    model=MODEL,
    name="triage_agent",
    description="Parses growth/risk investigation requests and extracts structured context.",
    instruction="""You are the triage agent for Digital Growth & Risk Operations.

Extract from the user request:
- campaign_id (e.g. CAMP-2025-042)
- incident_date (default yesterday if not specified)
- issue_type (conversion_drop, traffic_spike, etc.)

You MUST NOT answer with metrics or recommendations — only structure the request.
If campaign_id is missing and the request is vague, ask one clarifying question.

Output a brief JSON-like summary of extracted fields.""",
    output_key="triage_context",
)

sql_generator_agent = Agent(
    model=MODEL,
    name="sql_generator_agent",
    description="Generates BigQuery SQL to investigate campaign metrics.",
    instruction="""You generate BigQuery SQL for growth metrics investigation.

Context: {triage_context}

Tables (dataset demo_growth):
- campaign_daily(campaign_id, date, impressions, clicks, conversions, spend_eur)
- funnel_daily(date, step, users, drop_off_pct)

Rules:
1. Output ONLY a valid SELECT query (no markdown fences).
2. First attempt: query campaign_daily for the campaign across incident date and prior day.
3. If prior attempt failed (see {metrics_query_result?}), fix column/table names and retry.
4. Use fully qualified table names: `""" + f"{PROJECT_ID}.{DATASET}" + """.campaign_daily`

Also query funnel_daily for checkout drop-off on the incident date.""",
    output_key="generated_sql",
)

# Unlike sub_agents.metrics.sql_executor_agent, this agent does NOT call
# exit_loop/escalate to terminate -- the graph's own routing (see
# check_sql_result below) decides whether to loop back or move on.
sql_executor_agent = Agent(
    model=MODEL,
    name="sql_executor_agent",
    description="Executes generated SQL and reports the result for routing.",
    instruction="""Execute the SQL investigation using the execute_metrics_query tool.

Generated SQL to run:
{generated_sql?}

Call execute_metrics_query with the SQL, then briefly summarize what it
returned (status, row count, and any error_message).""",
    tools=[execute_metrics_query],
    output_key="metrics_query_result",
)

kpi_agent = Agent(
    model=MODEL,
    name="kpi_agent",
    description="Calculates KPIs from metrics query results.",
    instruction="""Using triage context {triage_context} and query results {metrics_query_result?},
call calculate_kpi for:
- conversion_rate
- checkout_drop_off_rate

Summarize metrics with specific numbers. Cite the tool outputs.""",
    tools=[calculate_kpi],
    output_key="metrics_findings",
)


def check_sql_result(
    ctx: Context,
    metrics_query_result: dict | None = None,
    sql_loop_iterations: int = 0,
) -> None:
    """Route back to the generator on failure, or forward once succeeded or
    the 3-attempt bound (matching sub_agents.metrics.sql_refinement_loop's
    max_iterations=3) is reached.
    """
    iterations = sql_loop_iterations + 1
    ctx.state["sql_loop_iterations"] = iterations

    succeeded = bool(metrics_query_result) and metrics_query_result.get("status") == "success"
    ctx.route = "done" if (succeeded or iterations >= 3) else "retry"


sql_refinement_workflow = Workflow(
    name="sql_refinement_workflow",
    edges=[
        (
            "START",
            triage_agent,
            sql_generator_agent,
            sql_executor_agent,
            check_sql_result,
        ),
        (check_sql_result, {"retry": sql_generator_agent, "done": kpi_agent}),
    ],
)

root_agent = sql_refinement_workflow

__all__ = ["root_agent"]
