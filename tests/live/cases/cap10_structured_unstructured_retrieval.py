"""Capability 10: structured and unstructured data retrieval from multiple sources."""
from tests.live.runner import Case, used_subagent, no_subagent_used, all_of, not_crashed_and_answered

TITLE = "Structured and unstructured data retrieval from multiple data sources"
CAPABILITY_NUMBER = 10

CASES = [
    Case("01", "pure structured retrieval: numeric zone/KPI question",
         ["What was North America's revenue in Q1 2024?"], used_subagent("structured")),

    Case("02", "pure unstructured retrieval: brand-only qualitative question",
         ["What is Corona's growth strategy outside Mexico?"], used_subagent("unstructured")),

    Case("03", "pure unstructured retrieval: country-color/context question",
         ["What's driving Brazil's volume trend?"], used_subagent("unstructured")),

    Case("04", "structured KPI question at company-wide grain",
         ["What was AB InBev's total net profit in FY2025?"], used_subagent("structured")),

    Case("05", "unstructured: press-release style question",
         ["What did AB InBev announce in its most recent earnings release?"],
         used_subagent("unstructured")),

    Case("06", "structured comparison across two zones",
         ["Compare volume between EMEA and Asia Pacific in 2025"], used_subagent("structured")),

    Case("07", "unstructured: document-type-specific question",
         ["What filing excerpts mention sustainability initiatives?"],
         used_subagent("unstructured")),

    Case("08", "structured: quarterly trend within one zone",
         ["Show me South America's revenue for each quarter of 2025"], used_subagent("structured")),
]
