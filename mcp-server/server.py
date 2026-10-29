"""Remote MCP server exposing the remediation-ticketing capability.

The `remediation-mcp-server` Cloud Run service the growth-risk-agent calls.
setup/04_mcp_server.sh deploys it.

It speaks MCP over streamable HTTP rather than local stdio, so it is a real
network service: deployable to Cloud Run (private, `roles/run.invoker` only),
reachable through Agent Gateway, and listable in Agent Registry.

Local:      uv run --with "mcp>=1.24,<2" python server.py   # :8080/mcp
Cloud Run:  gcloud run deploy <name> --source . --no-allow-unauthenticated
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="remediation-ticketing",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),  # Cloud Run injects $PORT
)


@mcp.tool()
def create_remediation_action_mcp(
    action: str, campaign_id: str, reason: str, priority: str = "P1"
) -> dict[str, Any]:
    """Create a remediation action ticket for campaign or checkout issues.

    WRITE ACTION. Use only after compliance has passed and the investigation
    is complete.

    Args:
        action: Action to take, e.g. 'pause_campaign_segment', 'escalate_checkout_fix'.
        campaign_id: Campaign identifier, e.g. 'CAMP-2025-042'.
        reason: Business justification based on investigation evidence.
        priority: Ticket priority P1-P3. Defaults to P1.
    """
    # A demo "ticketing system": the point is the protocol, not the backend.
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
