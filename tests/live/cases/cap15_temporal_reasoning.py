"""Capability 15: temporal reasoning for current, historical, and comparative periods."""
from tests.live.runner import Case, not_crashed_and_answered, answer_contains_any, all_of, intent_is

TITLE = "Temporal reasoning for current, historical, and comparative period analysis"
CAPABILITY_NUMBER = 15

CASES = [
    Case("01", "current/latest period, implied not stated",
         ["What is AB InBev's most recent quarterly revenue?"], not_crashed_and_answered()),

    Case("02", "explicit historical period",
         ["What was North America's revenue in Q1 2024?"], not_crashed_and_answered()),

    Case("03", "year-over-year comparison, explicit",
         ["How did Middle Americas revenue in Q4 2025 compare to Q4 2024?"],
         answer_contains_any("%", "increase", "decrease", "up", "down", "grew", "declined")),

    Case("04", "quarter-over-quarter comparison",
         ["How did North America's revenue in Q2 2025 compare to Q1 2025?"],
         not_crashed_and_answered()),

    Case("05", "full-year trend across all quarters",
         ["What is EMEA's revenue trend across each quarter of 2025?"], not_crashed_and_answered()),

    Case("06", "relative period phrasing ('last year', 'this year')",
         ["What was South America's revenue last year?"], not_crashed_and_answered()),

    Case("07", "explicit multi-year comparison intent",
         ["Compare North America's EBITDA margin in 2024 versus 2025"], intent_is("comparison")),

    Case("08", "annual (FY) grain versus quarterly grain distinction",
         ["What was AB InBev's FY2025 total revenue?"], not_crashed_and_answered()),
]
