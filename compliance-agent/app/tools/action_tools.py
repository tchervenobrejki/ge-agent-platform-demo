"""Governance and action tools (read compliance check + write with HITL).

This exact file also
lives at compliance-agent/app/tools/action_tools.py -- the two scaffolded
projects have no shared package, so ComplianceDecision/RECOGNIZED_ACTIONS/
check_action_compliance are intentionally duplicated. Keep both copies in
sync by hand (F8 in docs/design-decisions.md);
growth-risk-agent/tests/unit/test_action_tools_sync.py fails if they drift.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class ComplianceDecision(BaseModel):
    """A validated compliance decision for a proposed remediation action.

    Shared shape between this project's action_pipeline (compliance_agent,
    a RemoteA2aAgent) and compliance-agent/app/agent.py's standalone A2A
    service -- keep both copies of this class in sync by hand.
    """

    # Any string, not a Literal of the two "happy path" actions: the
    # policy-violation case (e.g. approve_discount above 20%) must be
    # expressible as compliant=false. Unrecognized values are rejected by
    # check_action_compliance (fail-closed), not by this schema.
    action_type: str
    campaign_id: str
    reason: str
    compliant: bool
    violations: list[str] = []


RECOGNIZED_ACTIONS = frozenset({
    "create_discount",
    "approve_discount",
    "increase_budget",
    "pause_campaign",
    "pause_campaign_segment",
    "escalate_checkout_fix",
    "create_remediation_ticket",
})

_REASON_REQUIRED_ACTIONS = frozenset({
    "create_remediation_ticket",
    "pause_campaign_segment",
    "escalate_checkout_fix",
})


def check_action_compliance(action_type: str, details: dict) -> dict[str, Any]:
    """Check whether a proposed action complies with company policy.

    Read-only governance tool. Call before any write/action tool.

    Args:
        action_type: Type of action. Must be one of RECOGNIZED_ACTIONS, e.g.
            'pause_campaign_segment', 'escalate_checkout_fix', 'pause_campaign',
            'create_discount', 'approve_discount', 'increase_budget',
            'create_remediation_ticket'. Any other value is treated as
            non-compliant pending manual review.
        details: Action details including campaign_id, amount, percentage, reason.

    Returns:
        dict with status, compliant (bool), violations (list), and recommendation.
    """
    action = action_type.strip().lower()
    violations: list[str] = []

    amount = float(details.get("amount", 0) or 0)
    pct = float(details.get("percentage", 0) or details.get("discount_pct", 0) or 0)

    if action not in RECOGNIZED_ACTIONS:
        violations.append(
            f"Unrecognized action type '{action_type}' — requires manual review before execution."
        )

    if action in ("create_discount", "approve_discount") and pct > 20:
        violations.append("Discounts above 20% require VP approval per campaign policy.")

    if action == "increase_budget" and pct > 20:
        violations.append("Budget increases above 20% require VP sign-off.")

    if action in ("pause_campaign", "pause_campaign_segment"):
        # Pausing is allowed but requires manager approval at execution time.
        pass

    if action in _REASON_REQUIRED_ACTIONS and not details.get("reason"):
        violations.append("Remediation actions must include a reason.")

    compliant = len(violations) == 0
    return {
        "status": "success",
        "compliant": compliant,
        "action_type": action_type,
        "violations": violations,
        "recommendation": (
            "Proceed with human approval for the write action."
            if compliant
            else "Do NOT execute the action. Explain policy violations to the user."
        ),
    }


def create_remediation_action(
    action: str, campaign_id: str, reason: str, priority: str = "P1"
) -> dict[str, Any]:
    """Create a remediation action ticket for campaign or checkout issues.

    WRITE ACTION — requires human confirmation before execution.
    Use only after compliance check passes and investigation is complete.

    Args:
        action: Action to take, e.g. 'pause_campaign_segment', 'escalate_checkout_fix'.
        campaign_id: Campaign identifier, e.g. 'CAMP-2025-042'.
        reason: Business justification based on investigation evidence.
        priority: Ticket priority P1-P3. Defaults to P1.

    Returns:
        dict with status, ticket_id, action, campaign_id, and message.
    """
    ticket_id = f"REM-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "success",
        "ticket_id": ticket_id,
        "action": action,
        "campaign_id": campaign_id,
        "priority": priority,
        "reason": reason,
        "message": f"Remediation ticket {ticket_id} created for {campaign_id}.",
    }
