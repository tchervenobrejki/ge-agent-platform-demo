# ruff: noqa
"""Digital Growth & Risk Operations Agent -- root orchestrator.

See ../.agents-cli-spec.md for the spec and ../docs/design-decisions.md for why the
pipeline is built this way.
"""

from __future__ import annotations

import logging
import os

from google.adk.agents import SequentialAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.plugins.bigquery_agent_analytics_plugin import (
    BigQueryAgentAnalyticsPlugin,
    BigQueryLoggerConfig,
)
from google.cloud import bigquery

from .sub_agents.action_pipeline import action_pipeline
from .sub_agents.investigation import parallel_investigation
from .sub_agents.synthesizer import synthesizer_agent
from .sub_agents.triage import triage_agent
from .tools.memory_tools import add_investigation_to_memory

# after_agent_callback=add_investigation_to_memory saves the whole completed
# investigation to Memory Bank once the full pipeline finishes, so a later
# session investigating the same or a related campaign can recall it via
# synthesizer_agent's preload_memory tool.
root_agent = SequentialAgent(
    # Keep in sync with agents-cli-manifest.yaml's root_agent_name: telemetry
    # reports this as gen_ai.agent.name.
    name="growth_risk_orchestrator",
    description=(
        "Digital Growth & Risk Operations Agent — investigates campaign conversion "
        "drops using BigQuery metrics, support/policy search, and governed actions."
    ),
    sub_agents=[
        triage_agent,
        parallel_investigation,
        synthesizer_agent,
        action_pipeline,
    ],
    after_agent_callback=add_investigation_to_memory,
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
                location=os.environ.get("BQ_ANALYTICS_LOCATION", _location),
                config=BigQueryLoggerConfig(
                    gcs_bucket_name=os.environ.get("BQ_ANALYTICS_GCS_BUCKET"),
                    connection_id=os.environ.get("BQ_ANALYTICS_CONNECTION_ID"),
                ),
            )
        )
    except Exception as e:
        logging.warning(f"Failed to initialize BigQuery Analytics: {e}")

# HITL (require_confirmation) needs resumable invocations so approval resumes
# remediation_agent with its tools -- without this, Approve starts a new run
# on the root orchestrator and create_remediation_action_mcp is not found.
app = App(
    name="app",
    root_agent=root_agent,
    plugins=_plugins,
    resumability_config=ResumabilityConfig(is_resumable=True),
)

# Diagnostic control for console Agent Evaluation (docs/evaluation.md):
# the workshop-eval-control engine serves a one-agent app instead.
if os.environ.get("EVAL_CONTROL_AGENT", "").lower() == "true":
    from .eval_control_agent import app, root_agent  # noqa: F811
