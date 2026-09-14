"""Capability 19: multiple KPIs, entities, dimensions, and hierarchical business structures."""
from tests.live.runner import Case, not_crashed_and_answered, answer_contains_any, all_of, active_filter_contains

TITLE = "Multiple KPIs, entities, dimensions, and hierarchical business structures"
CAPABILITY_NUMBER = 19

CASES = [
    Case("01", "revenue KPI", ["What was North America's revenue in Q1 2024?"], not_crashed_and_answered()),
    Case("02", "volume KPI", ["What was EMEA's volume in Q2 2025?"], not_crashed_and_answered()),
    Case("03", "normalized EBITDA KPI", ["What was Asia Pacific's normalized EBITDA in 2025?"],
         not_crashed_and_answered()),
    Case("04", "EBITDA margin KPI (computed)", ["What was South America's EBITDA margin in Q4 2025?"],
         not_crashed_and_answered()),
    Case("05", "organic revenue growth KPI", ["What was Middle Americas' organic revenue growth in 2025?"],
         not_crashed_and_answered()),
    Case("06", "net profit KPI", ["What was AB InBev's net profit in FY2025?"], not_crashed_and_answered()),
    Case("07", "hierarchy: country resolves under its zone",
         ["What was the revenue for the United States in Q1 2024?"],
         active_filter_contains("zone", "North America")),
    Case("08", "hierarchy: a different country under a different zone",
         ["What was Colombia's revenue contribution in 2025?"],
         answer_contains_any("middle americas")),
    Case("09", "entity dimension: brand-level qualitative question",
         ["How is Stella Artois performing globally?"], not_crashed_and_answered()),
    Case("10", "multiple dimensions combined: zone + KPI + period in one ask",
         ["What was North America's EBITDA margin in Q1 2024?"], not_crashed_and_answered()),
]
