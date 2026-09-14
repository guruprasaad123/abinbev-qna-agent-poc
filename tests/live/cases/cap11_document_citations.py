"""Capability 11: document retrieval with source citations."""
from tests.live.runner import Case, citations_nonempty, used_subagent, all_of

TITLE = "Document retrieval with source citations"
CAPABILITY_NUMBER = 11

CASES = [
    Case("01", "brand question should come back with citations",
         ["What is Corona's growth strategy outside Mexico?"], citations_nonempty()),

    Case("02", "country-context question should come back with citations",
         ["What's driving Brazil's volume decline?"], citations_nonempty()),

    Case("03", "earnings-commentary question should come back with citations",
         ["What did the FY2025 earnings commentary say about North America?"],
         citations_nonempty()),

    Case("04", "megabrand/portfolio question should come back with citations",
         ["How are AB InBev's megabrands performing?"], citations_nonempty()),

    Case("05", "a specific brand+country combination should come back with citations",
         ["How is Michelob Ultra doing in the US market?"], citations_nonempty()),

    Case("06", "sustainability/strategy question should come back with citations",
         ["What are AB InBev's sustainability initiatives?"], citations_nonempty()),

    Case("07", "a pure structured question should NOT need citations (sanity/contrast case)",
         ["What was North America's revenue in Q1 2024?"], used_subagent("structured")),
]
