"""A read-only HubSpot CRM agent, through HubSpot's remote MCP server.

The agent acts as the signed-in HubSpot user (OAuth 2.1 authorization code
with PKCE), not as a service account: it sees exactly what that user may see.

Three layers keep it read-only and least-privilege, because HubSpot's MCP
server also offers write tools and grants whatever the user's role allows:

  1. ``tool_filter``           which tools the model gets at all
  2. ``before_tool_callback``  which arguments a call may use
  3. ``after_tool_callback``   which fields the model gets back

The same pattern fits any OAuth-protected remote MCP server; see README.md.
"""

from __future__ import annotations

import functools
import json
import logging
import os
from typing import Any

from fastapi.openapi.models import OAuth2, OAuthFlowAuthorizationCode, OAuthFlows
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)

# --- Connection and sign-in (written to .env by notebooks/10_hubspot_mcp.ipynb) ---

# https://mcp.hubspot.com, or https://mcp-eu1.hubspot.com for EU-hosted accounts.
HUBSPOT_MCP_URL = os.environ.get("HUBSPOT_MCP_URL", "https://mcp.hubspot.com")
# The MCP auth app's client ID: shown on its details page, not a secret.
CLIENT_ID = os.environ.get("HUBSPOT_CLIENT_ID", "")
CLIENT_SECRET_NAME = os.environ.get("HUBSPOT_CLIENT_SECRET_NAME", "hubspot-mcp-client-secret")
# Must be one of the MCP auth app's redirect URLs. adk web handles this one.
REDIRECT_URI = os.environ.get("HUBSPOT_REDIRECT_URI", "http://localhost:8000/dev-ui/")
# From the server's /.well-known/oauth-authorization-server metadata.
AUTHORIZATION_URL = os.environ.get("HUBSPOT_AUTHORIZATION_URL", "https://mcp.hubspot.com/oauth/authorize/user")
TOKEN_URL = os.environ.get("HUBSPOT_TOKEN_URL", "https://mcp.hubspot.com/oauth/v3/token")

# --- Policy ---

# 1. Tools: an allow-list, so tools HubSpot adds later stay off until reviewed.
#    Every write tool (manage_*, ...) is left out, and so is query_crm_data:
#    its free-form SQL would need its own checks.
READ_ONLY_TOOLS = ["get_user_details", "search_crm_objects", "get_crm_objects", "search_owners"]

# 2. Arguments: the object types and fields the agent may read, in HubSpot's
#    MCP naming. Fields are allow-listed, not block-listed: a custom field can
#    hold anything, and deal amounts are left out on purpose.
ALLOWED_PROPERTIES = {
    "COMPANY": {"name", "domain", "industry", "country", "city", "numberofemployees", "description"},
    "CONTACT": {"firstname", "lastname", "jobtitle", "company"},
    "DEAL": {"dealname", "dealstage", "pipeline", "closedate", "description"},
    "NOTE": {"hs_note_body", "hs_timestamp"},
}
COMMON_PROPERTIES = {"hs_object_id", "createdate", "hs_lastmodifieddate"}
_ALIASES = {"companies": "COMPANY", "contacts": "CONTACT", "deals": "DEAL", "notes": "NOTE"}
_OBJECT_TOOLS = {"search_crm_objects", "get_crm_objects"}
# HubSpot's tools ask the model to describe the user's request on every call;
# send a fixed value instead.
NEUTRAL_CHAT_INSIGHTS = {"userIntent": "Not shared", "satisfaction": "NEUTRAL"}


def read_only_filter(tool: BaseTool, readonly_context: ReadonlyContext | None = None) -> bool:
    """Layer 1: load only allow-listed tools; log the rest, so new ones show up."""
    if tool.name in READ_ONLY_TOOLS:
        return True
    logger.info("HubSpot MCP tool not loaded: %s", tool.name)
    return False


