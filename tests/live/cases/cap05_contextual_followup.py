"""Capability 5: contextual follow-up questions by maintaining conversation history."""
from tests.live.runner import Case, active_filter_contains, not_crashed_and_answered, all_of, answer_contains_any

TITLE = "Contextual follow-up questions by maintaining conversation history"
CAPABILITY_NUMBER = 5

CASES = [
    Case("01", "follow-up omits the zone -- should reuse the prior one",
         ["What was North America's revenue in Q1 2024?", "What about its EBITDA margin?"],
         active_filter_contains("zone", "North America")),

    Case("02", "follow-up omits the period -- should reuse the prior one",
         ["What was EMEA's revenue in Q3 2025?", "And the volume?"],
         active_filter_contains("period", "Q3 2025")),

    Case("03", "'and last year?' style follow-up implying a period shift",
         ["What was South America's revenue in 2025?", "And in 2024?"],
         not_crashed_and_answered()),

    Case("04", "pronoun follow-up ('it', 'that') resolved via context",
         ["What was Middle Americas' revenue in 2025?", "Is that up or down from 2024?"],
         answer_contains_any("up", "down", "increase", "decrease", "grew", "declined", "%")),

    Case("05", "follow-up asking for a related KPI without repeating the zone",
         ["What was Asia Pacific's volume in Q2 2025?", "What about revenue for the same period?"],
         active_filter_contains("zone", "Asia Pacific")),

    Case("06", "3-turn chain, each turn depends on the previous one's context",
         ["What was North America's revenue in 2025?",
          "Break that down by quarter.",
          "Which quarter was strongest?"],
         not_crashed_and_answered()),

    Case("07", "follow-up explicitly overriding the zone should NOT keep the old one",
         ["What was EMEA's revenue in 2025?", "Now show me North America instead."],
         active_filter_contains("zone", "North America")),
]
