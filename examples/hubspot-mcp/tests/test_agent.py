"""Offline tests: the read-only policy, and that the agent asks for sign-in first.

    uv run pytest

No HubSpot account, network or Gemini call needed: the secret is a dummy and
the sign-in request is built before any tool is listed or model called.
"""

import json
import os
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

os.environ.setdefault("HUBSPOT_CLIENT_ID", "test-client-id")
os.environ.setdefault("HUBSPOT_CLIENT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from hubspot_agent import agent  # noqa: E402


def tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def test_only_read_tools_are_loaded():
    assert agent.read_only_filter(tool("search_crm_objects"))
    assert not agent.read_only_filter(tool("manage_crm_objects"))
    assert not agent.read_only_filter(tool("query_crm_data"))


def test_disallowed_object_type_is_blocked():
    result = agent.guard_hubspot_call(tool("search_crm_objects"), {"objectType": "INVOICE"}, None)
    assert "not allowed" in result["error"]


def test_default_fields_are_replaced_by_the_allow_list():
    args = {"objectType": "deals"}
    assert agent.guard_hubspot_call(tool("search_crm_objects"), args, None) is None
    assert "amount" not in args["properties"]
    assert set(args["properties"]) == agent.ALLOWED_PROPERTIES["DEAL"]


def test_disallowed_field_in_a_filter_is_blocked():
    args = {
        "objectType": "DEAL",
        "properties": ["dealname"],
        "filterGroups": [{"filters": [{"propertyName": "amount", "operator": "GT", "value": "0"}]}],
    }
    assert "amount" in agent.guard_hubspot_call(tool("search_crm_objects"), args, None)["error"]


def test_chat_insights_are_neutralised():
    args = {"chatInsights": {"userIntent": "the user's exact question"}}
    agent.guard_hubspot_call(tool("get_user_details"), args, None)
    assert args["chatInsights"] == agent.NEUTRAL_CHAT_INSIGHTS


def test_response_keeps_only_allowed_fields():
    record = {"results": [{"id": "1", "properties": {"dealname": "Renewal", "amount": "50000"}}]}
    response = {"content": [{"type": "text", "text": json.dumps(record)}], "structuredContent": record}
    filtered = agent.filter_hubspot_response(tool("search_crm_objects"), {}, None, response)
    properties = json.loads(filtered["content"][0]["text"])["results"][0]["properties"]
    assert properties == {"dealname": "Renewal"}
    assert "structuredContent" not in filtered


def test_unparseable_record_response_fails_closed():
    response = {"content": [{"type": "text", "text": "not json"}]}
    assert "error" in agent.filter_hubspot_response(tool("get_crm_objects"), {}, None, response)


@pytest.mark.asyncio
async def test_first_step_is_a_hubspot_sign_in_request_with_pkce():
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=agent.root_agent, app_name="hubspot_agent")
    session = await runner.session_service.create_session(app_name="hubspot_agent", user_id="u")
    message = types.Content(role="user", parts=[types.Part(text="Which companies do I own?")])
    requests = []
    async for event in runner.run_async(user_id="u", session_id=session.id, new_message=message):
        requests += [c for c in event.get_function_calls() if c.name == "adk_request_credential"]
    assert len(requests) == 1
    auth_uri = requests[0].args["authConfig"]["exchangedAuthCredential"]["oauth2"]["authUri"]
    url = urlparse(auth_uri)
    query = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == agent.AUTHORIZATION_URL
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == [agent.REDIRECT_URI]
    assert query["code_challenge_method"] == ["S256"] and query["code_challenge"]
