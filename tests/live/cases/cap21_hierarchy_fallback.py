"""Capability 21: hierarchy-aware fallback for unsupported entities or granularities."""
from tests.live.runner import Case, assumptions_contains, not_crashed_and_answered, all_of, answer_contains_any

TITLE = "Hierarchy-aware fallback for unsupported entities or granularities"
CAPABILITY_NUMBER = 21

CASES = [
    Case("01", "country requested -> should roll up to its zone with an explicit note",
         ["What was AB InBev's revenue in Brazil specifically in 2025?"],
         assumptions_contains("south america", "doesn't publicly disclose", "zone")),

    Case("02", "a different country -> different zone rollup",
         ["What was the revenue for the United States in Q1 2024?"],
         assumptions_contains("north america")),

    Case("03", "a real, named competitor -> flagged as genuinely unsupported, not silently dropped",
         ["How is Heineken performing financially?"],
         assumptions_contains("tracked entities", "not part of", "competitor", "heineken")),

    Case("04", "brand-level financials requested -> should say they aren't disclosed, not approximate",
         ["What was Budweiser's exact revenue in 2025?"],
         not_crashed_and_answered()),

    Case("05", "a country whose zone rollup should be Middle Americas",
         ["What was Mexico's revenue contribution in 2025?"],
         answer_contains_any("middle americas")),

    Case("06", "a country whose zone rollup should be EMEA",
         ["What was the United Kingdom's revenue in 2025?"], answer_contains_any("emea")),

    Case("07", "combination: country rollup AND a qualitative document answer together",
         ["What was AB InBev's revenue in Brazil, and what's driving it?"],
         not_crashed_and_answered()),
]