def _object_type(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    canonical = _ALIASES.get(name.lower(), name.upper())  # "companies", "company", "COMPANY"
    return canonical if canonical in ALLOWED_PROPERTIES else None


def _property_names(value: Any) -> list[str]:
    """Every ``propertyName`` in filters and sorts, however deeply nested."""
    if isinstance(value, dict):
        own = [value["propertyName"]] if "propertyName" in value else []
        return own + [n for v in value.values() for n in _property_names(v)]
    if isinstance(value, list):
        return [n for v in value for n in _property_names(v)]
    return []


def _blocked(reason: str) -> dict:
    logger.warning("HubSpot call blocked: %s", reason)
    return {"error": f"Blocked by the agent's read-only policy: {reason}"}


def guard_hubspot_call(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """Layer 2 (``before_tool_callback``): allowed object types and fields only.

    Returning a dict skips the call and gives the model that result instead.
    """
    if tool.name not in READ_ONLY_TOOLS:
        return None
    if "chatInsights" in args:
        args["chatInsights"] = dict(NEUTRAL_CHAT_INSIGHTS)
    if tool.name not in _OBJECT_TOOLS:
        return None
    object_type = _object_type(args.get("objectType"))
    if object_type is None:
        return _blocked(f"object type {args.get('objectType')!r} is not allowed")
    allowed = COMMON_PROPERTIES | ALLOWED_PROPERTIES[object_type]
    requested = args.get("properties")
    if not requested:
        # Without a list, HubSpot returns its default fields (a deal's amount).
        args["properties"] = sorted(ALLOWED_PROPERTIES[object_type])
    elif not isinstance(requested, list) or not set(map(str, requested)) <= allowed:
        return _blocked(f"fields {requested!r} are not all allowed")
    for name in _property_names(args.get("filterGroups")) + _property_names(args.get("sorts")):
        if name not in allowed:
            return _blocked(f"field {name!r} is not allowed")
    return None


_ANY_ALLOWED = COMMON_PROPERTIES.union(*ALLOWED_PROPERTIES.values())


def _filter_records(value: Any) -> Any:
    """Drop every field that isn't allow-listed from the records in a response."""
    if isinstance(value, dict):
        return {
            key: {k: v for k, v in item.items() if k in _ANY_ALLOWED}
            if key == "properties" and isinstance(item, dict)
            else _filter_records(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_filter_records(item) for item in value]
    return value


def filter_hubspot_response(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> dict | None:
    """Layer 3 (``after_tool_callback``): the model only sees allow-listed fields.

    Covers fields HubSpot adds on its own. Fails closed: a record response that
    can't be parsed is replaced by an error.
    """
    if tool.name not in _OBJECT_TOOLS or not isinstance(tool_response, dict):
        return None
    filtered = dict(tool_response)
    filtered.pop("structuredContent", None)  # a second, unfiltered copy of the same data
    content = []
    for item in tool_response.get("content") or []:
        if not (isinstance(item, dict) and item.get("type") == "text"):
            continue
        try:
            data = json.loads(item.get("text", ""))
        except (TypeError, ValueError):
            if tool_response.get("isError"):
                content.append(item)  # HubSpot's own error message, no records
                continue
            return _blocked("the response could not be checked")
        content.append({**item, "text": json.dumps(_filter_records(data), ensure_ascii=False)})
    filtered["content"] = content
    return filtered


# --- Sign-in ---


@functools.cache
def client_secret() -> str:
    """``HUBSPOT_CLIENT_SECRET`` if set (a deployed agent can get it injected from
    Secret Manager that way), otherwise read from Secret Manager with your login."""
    if secret := os.environ.get("HUBSPOT_CLIENT_SECRET"):
        return secret
    from google.cloud import secretmanager

    name = f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/secrets/{CLIENT_SECRET_NAME}/versions/latest"
    return secretmanager.SecretManagerServiceClient().access_secret_version(name=name).payload.data.decode()


def hubspot_toolset() -> McpToolset:
    """HubSpot's MCP tools, signed in as the user.

    With ``auth_scheme`` set, ADK asks the user to sign in before it lists the
    tools (HubSpot answers 401 without a token), exchanges the code for a token
    and sends it as a Bearer header on every MCP request.
    """
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=HUBSPOT_MCP_URL),
        tool_filter=read_only_filter,
        auth_scheme=OAuth2(
            flows=OAuthFlows(
                authorizationCode=OAuthFlowAuthorizationCode(
                    authorizationUrl=AUTHORIZATION_URL,
                    tokenUrl=TOKEN_URL,
                    scopes={},  # MCP auth apps have no scopes: HubSpot derives them
                )
            )
        ),
        auth_credential=AuthCredential(
            auth_type=AuthCredentialTypes.OAUTH2,
            oauth2=OAuth2Auth(
                client_id=CLIENT_ID,
                client_secret=client_secret(),
                redirect_uri=REDIRECT_URI,
                code_challenge_method="S256",  # PKCE, required by HubSpot
                token_endpoint_auth_method="client_secret_post",  # the only method HubSpot accepts
            ),
        ),
        credential_key="hubspot",
    )


root_agent = LlmAgent(
    name="hubspot_reader",
    model=os.environ.get("MODEL", "gemini-3.5-flash"),
    description="Answers questions about the signed-in user's HubSpot CRM, read-only.",
    instruction="""
You answer questions about the user's HubSpot CRM: companies, contacts, deals and notes.
You can only read. If asked to create, change or delete anything, say that you are read-only.
Use only what the tools return; if a search finds nothing, say so instead of guessing.
If a tool says a call was blocked by the policy, tell the user which object or field isn't available.
""",
    tools=[hubspot_toolset()],
    before_tool_callback=guard_hubspot_call,
    after_tool_callback=filter_hubspot_response,
)
