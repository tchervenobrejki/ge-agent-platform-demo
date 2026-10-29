"""extract_compliance_result must always leave a decision, failing closed."""

from types import SimpleNamespace

from google.genai import types

from app.tools.a2a_callbacks import extract_compliance_result


def _event(author, *parts):
    return SimpleNamespace(author=author, content=types.Content(role="model", parts=list(parts)))


def _ctx(*events):
    return SimpleNamespace(
        agent_name="compliance_agent",
        session=SimpleNamespace(events=list(events)),
        state={},
    )


def test_uses_final_decision_text() -> None:
    ctx = _ctx(
        _event(
            "compliance_agent",
            types.Part(
                text='{"action_type": "pause_campaign", "campaign_id": "CAMP-2025-042",'
                ' "reason": "r", "compliant": true, "violations": []}'
            ),
        )
    )
    extract_compliance_result(ctx)
    assert ctx.state["compliance_result"]["compliant"] is True
    assert ctx.state["compliance_result"]["action_type"] == "pause_campaign"


def test_rebuilds_from_relayed_tool_events() -> None:
    ctx = _ctx(
        _event(
            "compliance_agent",
            types.Part(
                function_call=types.FunctionCall(
                    name="check_action_compliance",
                    args={
                        "action_type": "approve_discount",
                        "details": {"campaign_id": "CAMP-2025-099", "percentage": 35},
                    },
                )
            ),
        ),
        _event(
            "compliance_agent",
            types.Part(
                function_response=types.FunctionResponse(
                    name="check_action_compliance",
                    response={
                        "compliant": False,
                        "violations": ["Discounts above 20% require VP approval."],
                    },
                )
            ),
        ),
    )
    extract_compliance_result(ctx)
    result = ctx.state["compliance_result"]
    assert result["compliant"] is False
    assert result["action_type"] == "approve_discount"
    assert result["campaign_id"] == "CAMP-2025-099"


def test_fails_closed_without_any_decision() -> None:
    ctx = _ctx(_event("someone_else", types.Part(text="hi")))
    extract_compliance_result(ctx)
    assert ctx.state["compliance_result"]["compliant"] is False
    assert ctx.state["compliance_result"]["violations"]
