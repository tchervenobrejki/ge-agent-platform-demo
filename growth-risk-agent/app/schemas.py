"""Structured-output schemas shared between agents and their callbacks."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RequestedAction(BaseModel):
    """An action the user explicitly asked for (spec use case 3).

    When set, the investigation is skipped and this exact action goes to the
    Compliance Agent -- otherwise only the synthesizer's own recommendation
    would ever be checked, and the requested action might never be.
    """

    action_type: str
    campaign_id: Optional[str] = None
    percentage: Optional[float] = None
    amount: Optional[float] = None
    reason: Optional[str] = None


class TriageContext(BaseModel):
    """Structured extraction from the user's investigation request.

    Exactly one of (campaign_id/incident_date/issue_type) or
    clarifying_question is populated -- see triage_agent's instruction.
    """

    campaign_id: Optional[str] = None
    incident_date: Optional[str] = None
    issue_type: Optional[str] = None
    clarifying_question: Optional[str] = None
    requested_action: Optional[RequestedAction] = None
