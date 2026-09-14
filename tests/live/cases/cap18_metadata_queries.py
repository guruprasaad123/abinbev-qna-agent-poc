"""Capability 18: metadata queries."""
from tests.live.runner import Case, intent_is, no_subagent_used, answer_contains_any, all_of

TITLE = "Metadata queries"
CAPABILITY_NUMBER = 18

CASES = [
    Case("01", "asking what KPIs are available", ["What KPIs do you track?"],
         all_of(intent_is("metadata_discovery"), no_subagent_used())),
    Case("02", "asking what zones/regions are available", ["What zones can I ask about?"],
         intent_is("metadata_discovery")),
    Case("03", "asking what data is available in general -- observed non-deterministically "
               "classified as capability_intro on some real runs, metadata_discovery on others; "
               "both are genuinely reasonable readings of this open-ended phrasing, so accepting "
               "either rather than treating one run's classification as ground truth",
         ["What data do you have access to?"],
         intent_is("metadata_discovery", "capability_intro")),
    Case("04", "asking about the time range of the data", ["What time period does your data cover?"],
         answer_contains_any("2024", "2025", "2022")),
    Case("05", "asking what topics/datasets are supported -- consistently and reasonably read "
               "as EITHER capability_intro or metadata_discovery by the real model (both produce "
               "a complete, sensible answer); accepting both rather than forcing one 'correct' "
               "reading of a genuinely dual-purpose phrasing",
         ["What topics or datasets can I ask you about?"],
         intent_is("metadata_discovery", "capability_intro")),
    Case("06", "asking specifically about available metrics",
         ["What metrics are available?"], intent_is("metadata_discovery")),
    Case("07", "asking about dataset granularity",
         ["Do you have country-level or brand-level financial data?"],
         answer_contains_any("zone", "does not", "doesn't", "no country", "no brand")),
]
