"""Capability 23: document filtering using metadata, tags, and recency."""
from tests.live.runner import Case, citations_nonempty, used_subagent, not_crashed_and_answered, all_of

TITLE = "Document filtering using metadata, tags, and recency"
CAPABILITY_NUMBER = 23

CASES = [
    Case("01", "filter by recency explicitly",
         ["What are the most recent earnings documents mentioning Asia Pacific?"],
         all_of(used_subagent("unstructured"), citations_nonempty())),

    Case("02", "filter by zone/region tag",
         ["Show me documents related to North America"], citations_nonempty()),

    Case("03", "filter by brand tag",
         ["What documents mention Corona specifically?"], citations_nonempty()),

    Case("04", "filter by source type (press release vs filing)",
         ["What press releases do you have on file?"], not_crashed_and_answered()),

    Case("05", "filter by country tag",
         ["What documents discuss Brazil?"], citations_nonempty()),

    Case("06", "combined filter: brand + recency",
         ["What's the most recent commentary on Michelob Ultra?"], not_crashed_and_answered()),

    Case("07", "combined filter: zone + source type",
         ["Any recent filing excerpts about EMEA?"], not_crashed_and_answered()),

    Case("08", "a query that matches no strong metadata tag -- pure text relevance",
         ["What's AB InBev's approach to sustainability?"], citations_nonempty()),
]
