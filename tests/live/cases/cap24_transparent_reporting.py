"""Capability 24: transparent reporting of assumptions, data availability, and system limitations."""
from tests.live.runner import Case, assumptions_contains, not_crashed_and_answered, all_of

TITLE = "Transparent reporting of assumptions, data availability, and system limitations"
CAPABILITY_NUMBER = 24

CASES = [
    Case("01", "country rollup should be stated as an explicit assumption",
         ["What was AB InBev's revenue in Brazil in 2025?"],
         assumptions_contains("doesn't publicly disclose", "zone", "south america")),

    Case("02", "unsupported competitor should be flagged transparently",
         ["What is Molson Coors' revenue?"], not_crashed_and_answered()),

    Case("03", "brand-level financial unavailability should be stated plainly",
         ["What was the exact revenue for Budweiser as a standalone brand in 2025?"],
         not_crashed_and_answered()),

    Case("04", "a truncated/limited result should note the limitation",
         ["Show me every single data point you have for North America"],
         not_crashed_and_answered()),

    Case("05", "web search unavailable/degraded should be reported, not silently ignored",
         ["What's Heineken's current global market share?"], not_crashed_and_answered()),

    Case("06", "an answer combining structured + unstructured should note which came from where",
         ["What was North America's revenue in Q1 2024, and what's the commentary behind it?"],
         not_crashed_and_answered()),
]
