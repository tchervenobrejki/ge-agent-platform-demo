"""Guards the duplicated governance schema shared with compliance-agent.

app/tools/action_tools.py (ComplianceDecision, RECOGNIZED_ACTIONS,
check_action_compliance) exists verbatim in both independently-scaffolded
projects. The orchestrator parses the Compliance Agent's A2A response with its
own copy of ComplianceDecision, so a drift between the two silently breaks the
compliance gate.
"""

from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_LOCAL = _HERE.parents[2] / "app" / "tools" / "action_tools.py"
_SIBLING = _HERE.parents[3] / "compliance-agent" / "app" / "tools" / "action_tools.py"


@pytest.mark.skipif(not _SIBLING.exists(), reason="compliance-agent not checked out alongside")
def test_action_tools_identical_to_compliance_agent() -> None:
    assert _LOCAL.read_text() == _SIBLING.read_text(), (
        f"{_LOCAL} and {_SIBLING} have drifted; copy the change to both."
    )


def test_policy_violation_is_expressible() -> None:
    """Spec use case 3: a >20% discount must come back as compliant=False."""
    from app.tools.action_tools import ComplianceDecision, check_action_compliance

    result = check_action_compliance(
        "approve_discount", {"campaign_id": "CAMP-2025-099", "percentage": 35}
    )
    assert result["compliant"] is False
    decision = ComplianceDecision(
        action_type=result["action_type"],
        campaign_id="CAMP-2025-099",
        reason="boost conversions",
        compliant=result["compliant"],
        violations=result["violations"],
    )
    assert decision.violations


def test_unrecognized_action_fails_closed() -> None:
    from app.tools.action_tools import check_action_compliance

    assert check_action_compliance("delete_campaign", {})["compliant"] is False
