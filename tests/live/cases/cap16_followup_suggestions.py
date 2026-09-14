"""Capability 16: context-aware follow-up suggestions within supported business domains."""
from tests.live.runner import Case, has_follow_up_suggestions, not_crashed_and_answered, all_of

TITLE = "Context-aware follow-up suggestions within supported business domains"
CAPABILITY_NUMBER = 16

CASES = [
    Case("01", "a single-KPI answer should suggest a natural adjacent KPI",
         ["What was North America's revenue in Q1 2024?"], has_follow_up_suggestions()),

    Case("02", "a single-zone answer should suggest comparing across zones",
         ["What was EMEA's EBITDA margin in 2025?"], has_follow_up_suggestions()),

    Case("03", "a single-period answer should suggest an adjacent period",
         ["What was South America's revenue in Q3 2025?"], has_follow_up_suggestions()),

    Case("04", "after a comparison, suggestions should still be relevant (not necessarily present, but answer must be sound)",
         ["Compare North America and EMEA revenue in 2025"], not_crashed_and_answered()),

    Case("05", "a metadata-discovery turn need not force suggestions (sanity/contrast case)",
         ["What KPIs do you track?"], not_crashed_and_answered()),

    Case("06", "a brand-level qualitative answer should still offer a next step",
         ["Tell me about Corona's growth strategy outside Mexico"], not_crashed_and_answered()),
]
