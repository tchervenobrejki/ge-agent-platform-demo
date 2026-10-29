"""Persists the final investigation report as a downloadable artifact.

Backed by GcsArtifactService when LOGS_BUCKET_NAME is set
(app_utils/services.py's get_artifact_service -- the scaffold uses one bucket
for telemetry logs and artifacts).
"""

from __future__ import annotations

import logging

from google.genai import types

from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)


async def save_investigation_report(callback_context: CallbackContext) -> None:
    """after_agent_callback on synthesizer_agent.

    Persists the just-produced investigation_summary as a downloadable
    artifact, in addition to it living in session state for
    action_pipeline's later agents to read.
    """
    report = callback_context.state.get("investigation_summary")
    if not report:
        logger.warning("No investigation_summary in state -- skipping artifact save.")
        return

    triage_context = callback_context.state.get("triage_context") or {}
    campaign_id = triage_context.get("campaign_id") or "unknown-campaign"
    incident_date = triage_context.get("incident_date") or "unknown-date"
    filename = f"investigation_report_{campaign_id}_{incident_date}.md"
    artifact = types.Part.from_bytes(data=report.encode("utf-8"), mime_type="text/markdown")

    # An earlier version of this agent hit an upstream pyOpenSSL/urllib3
    # SSL-context-reuse bug here (F6 in docs/design-decisions.md) that made
    # GcsArtifactService's paginated blob-list call fail intermittently. It did
    # not reproduce with the current pinned dependencies, so this retry guard
    # is a safety net, not load-bearing -- don't assume still
    # broken. Retry once; if that also fails, log and move on rather than
    # crash the whole pipeline over a downloadable-report nice-to-have.
    for attempt in (1, 2):
        try:
            version = await callback_context.save_artifact(filename=filename, artifact=artifact)
            logger.info("Saved investigation report artifact %r (version %d)", filename, version)
            return
        except ValueError as e:
            if attempt == 2 or "cannot be mutated again" not in str(e):
                logger.error("Could not save investigation report artifact %r: %s", filename, e)
                return
            logger.warning("Artifact save attempt 1 hit known SSL context bug, retrying once: %s", e)
