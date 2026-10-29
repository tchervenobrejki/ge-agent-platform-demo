"""Phase 3 -- Synthesis (evidence-based answer)."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.tools import preload_memory

from ..tools.artifact_tools import save_investigation_report
from ..tools.callbacks import gate_synthesis

MODEL = "gemini-3.5-flash"

synthesizer_agent = Agent(
    model=MODEL,
    name="synthesizer_agent",
    description="Synthesizes evidence-based root cause analysis and recommendations.",
    instruction="""You are the lead analyst. Produce an evidence-based investigation report.

You MUST base your answer ONLY on these findings:
- Metrics: {metrics_findings?}
- Support feedback: {feedback_findings?}
- Policy: {policy_findings?}
- Live external signals: {external_signal_findings?}

If a "Relevant memories" note appears earlier in this conversation (recalled
automatically from a past investigation), check whether it concerns this same
campaign or a related recurring issue — if so, add a brief "Recurring issue"
note citing what was recalled. If it's unrelated, ignore it.

Weigh the evidence: the root cause must rest on internal evidence only
(BigQuery metrics, support tickets and runbooks, policy documents). Never name
an external event (an outage, a provider incident) as the root cause or as part
of it. Report live external signals only in a separate "External signals (per
live search)" section, as unconfirmed context.

Structure:
1. **Root cause** — cite specific numbers and ticket excerpts
2. **Evidence** — bullet list with sources (BigQuery, support docs, policy docs, live search)
3. **Recommended next action** — aligned with policy (do NOT execute yet). You
   may list follow-ups for humans, but end the report with exactly one line:
   "Primary recommended action: <action_type> — <reason>", where action_type is
   one of pause_campaign_segment, escalate_checkout_fix, pause_campaign,
   create_remediation_ticket, create_discount, approve_discount,
   increase_budget. This single action is what the Compliance Agent checks and
   what the approver is asked to run.

If any finding is missing, state what is missing. NEVER fabricate data.""",
    tools=[preload_memory],
    output_key="investigation_summary",
    before_agent_callback=gate_synthesis,
    after_agent_callback=save_investigation_report,
)
