"""Google-signed ID-token auth for calling the remote MCP server on Cloud Run.

remediation-mcp-server
requires roles/run.invoker -- Cloud Run's front-end proxy rejects any request
whose bearer token isn't a Google-signed ID token with an audience matching
the service URL.

mcp_http_client_factory_for also disables ADK's internal MCP mTLS
auto-configuration (see its docstring) -- that path silently overrides any
custom httpx_client_factory, including this one, whenever it successfully
configures, sending an ambient cloud-platform-scoped access token instead of
the audience-scoped ID token Cloud Run requires. The symptom is 401s and
MALFORMED_FUNCTION_CALL (the tools never load); see F4 and F12 in
docs/design-decisions.md. It is ADK library behavior, so the fix is needed
however the agent is deployed.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import httpx
from google.auth import default as google_auth_default
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request

_CALLER_SERVICE_ACCOUNT = os.environ.get("MCP_CALLER_SERVICE_ACCOUNT")
_TOKEN_REFRESH_MARGIN_SECONDS = 60


class _IdTokenMinter:
    """Mints and caches a Google-signed ID token for one audience."""

    def __init__(self, audience: str):
        self._audience = audience
        self._token: str | None = None
        self._expiry_epoch = 0.0

    def get_token(self) -> str:
        if self._token is None or time.time() > self._expiry_epoch - _TOKEN_REFRESH_MARGIN_SECONDS:
            self._token, self._expiry_epoch = self._fetch_token()
        return self._token

    def _fetch_token(self) -> tuple[str, float]:
        request = Request()
        source_credentials, _ = google_auth_default()
        if _CALLER_SERVICE_ACCOUNT:
            target_credentials = impersonated_credentials.IDTokenCredentials(
                impersonated_credentials.Credentials(
                    source_credentials=source_credentials,
                    target_principal=_CALLER_SERVICE_ACCOUNT,
                    target_scopes=[],
                ),
                target_audience=self._audience,
                include_email=True,
            )
        else:
            # No caller SA configured: the runtime's own identity mints the
            # ID token directly. Requires google.auth's ID-token-capable
            # credentials (available when running as a real attached SA
            # identity on GCP compute).
            from google.auth import compute_engine

            target_credentials = compute_engine.IDTokenCredentials(
                request, target_audience=self._audience, use_metadata_identity_endpoint=True
            )
        target_credentials.refresh(request)
        return target_credentials.token, target_credentials.expiry.timestamp()


class GoogleIdTokenAuth(httpx.Auth):
    """httpx.Auth that attaches a fresh Google-signed ID token per request.

    For httpx (1.x) clients -- the A2A client in a2a_auth.py.
    """

    def __init__(self, audience: str):
        self._minter = _IdTokenMinter(audience)

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._minter.get_token()}"
        yield request


def _mcp_id_token_auth(audience: str):
    """Same ID-token auth, typed for whichever httpx the MCP SDK uses.

    MCP SDK 2.x builds its clients on the separate `httpx2` package and
    rejects an httpx (1.x) Auth with 'Invalid "auth" argument' -- the MCP
    toolset then fails to load and remediation_agent's model emits a
    MALFORMED_FUNCTION_CALL for the tool it can no longer see.
    """
    from google.adk.dependencies._mcp import IS_MCP_SDK_V2

    if not IS_MCP_SDK_V2:
        return GoogleIdTokenAuth(audience)

    import httpx2

    minter = _IdTokenMinter(audience)

    class _Httpx2GoogleIdTokenAuth(httpx2.Auth):
        def auth_flow(self, request: httpx2.Request):
            request.headers["Authorization"] = f"Bearer {minter.get_token()}"
            yield request

    return _Httpx2GoogleIdTokenAuth()


def mcp_http_client_factory_for(url: str):
    """Build an MCPToolset httpx_client_factory that authenticates to `url`.

    Returns the vanilla client factory unmodified for localhost URLs -- no
    auth needed for local dev against a locally-run MCP server.

    For any other URL, also disables ADK's own MCP mTLS auto-configuration
    (google.adk.tools.mcp_tool.mcp_session_manager._get_mtls_transport),
    which -- whenever it successfully configures -- replaces whatever
    httpx_client_factory is passed here with its own, sending an ambient
    cloud-platform-scoped access token instead of the audience-scoped ID
    token Cloud Run's roles/run.invoker requires.
    """
    from google.adk.tools.mcp_tool import mcp_session_manager
    from google.adk.tools.mcp_tool.mcp_session_manager import create_mcp_http_client

    host = urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1"):
        return create_mcp_http_client

    mcp_session_manager._AIO_SUPPORTED = False

    parsed = urlparse(url)
    id_token_auth = _mcp_id_token_auth(f"{parsed.scheme}://{parsed.netloc}")

    def factory(headers=None, timeout=None, auth=None):
        return create_mcp_http_client(headers=headers, timeout=timeout, auth=auth or id_token_auth)

    return factory
