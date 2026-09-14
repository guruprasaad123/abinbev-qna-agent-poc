"""Capability 20: analytical comparisons across KPIs, entities, periods, and business domains."""
from tests.live.runner import Case, intent_is, has_markdown_table, not_crashed_and_answered, all_of

TITLE = "Analytical comparisons across KPIs, entities, periods, and business domains"
CAPABILITY_NUMBER = 20

CASES = [
    Case("01", "compare one KPI across two zones",
         ["Compare revenue between North America and EMEA in 2025"], intent_is("comparison")),

    Case("02", "compare one zone across two periods",
         ["How did North America's revenue in 2025 compare to 2024?"], not_crashed_and_answered()),

    Case("03", "compare two KPIs for one zone",
         ["Compare EBITDA margin and organic revenue growth for North America in 2025"],
         not_crashed_and_answered()),

    Case("04", "compare two KPIs across two zones at once",
         ["Compare EBITDA margin and organic revenue growth for North America versus EMEA in 2025"],
         has_markdown_table()),

    Case("05", "compare three zones on one KPI",
         ["Compare revenue across North America, EMEA, and Asia Pacific in 2025"],
         has_markdown_table()),

    Case("06", "compare a brand's document-level context across two countries",
         ["How does Corona's positioning differ between Mexico and other markets?"],
         not_crashed_and_answered()),

    Case("07", "compare quarter-over-quarter within a single zone",
         ["Compare Middle Americas revenue in Q4 2025 versus Q3 2025"], not_crashed_and_answered()),

    Case("08", "compare AB InBev's own numbers against a named real competitor",
         ["How does AB InBev's overall performance compare to Heineken's public position?"],
         not_crashed_and_answered()),
]
