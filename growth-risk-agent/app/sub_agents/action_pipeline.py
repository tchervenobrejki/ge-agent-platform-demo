"""Phase 4 -- Governance + action (compliance check -> HITL write).

compliance_agent runs as its own, independently deployed Agent2Agent (A2A)
service (../../compliance-agent/, on Cloud Run) rather than a local
sub-agent: the rules an action is judged by are governed and deployed
separately from the agent that proposes it. The scaffold's A2A support
(app_utils/a2a.py) gives compliance-agent a real A2A endpoint and agent card.
"""

from __future__ import annotations

import os

from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ..tools.a2a_auth import (
    COMPLIANCE_AGENT_CARD,
    CompactRemoteA2aAgent,
    investigation_summary_context,
)
from ..tools.a2a_callbacks import extract_compliance_result
from ..tools.callbacks import (
    block_unrecognized_remediation_action,
    gate_actions,
)
from ..tools.gcp_auth import mcp_http_client_factory_for

MODEL = "gemini-3.5-flash"

# Remote MCP server: the remediation-mcp-server Cloud Run service that
# setup/04_mcp_server.sh deploys from ../../mcp-server/. The localhost default
# is for a locally run copy of mcp-server/server.py; REMEDIATION_MCP_URL in
# .env points at the deployed URL otherwise.
_MCP_SERVER_URL = os.environ.get("REMEDIATION_MCP_URL", "http://localhost:8080/mcp")

# RemoteA2aAgent has no instruction/output_schema/output_key of its own --
# investigation_summary_context (../tools/a2a_auth.py) sends just
# investigation_summary to the remote agent as its A2A message, instead of the
# plain RemoteA2aAgent default of the full preceding conversation.
# extract_compliance_result (after_agent_callback) then pulls the remote
# agent's structured JSON response back out into state["compliance_result"] by
# hand, since remediation_agent's instruction expects that exact state key.
compliance_agent = CompactRemoteA2aAgent(
    name="compliance_agent",
    description="Runs policy compliance check before any write action (standalone A2A service).",
    agent_card=COMPLIANCE_AGENT_CARD,
    context_builder=investigation_summary_context,
    after_agent_callback=extract_compliance_result,
)

remediation_agent = Agent(
    model=MODEL,
    name="remediation_agent",
    description="Creates remediation tickets (write action, requires human approval).",
    instruction="""compliance_result: {compliance_result}
investigation_summary: {investigation_summary?}

If compliance_result.compliant is true:
1. ALWAYS first write a short summary for the human approver — never call the
   tool without it:
   - After an investigation (investigation_summary is present), use the
     headings **Root cause** (one or two sentences, internal evidence only —
     never an external outage or provider incident), **Evidence** (2-4
     bullets, each with its source: BigQuery, a support ticket or runbook, or
     a policy document — internal evidence only; leave live-search signals to
     the investigation report) and **Proposed action** (action, campaign,
     reason; found compliant by the Compliance Agent). Use only facts stated
     in investigation_summary.
   - For a direct request (no investigation_summary), use the headings
     **Requested action** (what the user asked for: action, campaign, their
     stated reason) and **Compliance** (found compliant by the Compliance
     Agent, no violations). Do not add causes or evidence the user didn't
     give.
   End by saying the action will only run after their approval.
2. Then call create_remediation_action_mcp, passing
   compliance_result.action_type as its action argument, and
   compliance_result.campaign_id / compliance_result.reason as its
   campaign_id / reason arguments — do not re-derive these from the
   investigation, the compliance check already validated them.
3. When the tool returns (after the human approves or rejects), always tell
   the user the outcome in one or two sentences: on approval, that the action
   was created, with any ticket or action ID the tool returned; on rejection,
   that nothing was created.

If compliance_result.compliant is false, do NOT call create_remediation_action_mcp.
Instead tell the user the requested action is blocked by policy, name the
action and campaign, list every item in compliance_result.violations, and say
what would be needed to proceed (e.g. the approval the violation names).""",
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=_MCP_SERVER_URL,
                timeout=30,
                httpx_client_factory=mcp_http_client_factory_for(_MCP_SERVER_URL),
            ),
            require_confirmation=True,
        ),
    ],
    before_tool_callback=block_unrecognized_remediation_action,
    output_key="action_result",
)

action_pipeline = SequentialAgent(
    name="action_pipeline",
    description="Compliance gate then governed write action with HITL.",
    sub_agents=[compliance_agent, remediation_agent],
    before_agent_callback=gate_actions,
)
