"""Phase 2a -- Metrics branch with SQL Loop (generate -> execute -> retry)."""

from __future__ import annotations

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.tools import exit_loop

from ..tools.bigquery_tools import (
    DATASET,
    PROJECT_ID,
    calculate_kpi,
    execute_metrics_query,
)

MODEL = "gemini-3.5-flash"

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

sql_executor_agent = Agent(
    model=MODEL,
    name="sql_executor_agent",
    description="Executes generated SQL and exits loop on success.",
    instruction="""Execute the SQL investigation using the execute_metrics_query tool.

Generated SQL to run:
{generated_sql?}

Steps:
1. Call execute_metrics_query with the SQL.
2. If status is 'success', summarize findings briefly, then call exit_loop.
3. If status is 'error', return the error_message so the generator can fix the query.
Do NOT call exit_loop on error.""",
    tools=[execute_metrics_query, exit_loop],
    output_key="metrics_query_result",
)

sql_refinement_loop = LoopAgent(
    name="sql_refinement_loop",
    description="Bounded retry loop for SQL generation and execution.",
    sub_agents=[sql_generator_agent, sql_executor_agent],
    max_iterations=3,
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

metrics_branch = SequentialAgent(
    name="metrics_branch",
    description="Metrics investigation: SQL loop then KPI calculation.",
    sub_agents=[sql_refinement_loop, kpi_agent],
)
