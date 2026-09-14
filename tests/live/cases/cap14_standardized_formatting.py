"""Capability 14: standardized formatting -- markdown tables and unit-aware presentation."""
from tests.live.runner import Case, has_markdown_table, answer_contains_any, all_of, not_crashed_and_answered

TITLE = "Standardized formatting, including markdown tables and unit-aware presentation"
CAPABILITY_NUMBER = 14

CASES = [
    Case("01", "multi-KPI question should render as a markdown table",
         ["Give me North America's revenue, volume, and EBITDA margin for Q1 2024"],
         has_markdown_table()),

    Case("02", "comparison across zones should render as a markdown table",
         ["Compare revenue between North America and EMEA in 2025"], has_markdown_table()),

    Case("03", "revenue figure should carry its unit (USD million)",
         ["What was North America's revenue in Q1 2024?"],
         answer_contains_any("million", "usd", "$")),

    Case("04", "volume figure should carry its unit (thousand hL)",
         ["What was EMEA's volume in Q2 2025?"], answer_contains_any("hl", "hectoliter")),

    Case("05", "EBITDA margin should be presented as a percentage",
         ["What was Asia Pacific's EBITDA margin in 2025?"], answer_contains_any("%", "percent")),

    Case("06", "a quarterly trend question should render as a table with one row per quarter",
         ["Show me EMEA's revenue for each quarter of 2025"], has_markdown_table()),

    Case("07", "a single, simple figure need not force a table (sanity check formatting isn't over-applied)",
         ["What was North America's net profit in FY2025?"], not_crashed_and_answered()),
]
