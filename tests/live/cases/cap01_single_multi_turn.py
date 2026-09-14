"""Capability 1: single-turn and multi-turn conversational interactions."""
from tests.live.runner import (
    Case, intent_is, not_crashed_and_answered, active_filter_contains, all_of,
)

TITLE = "Single-turn and multi-turn conversational interactions"
CAPABILITY_NUMBER = 1

CASES = [
    Case("01", "single-turn: one question, one complete answer",
         ["What was North America's revenue in Q1 2024?"],
         all_of(intent_is("data_query"), not_crashed_and_answered())),

    Case("02", "single-turn: a different zone/KPI in isolation",
         ["What was EMEA's EBITDA margin in Q2 2025?"],
         all_of(intent_is("data_query"), not_crashed_and_answered())),

    Case("03", "multi-turn: 2 turns, second reuses zone from the first",
         ["What was South America's revenue in 2024?", "And its volume?"],
         active_filter_contains("zone", "South America")),

    Case("04", "multi-turn: 3 turns, drilling from company-wide to a zone to a KPI",
         ["Give me AB InBev's overall FY2025 revenue.",
          "Now just for Middle Americas.",
          "What about its EBITDA margin?"],
         active_filter_contains("zone", "Middle Americas")),

    Case("05", "multi-turn: 4 turns mixing intents (greeting, data, comparison, metadata)",
         ["Hi there",
          "What was North America's revenue in Q1 2025?",
          "How does that compare to EMEA?",
          "What KPIs do you track?"],
         not_crashed_and_answered()),

    Case("06", "multi-turn: a long-ish 5-turn back-and-forth on the same zone",
         ["What was Asia Pacific's revenue in 2025?",
          "And 2024?",
          "What about volume for both years?",
          "Any earnings commentary on Asia Pacific?",
          "What's the EBITDA margin trend across 2025?"],
         active_filter_contains("zone", "Asia Pacific")),

    Case("07", "single-turn immediately followed by an unrelated single-turn (no shared context expected)",
         ["What was North America's net profit in FY2025?"],
         all_of(intent_is("data_query"), not_crashed_and_answered())),

    Case("08", "multi-turn: switching zones mid-conversation, latest wins",
         ["What was North America's revenue in Q1 2024?",
          "Now show me the same for South America."],
         active_filter_contains("zone", "South America")),

    Case("09", "multi-turn: a clarification turn followed by a proper answer",
         ["Tell me about performance.",
          "I mean North America's revenue for Q1 2024."],
         not_crashed_and_answered()),
]
