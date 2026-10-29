"""Glue between the remote Compliance Agent (A2A) and the local pipeline.

RemoteA2aAgent has no `output_key` -- that's an LlmAgent-only mechanism for
writing the model's answer into session state, and RemoteA2aAgent is a plain
BaseAgent. The remote compliance agent's structured ComplianceDecision JSON
(its own output_schema) comes back as this agent's own final event text
after the A2A round-trip, so pull it out of the session's event history and
write it into state["compliance_result"] by hand -- remediation_agent's
instruction already expects that exact state key.
"""

from __future__ import annotations

import collections
import logging

from google.adk.agents.callback_context import CallbackContext

from .action_tools import ComplianceDecision

logger = logging.getLogger(__name__)

_COMPLIANCE_TOOL = "check_action_compliance"


def extract_compliance_result(callback_context: CallbackContext) -> None:
    """after_agent_callback on the compliance_agent RemoteA2aAgent.

    Always leaves state["compliance_result"] set, so remediation_agent never
    runs against a missing decision. In order of preference:

    1. The remote agent's final ComplianceDecision JSON text.
    2. Rebuilt from the relayed check_action_compliance call + response. In
       the agents-cli 1.10 rebuild's local smoke tests the final text was
       sometimes missing from the session when the remote answered as an A2A
       Task (status updates) rather than a Message; the relayed tool events
       still carry the deterministic policy verdict.
    3. Fail-closed: compliant=False with a violation explaining why. The spec
       requires an explicit compliant=true before any write action.
    """
    agent_name = callback_context.agent_name
    own_events = [
        e for e in callback_context.session.events if e.author == agent_name
    ]

    for event in reversed(own_events):
        if not event.content or not event.content.parts:
            continue
        text = "".join(part.text or "" for part in event.content.parts)
        if not text.strip():
            continue
        try:
            decision = ComplianceDecision.model_validate_json(text)
        except ValueError:
            logger.warning(
                "compliance_agent text did not match ComplianceDecision: %r", text
            )
            continue
        callback_context.state["compliance_result"] = decision.model_dump()
        return

    decision = _decision_from_tool_events(own_events)
    if decision is not None:
        logger.warning(
            "compliance_agent returned no final decision text; rebuilt it from"
            " the relayed %s events.",
            _COMPLIANCE_TOOL,
        )
        callback_context.state["compliance_result"] = decision.model_dump()
        return

    kinds = collections.Counter(
        _part_kind(part)
        for e in own_events
        for part in (e.content.parts if e.content and e.content.parts else [])
    )
    logger.error(
        "No compliance decision found from %s (%d events, parts: %s);"
        " blocking the write action (fail-closed).",
        agent_name,
        len(own_events),
        dict(kinds),
    )
    callback_context.state["compliance_result"] = ComplianceDecision(
        action_type="unknown",
        campaign_id="unknown",
        reason="No decision was returned by the Compliance Agent.",
        compliant=False,
        violations=[
            "Compliance check returned no decision — write action blocked"
            " (fail-closed). Retry the request."
        ],
    ).model_dump()


def _decision_from_tool_events(events) -> ComplianceDecision | None:
    """Rebuild a ComplianceDecision from the last check_action_compliance pair."""
    call_args = None
    response = None
    for event in events:
        for part in event.content.parts if event.content and event.content.parts else []:
            if part.function_call and part.function_call.name == _COMPLIANCE_TOOL:
                call_args = dict(part.function_call.args or {})
            if part.function_response and part.function_response.name == _COMPLIANCE_TOOL:
                response = dict(part.function_response.response or {})
    if not call_args or not response or "compliant" not in response:
        return None
    details = call_args.get("details") or {}
    return ComplianceDecision(
        action_type=str(call_args.get("action_type") or response.get("action_type") or "unknown"),
        campaign_id=str(details.get("campaign_id") or "unknown"),
        reason=str(details.get("reason") or ""),
        compliant=bool(response["compliant"]),
        violations=list(response.get("violations") or []),
    )


def _part_kind(part) -> str:
    if part.text:
        return "text"
    if part.function_call:
        return f"function_call:{part.function_call.name}"
    if part.function_response:
        return f"function_response:{part.function_response.name}"
    return "other"
