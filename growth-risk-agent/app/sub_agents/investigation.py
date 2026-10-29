"""Phase 2b -- Parallel fan-out: metrics + support RAG + policy RAG + live
external search. The two RAG branches use explicit function tools
(see ../tools/rag_tools.py's docstring for why)."""

from __future__ import annotations

from google.adk.agents import Agent, ParallelAgent
from google.adk.tools import google_search

from ..tools.callbacks import gate_investigation
from ..tools.rag_tools import search_policy_docs, search_support_docs
from .metrics import metrics_branch

MODEL = "gemini-3.5-flash"

feedback_agent = Agent(
    model=MODEL,
    name="feedback_agent",
    description="Retrieves customer support feedback via RAG.",
    instruction="""Investigate customer/support signals for the issue in {triage_context}.

Call search_support_docs (one or two focused queries, e.g. checkout errors,
payment timeouts, conversion drop) and summarize what the returned chunks say.

Cite ONLY the returned chunks: quote ticket IDs, symptoms and runbook steps
exactly as written, naming the source file. Never add tickets, ticket counts,
runbook names or technical causes that are not in a returned chunk. If the
chunks don't cover something, say it is not documented.""",
    tools=[search_support_docs],
    output_key="feedback_findings",
)

# Google Search grounding lives on its own agent rather than folded into
# feedback_agent: Gemini's built-in grounding tools (google_search,
# VertexAiSearchTool, VertexAiRagRetrieval, ...) cannot be declared alongside
# custom function tools in the same model call unless
# bypass_multi_tools_limit=True is set on the tool -- a dedicated
# single-tool agent avoids depending on that.
external_signal_agent = Agent(
    model=MODEL,
    name="external_signal_agent",
    description="Live external grounding via Google Search (contrast with static RAG).",
    instruction="""Search for live external signals relevant to the issue in {triage_context}.

Call google_search for things a static document store wouldn't have — e.g. a
payment gateway's public status page, or reports of an outage affecting
checkout providers around the incident date. Summarize findings with sources
and the search terms used.

Never invent search results — only cite what google_search returns. If
nothing relevant is found, say so.""",
    tools=[google_search],
    output_key="external_signal_findings",
)

policy_agent = Agent(
    model=MODEL,
    name="policy_agent",
    description="Retrieves compliance and campaign policy context via RAG.",
    instruction="""Retrieve policy context for the issue in {triage_context}.

Call search_policy_docs (focused queries such as campaign pause rules,
approval thresholds, conversion drop rollback) and report what the returned
chunks say.

Quote policy ONLY from the returned chunks, verbatim, naming the source file.
Never invent section numbers, thresholds, deadlines or approval roles that are
not in a returned chunk. If the policy doesn't address something, say so.""",
    tools=[search_policy_docs],
    output_key="policy_findings",
)

parallel_investigation = ParallelAgent(
    name="parallel_investigation",
    description="Runs metrics, support, policy, and live external investigations concurrently.",
    sub_agents=[metrics_branch, feedback_agent, policy_agent, external_signal_agent],
    before_agent_callback=gate_investigation,
)
