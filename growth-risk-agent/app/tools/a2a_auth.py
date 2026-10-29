"""Auth + connection for calling the standalone Compliance Agent's A2A server
on Cloud Run (compliance-agent/) -- RemoteA2aAgent's counterpart to
gcp_auth.py's MCP-calling helper.

The Compliance Agent's URL is read from a plain COMPLIANCE_AGENT_URL env var
(Cloud Run URLs are deterministic given service name + project number +
region) rather than resolved dynamically from Agent Registry. The Compliance
Agent is registered in Agent Registry as A2A, so a registry lookup would work,
but it adds a runtime dependency for no benefit here (docs/design-decisions.md).

Same underlying auth mechanism as gcp_auth.py: Cloud Run's roles/run.invoker
check requires a Google-signed ID token whose audience matches the service
URL -- GoogleIdTokenAuth (gcp_auth.py) mints one via MCP_CALLER_SERVICE_ACCOUNT
impersonation.
"""

from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.events.event import Event
from google.genai import types as genai_types

from .gcp_auth import GoogleIdTokenAuth

_COMPLIANCE_AGENT_URL = os.environ.get(
    "COMPLIANCE_AGENT_URL", "http://localhost:8000/a2a/app"
)
_COMPLIANCE_AGENT_CARD_URL = f"{_COMPLIANCE_AGENT_URL}/.well-known/agent-card.json"


def _build_compliance_agent_httpx_client():
    import httpx
    from urllib.parse import urlparse

    parsed = urlparse(_COMPLIANCE_AGENT_URL)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    return httpx.AsyncClient(
        auth=GoogleIdTokenAuth(audience=audience),
        timeout=httpx.Timeout(60.0),
    )


def investigation_summary_context(
    ctx: InvocationContext, agent_name: str, part_converter: Any
) -> tuple[list[Any], Optional[str]]:
    """RemoteA2aAgent context_builder: send only what needs checking.

    The user's directly requested action if triage found one, otherwise
    investigation_summary.

    Replaces the default of the full preceding session transcript, which
    grows with every sub-agent's output and risks Cloud Run's 300s request
    ceiling. ADK 2.11 exposes this as the public
    context_builder parameter; the 1.0 port overrode the private
    _construct_message_parts_from_session instead.
    """
    requested = (ctx.session.state.get("triage_context") or {}).get("requested_action")
    if requested:
        # Spec use case 3: the user asked for this exact action; check it, not
        # a recommendation from an investigation that was skipped.
        details = ", ".join(
            f"{k}: {v}" for k, v in requested.items() if v is not None and k != "action_type"
        )
        text = (
            f"The user directly requested this action: {requested['action_type']}"
            f" ({details}). Check exactly this action."
        )
    else:
        text = ctx.session.state.get("investigation_summary", "")
    converted = part_converter(genai_types.Part(text=text))
    if not isinstance(converted, list):
        converted = [converted] if converted else []
    return converted, None


class CompactRemoteA2aAgent(RemoteA2aAgent):
    """RemoteA2aAgent that rebuilds its authenticated httpx client fresh on
    every top-level invocation instead of reusing one across the agent's
    whole lifetime.

    A client cached on the agent
    instance can end up bound to a closed event loop on Agent Runtime
    (google/adk-python#2428). ADK 2.11's RemoteA2aAgent still caches its
    httpx client and A2A client on the instance, so the reset is kept.
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        self._httpx_client = _build_compliance_agent_httpx_client()
        self._httpx_client_needs_cleanup = True
        self._a2a_client = None
        self._a2a_client_factory = None
        self._is_resolved = False
        async for event in super()._run_async_impl(ctx):
            yield event


COMPLIANCE_AGENT_CARD = _COMPLIANCE_AGENT_CARD_URL
