"""Capability 12: hybrid data retrieval (multiple sub-agents in one turn)."""
from tests.live.runner import Case, used_subagents_all, not_crashed_and_answered, all_of

TITLE = "Hybrid data retrieval"
CAPABILITY_NUMBER = 12

CASES = [
    Case("01", "numbers (structured) + qualitative commentary (unstructured) in one question",
         ["How did North America perform in Q1 2024, and what does the earnings commentary say about it?"],
         used_subagents_all("structured", "unstructured")),

    Case("02", "structured KPI + a named real competitor (needs web)",
         ["What was AB InBev's revenue in 2025, and how does that compare to Heineken's public position?"],
         not_crashed_and_answered()),

    Case("03", "structured + coding: a number plus a derived calculation on it",
         ["What was North America's Q1 2024 revenue, and what would it be if it grew 5% annually for 3 years?"],
         used_subagents_all("structured", "coding")),

    Case("04", "structured + unstructured + a hierarchy-fallback note (country -> zone)",
         ["What was AB InBev's revenue in Brazil specifically in 2025, and what's the commentary on it?"],
         used_subagents_all("structured", "unstructured")),

    Case("05", "three sub-agents in one turn: structured + unstructured + web",
         ["How did North America perform in Q1 2024, what's Heineken's public market position, "
          "and any recent AB InBev press commentary on North America?"],
         not_crashed_and_answered()),

    Case("06", "brand (unstructured) + a competitor comparison (web) together",
         ["How does Corona compare to Heineken in terms of brand positioning?"],
         not_crashed_and_answered()),
]
