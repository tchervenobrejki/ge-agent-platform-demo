"""Add agent and tool definitions to eval traces before grading.

`agents-cli eval generate` fills agent_data.agents from ADK's /app-info, which
only supports an LlmAgent root (400 "Root agent is not an LlmAgent" for our
SequentialAgent pipeline). Without it, multi_turn_tool_use_quality grades every
tool call against empty tool definitions and fails it. This walks the whole
agent tree -- workflow agents, the remote A2A agent and the MCP toolset
included -- and writes the same AgentConfig shape the generator would have.

Usage (from the project root, after `agents-cli eval generate`):
    uv run python tests/eval/enrich_traces.py artifacts/traces/traces_<ts>.json
then grade with `agents-cli eval grade --traces <that file>`.
"""

from __future__ import annotations

import asyncio
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.utils.agent_info import get_tools_info  # noqa: E402

from app.agent import root_agent  # noqa: E402
from app.tools.action_tools import check_action_compliance  # noqa: E402

# Tools the remote A2A agents run on their side; their calls are relayed into
# our trace under the remote agent's name. action_tools.py is an identical
# copy of the Compliance Agent's (tests/unit/test_action_tools_sync.py).
_REMOTE_TOOLS = {"compliance_agent": [check_action_compliance]}


async def _agents_map() -> dict[str, dict]:
    agents: dict[str, dict] = {}

    async def walk(agent) -> None:
        if agent.name in agents:
            return
        config = {
            "agent_id": agent.name,
            "agent_type": type(agent).__name__,
            "description": agent.description or None,
            "sub_agents": [sub.name for sub in agent.sub_agents] or None,
        }
        if isinstance(agent, LlmAgent):
            if isinstance(agent.instruction, str):
                config["instruction"] = agent.instruction
            tools = await get_tools_info(agent.tools)
            config["tools"] = [
                tool.model_dump(mode="json", exclude_none=True) for tool in tools
            ] or None
            for tool in agent.tools:
                if hasattr(tool, "close"):
                    await tool.close()
        elif agent.name in _REMOTE_TOOLS:
            tools = await get_tools_info(_REMOTE_TOOLS[agent.name])
            config["tools"] = [
                tool.model_dump(mode="json", exclude_none=True) for tool in tools
            ]
        agents[agent.name] = {k: v for k, v in config.items() if v is not None}
        for sub in agent.sub_agents:
            await walk(sub)

    await walk(root_agent)
    return agents


def main(path: str) -> None:
    with open(path) as f:
        data = json.load(f)
    agents = asyncio.run(_agents_map())
    cases = data["eval_cases"] if isinstance(data, dict) else data
    for case in cases:
        if case.get("agent_data") is not None:
            case["agent_data"]["agents"] = agents
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Added {len(agents)} agent definitions to {len(cases)} case(s) in {path}")


if __name__ == "__main__":
    main(sys.argv[1])
