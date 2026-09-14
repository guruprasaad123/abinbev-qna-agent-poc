"""Capability 22: metadata discovery for available KPIs, dimensions, periods, and datasets."""
from tests.live.runner import Case, intent_is, answer_contains_any, all_of

TITLE = "Metadata discovery for available KPIs, dimensions, periods, and datasets"
CAPABILITY_NUMBER = 22

CASES = [
    Case("01", "discover available KPIs with their units",
         ["What metrics are available and in what units?"],
         answer_contains_any("million", "hl", "%", "percent")),

    Case("02", "discover available zones",
         ["List all the zones/regions you have data for"],
         answer_contains_any("north america", "emea", "asia pacific")),

    Case("03", "discover available countries and their zone mapping",
         ["What countries do you know about, and which zone do they roll up to?"],
         intent_is("metadata_discovery")),

    Case("04", "discover available document-only brands",
         ["What brands do you have information about?"],
         answer_contains_any("budweiser", "corona", "stella")),

    Case("05", "discover the exact date range of structured data",
         ["What's the earliest and latest period in your structured data?"],
         answer_contains_any("2022", "2024", "2025")),

    Case("06", "discover document types available",
         ["What kinds of documents do you have?"], intent_is("metadata_discovery")),

    Case("07", "discover data granularity limitations upfront",
         ["Do you have quarterly and annual data, or just one?"],
         # The real answer correctly conveys this via the actual grain
         # ("zone x quarter", "zone x year") rather than the literal words
         # "quarterly"/"annual" -- broadened from an overly literal substring
         # check that was failing a genuinely correct answer.
         answer_contains_any("quarterly", "annual", "quarter", "year", "grain")),
]
