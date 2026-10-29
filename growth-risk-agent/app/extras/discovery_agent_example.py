"""Illustrative only -- NOT wired into app/agent.py, not deployed anywhere,
not part of the demo pipeline.

Shows a different Agent Registry pattern than tools/a2a_auth.py's: instead of
resolving one specific, known-in-advance agent by name (what compliance_agent
does), this agent discovers *any* MCP server registered in Agent Registry at
conversation time and calls it dynamically.

Real, runnable if someone wants to try it:
    adk web app/extras --port 8503
(from inside growth-risk-agent/, with the venv active.)
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.integrations.agent_registry import AgentRegistry
from google.adk.tools import ToolContext

_registry = AgentRegistry(
    project_id=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ.get("AGENT_REGISTRY_LOCATION", "global"),
)


def search_registered_mcp_servers(filter_str: str = "") -> dict:
    """Lists MCP servers registered in Agent Registry.

    Args:
        filter_str: Optional filter expression, e.g. "displayName:remediation".
            Leave empty to list everything registered.
    """
    return _registry.list_mcp_servers(filter_str=filter_str or None)


async def call_discovered_mcp_tool(
    mcp_server_name: str, tool_name: str, tool_args: dict, tool_context: ToolContext
) -> dict:
    """Calls a tool on an MCP server found via search_registered_mcp_servers.

    Args:
        mcp_server_name: Full resource name from the search result
            (e.g. projects/.../locations/.../mcpServers/agentregistry-...).
        tool_name: Name of the tool to call on that server.
        tool_args: Arguments to pass to the tool.
    """
    toolset = _registry.get_mcp_toolset(mcp_server_name)
    for tool in await toolset.get_tools():
        if tool.name == tool_name or tool.name.endswith(f"_{tool_name}"):
            return await tool.run_async(args=tool_args, tool_context=tool_context)
    return {"error": f"Tool {tool_name!r} not found on {mcp_server_name!r}"}


root_agent = Agent(
    model="gemini-3.5-flash",
    name="discovery_agent_example",
    description="Discovers and invokes MCP servers registered in Agent Registry at runtime.",
    instruction="""Help the user find and run tools from Google Cloud Agent Registry.

Use search_registered_mcp_servers to find servers matching what the user
needs, then call_discovered_mcp_tool to invoke a specific tool on whichever
server looks right. Never assume a server or tool exists -- always search
first and use the exact resource name the search returns.""",
    tools=[search_registered_mcp_servers, call_discovered_mcp_tool],
)

__all__ = ["root_agent"]
