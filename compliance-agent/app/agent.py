# ruff: noqa
"""Standalone Compliance Agent, served over A2A by this scaffold's own
app_utils/a2a.py (see fast_api_app.py's lifespan).
"""

from __future__ import annotations

import logging
import os

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin,
    BigQueryLoggerConfig,
)
from google.cloud import bigquery

from .tools.action_tools import ComplianceDecision, check_action_compliance

MODEL = "gemini-3.5-flash"

root_agent = Agent(
    model=MODEL,
    # Keep in sync with agents-cli-manifest.yaml's root_agent_name: telemetry
    # reports this as gen_ai.agent.name.
    name="compliance_agent",
    description="Runs policy compliance checks for proposed remediation actions.",
    instruction="""A remote caller will describe a proposed remediation action.

Check exactly ONE action. If the request contains a line "Primary recommended
action: ...", that is the action to check — ignore other follow-ups listed for
humans. Past changes mentioned as evidence (e.g. "the budget was raised from
€5,000 to €7,000") are context, not proposals: never check them.

Determine action_type, campaign_id, and reason from the request. action_type is
usually one of 'pause_campaign_segment', 'escalate_checkout_fix',
'pause_campaign', 'create_discount', 'approve_discount', 'increase_budget' or
'create_remediation_ticket'; if the request asks for something else, use the
caller's own wording — the tool treats unrecognized actions as non-compliant.

Call check_action_compliance with that action_type and a details object holding
campaign_id, reason, and any amount or percentage the request mentions (e.g. a
35% discount → percentage 35) before reporting your decision. Report the same
action_type, campaign_id, and reason you checked, plus the tool's compliant
flag and violations list — do not soften or reinterpret the tool's verdict.""",
    tools=[check_action_compliance],
    output_schema=ComplianceDecision,
    output_key="compliance_result",
)

# Initialize BigQuery Analytics (scaffold-generated, --bq-analytics)
_plugins = []
_project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
_dataset_id = os.environ.get("BQ_ANALYTICS_DATASET_ID")
_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west3")

# Only when Terraform provided the telemetry dataset (deployed agents). The
# scaffold default fell back to creating an "adk_agent_analytics" dataset in
# the US for local runs, and its write retries slowed local A2A calls past the
# client timeout.
if _project_id and _dataset_id:
    try:
        bq = bigquery.Client(project=_project_id)
        bq.create_dataset(f"{_project_id}.{_dataset_id}", exists_ok=True)

        _plugins.append(
            BigQueryAgentAnalyticsPlugin(
                project_id=_project_id,
                dataset_id=_dataset_id,
                location=_location,
                config=BigQueryLoggerConfig(
                    gcs_bucket_name=os.environ.get("BQ_ANALYTICS_GCS_BUCKET"),
                    connection_id=os.environ.get("BQ_ANALYTICS_CONNECTION_ID"),
                ),
            )
        )
    except Exception as e:
        logging.warning(f"Failed to initialize BigQuery Analytics: {e}")

app = App(
    root_agent=root_agent,
    name="app",
    plugins=_plugins,
)
