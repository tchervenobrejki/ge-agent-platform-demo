"""Minimal control agent for diagnosing console Agent Evaluation failures.

Served instead of the orchestrator only when EVAL_CONTROL_AGENT=true (the
workshop-eval-control engine): one LlmAgent, one tool, no resumability, no
callbacks or plugins. If the console evaluates this agent but not the
orchestrator, the failure lies in the orchestrator's structure.
"""

from google.adk.agents import Agent
from google.adk.apps import App

MODEL = "gemini-3.5-flash"


def define_kpi(kpi_name: str) -> dict:
    """Return the definition of a growth KPI.

    Args:
        kpi_name: conversion_rate or checkout_drop_off_rate.
    """
    definitions = {
        "conversion_rate": "conversions divided by clicks for a campaign and day",
        "checkout_drop_off_rate": "share of users who reach checkout but do not pay",
    }
    return {"kpi": kpi_name, "definition": definitions.get(kpi_name, "unknown KPI")}


root_agent = Agent(
    name="kpi_helper",
    model=MODEL,
    description="Explains growth KPIs.",
    instruction=(
        "You explain growth KPIs (conversion_rate, checkout_drop_off_rate) using"
        " the define_kpi tool. Politely decline anything else."
    ),
    tools=[define_kpi],
)

app = App(name="app", root_agent=root_agent)
