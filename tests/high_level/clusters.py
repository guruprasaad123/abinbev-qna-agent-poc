"""
The "High-Level Tier": groups the 25 granular required capabilities (see
tests/live/cases/) into 6 enterprise domain clusters, for an executive-
level view alongside the capability-by-capability one.

This is a ROLLUP over the already-executed tests/live/reports/cap*.json --
it defines no new cases and makes no new LLM calls (see rollup.py). Every
capability number 1-25 must appear in exactly one cluster; CLUSTERS'
completeness is asserted at import time and covered by
test_high_level_rollup.py.
"""

CLUSTERS = {
    "conversational_core": {
        "title": "Conversational Core",
        "description": "Turn-taking, scope handling, clarification, and memory across a conversation.",
        "capability_numbers": [1, 2, 3, 4, 5, 8, 16, 17],
    },
    "semantic_multilingual": {
        "title": "Semantic Understanding & Multilingual",
        "description": "Aliases, abbreviations, typo correction, and cross-language queries.",
        "capability_numbers": [6, 7],
    },
    "sql_safety": {
        "title": "SQL Safety",
        "description": "Secure, read-only, whitelisted access to structured data.",
        "capability_numbers": [9],
    },
    "retrieval_hybrid": {
        "title": "Retrieval & Hybrid Data Access",
        "description": "Structured + unstructured retrieval, citations, and combining sources in one turn.",
        "capability_numbers": [10, 11, 12, 23],
    },
    "analytics_temporal": {
        "title": "Analytics & Temporal Reasoning",
        "description": "KPIs, entities, hierarchies, comparisons, formatting, and time-aware analysis.",
        "capability_numbers": [14, 15, 18, 19, 20, 22],
    },
    "governance_guardrails": {
        "title": "Governance & Guardrails",
        "description": "Validation/retry, hierarchy fallback, transparency, and graceful degradation.",
        "capability_numbers": [13, 21, 24, 25],
    },
}

_ALL_NUMBERS = [n for c in CLUSTERS.values() for n in c["capability_numbers"]]
assert sorted(_ALL_NUMBERS) == list(range(1, 26)), (
    f"CLUSTERS must cover capability numbers 1-25 exactly once each; got {sorted(_ALL_NUMBERS)}"
)


def cluster_for_capability(number: int) -> str:
    for slug, cluster in CLUSTERS.items():
        if number in cluster["capability_numbers"]:
            return slug
    raise KeyError(f"capability {number} is not assigned to any cluster")
