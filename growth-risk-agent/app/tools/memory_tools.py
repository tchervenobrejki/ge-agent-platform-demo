"""Memory Bank wiring -- cross-session recall, distinct from Session (single
conversation) and Artifacts (files).

Backed by VertexAiMemoryBankService on Agent Runtime (app_utils/services.py's
get_memory_service, shared by every serving surface). The engine's
contextSpec.memoryBankConfig is provisioned automatically with the
reasoning engine -- no separate service to stand up.
"""

from __future__ import annotations

import logging

from google.genai import types

from google.adk.agents.callback_context import CallbackContext
from google.adk.memory.memory_entry import MemoryEntry

logger = logging.getLogger(__name__)


async def add_investigation_to_memory(callback_context: CallbackContext) -> None:
    """after_agent_callback on root_agent.

    Two writes, for two different reasons (F1 and F28 in
    docs/design-decisions.md):

    1. Automatic extraction (add_events_to_memory over the whole session).
       Only produces a memory when the session contains content Memory
       Bank's extraction model recognizes as "memorable" -- a purely
       technical, tool-call-heavy investigation transcript may produce zero
       memories. Kept as a defense-in-depth catch-all in case a real
       conversation ever states something personal mid-investigation;
       harmless no-op otherwise.

       wait_for_completion=True is required, not optional: the default path
       (add_session_to_memory / memories.ingest_events) fires the real
       network request as a bare asyncio.create_task(...) it never awaits --
       on Agent Runtime, each top-level invocation's event loop closes as
       soon as this callback returns, killing the still-in-flight background
       task before it completes. wait_for_completion=True routes through the
       service's properly-awaited path instead.

    2. An explicit, hand-composed fact via add_memory() -- since automatic
       extraction won't reliably capture "this campaign had this issue" from
       a tool-call-heavy transcript, state it directly so campaign recall
       actually works for synthesizer_agent's preload_memory tool next time.
    """
    session = callback_context.session
    try:
        await callback_context.add_events_to_memory(
            events=session.events,
            custom_metadata={"wait_for_completion": True},
        )
    except ValueError as e:
        logger.warning("Automatic memory extraction failed: %s", e)

    triage_context = callback_context.state.get("triage_context") or {}
    campaign_id = triage_context.get("campaign_id")
    if not campaign_id:
        return

    incident_date = triage_context.get("incident_date") or "an unspecified date"
    issue_type = triage_context.get("issue_type") or "an issue"

    # The root callback runs at the end of every turn, and a HITL approval is
    # a second turn of the same investigation -- write the fact once per
    # session and incident (the first live run stored it twice).
    memory_key = f"{campaign_id}|{incident_date}"
    if callback_context.state.get("memory_fact_saved_for") == memory_key:
        return
    fact_text = f"Campaign {campaign_id} had {issue_type} on {incident_date}."

    compliance_result = callback_context.state.get("compliance_result") or {}
    if compliance_result.get("action_type"):
        fact_text += (
            f" Recommended action: {compliance_result['action_type']}"
            f" ({compliance_result.get('reason', 'no reason given')})."
        )

    try:
        await callback_context.add_memory(
            memories=[MemoryEntry(content=types.Content(parts=[types.Part(text=fact_text)]))]
        )
        callback_context.state["memory_fact_saved_for"] = memory_key
    except (ValueError, NotImplementedError) as e:
        # NotImplementedError: a local in-memory memory service (e.g.
        # `agents-cli playground` without --memory_service_uri) doesn't
        # support direct add_memory() writes -- only VertexAiMemoryBankService
        # (the deployed Agent Runtime) supports this call.
        logger.warning("Could not write explicit investigation memory: %s", e)
