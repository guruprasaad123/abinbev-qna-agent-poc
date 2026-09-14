"""Capability 17: conversation memory optimization for long-running sessions.

src/memory.py's SUMMARIZE_TRIGGER_TURNS=14 (raw_turns entries; each full
turn adds 2 -- one user, one assistant), so a rolling summary should appear
once a conversation passes ~7 full turns. These cases are the most
expensive in the whole suite (each long case is 6-8 real sequential calls
plus a summarization call) -- kept to a small number for that reason.
"""
from tests.live.runner import Case, rolling_summary_present, not_crashed_and_answered, all_of

TITLE = "Conversation memory optimization for long-running sessions"
CAPABILITY_NUMBER = 17

CASES = [
    Case("01", "short conversation (3 turns) -- should NOT have a rolling summary yet",
         ["What was South America revenue in 2024?",
          "And in 2025?",
          "What drove that change?"],
         lambda responses, orch: (not orch.memory.rolling_summary,
                                   f"expected no summary yet, raw_turns={len(orch.memory.raw_turns)}")),

    Case("02", "long conversation (8 turns) -- SHOULD trigger a rolling summary",
         ["What was South America revenue in 2024?",
          "And in 2025?",
          "What drove that change?",
          "Any related earnings commentary?",
          "What about its EBITDA margin there?",
          "How does that compare to Middle Americas?",
          "What was the volume trend for South America in 2025?",
          "And North America's revenue for the same year?"],
         rolling_summary_present()),

    Case("03", "long conversation stays coherent/doesn't crash once summarized",
         ["What was North America revenue in 2024?",
          "And 2025?",
          "What was the EBITDA margin both years?",
          "Compare that to EMEA.",
          "What's driving EMEA's numbers?",
          "Any recent commentary on EMEA?",
          "What about Asia Pacific's revenue in 2025?",
          "Summarize everything we've discussed so far."],
         not_crashed_and_answered()),
]
