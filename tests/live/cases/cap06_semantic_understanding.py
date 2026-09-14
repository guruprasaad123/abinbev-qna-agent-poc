"""Capability 6: semantic understanding -- aliases, abbreviations, typo correction."""
from tests.live.runner import Case, answer_contains_any, not_crashed_and_answered, intent_is, all_of

TITLE = "Semantic understanding: aliases, abbreviations, and typo correction"
CAPABILITY_NUMBER = 6

CASES = [
    Case("01", "zone abbreviation 'NA' for North America",
         ["NA rev Q1 2024?"], answer_contains_any("3,593", "3593", "north america")),

    Case("02", "zone alias 'EMEA' used directly (already canonical, sanity check)",
         ["EMEA revenue Q2 2025"], not_crashed_and_answered()),

    Case("03", "country alias 'US' for United States, should roll up to North America",
         ["What's US revenue for Q1 2024?"], answer_contains_any("north america")),

    Case("04", "typo in a zone name ('Norht' for 'North')",
         ["What was the revenu for Norht America in Q1 2024?"],
         answer_contains_any("3,593", "3593", "north america")),

    Case("05", "typo in a KPI word ('EBTIDA' for 'EBITDA')",
         ["What was North America's EBTIDA margin in Q1 2025?"], not_crashed_and_answered()),

    Case("06", "KPI abbreviation 'rev' for revenue",
         ["EMEA rev 2025"], not_crashed_and_answered()),

    Case("07", "KPI shorthand 'margin' for EBITDA margin",
         ["What's the margin for North America in Q4 2025?"], not_crashed_and_answered()),

    Case("08", "casual shorthand for a comparison ('NA vs EMEA')",
         ["NA vs EMEA revenue 2025"], intent_is("comparison")),

    Case("09", "brand alias/shorthand recognized (Bud for Budweiser)",
         ["How is Bud doing as a global brand?"], not_crashed_and_answered()),
]
