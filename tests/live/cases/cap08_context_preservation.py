"""Capability 8: conversation context preservation across interactions.

Distinct from capability 5 (contextual FOLLOW-UP questions): this is about
the memory state itself persisting correctly across many turns, including
after the rolling-summary mechanism kicks in (see cap17 for the
summarization-specific capability).
"""
from tests.live.runner import Case, active_filter_contains, not_crashed_and_answered, all_of

TITLE = "Conversation context preservation across interactions"
CAPABILITY_NUMBER = 8

CASES = [
    Case("01", "zone set on turn 1 is still active after 2 unrelated-ish turns",
         ["What was North America's revenue in Q1 2024?",
          "What KPIs do you track?",
          "What about the volume?"],
         active_filter_contains("zone", "North America")),

    Case("02", "brand context persists across a follow-up",
         ["Tell me about Stella Artois's positioning.",
          "Any recent commentary on it?"],
         active_filter_contains("brand", "Stella Artois")),

    Case("03", "period context persists across a zone change",
         ["What was North America's revenue in Q3 2025?",
          "Now show me the same for EMEA."],
         active_filter_contains("period", "Q3 2025")),

    Case("04", "KPI context persists when only the zone is repeated",
         ["What was the EBITDA margin for Asia Pacific in 2025?",
          "And for South America?"],
         active_filter_contains("kpi", "ebitda")),

    Case("05", "5-turn conversation, context intact at the end",
         ["What was Middle Americas' revenue in 2025?",
          "And its volume?",
          "And EBITDA margin?",
          "Any related earnings commentary?",
          "How does that compare to South America?"],
         not_crashed_and_answered()),

    Case("06", "context correctly overridden, not merely appended, when the user changes topic",
         ["What was North America's revenue in Q1 2024?",
          "Actually, tell me about Corona's strategy instead."],
         active_filter_contains("brand", "Corona")),
]
