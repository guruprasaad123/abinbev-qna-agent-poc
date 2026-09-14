"""
Aggregates all 25 capability case modules into one ordered list, so both
the live test suite and the notebook generator have a single place to
iterate from. Each module (cap01_... through cap25_...) defines TITLE,
CAPABILITY_NUMBER, and CASES -- see tests/live/runner.py for the Case
schema these are built from.
"""
import importlib
import pkgutil

_MODULE_NAMES = [
    "cap01_single_multi_turn",
    "cap02_greeting_capability_oos",
    "cap03_intent_validation",
    "cap04_clarification",
    "cap05_contextual_followup",
    "cap06_semantic_understanding",
    "cap07_multilingual",
    "cap08_context_preservation",
    "cap09_sql_safety",
    "cap10_structured_unstructured_retrieval",
    "cap11_document_citations",
    "cap12_hybrid_retrieval",
    "cap13_answer_validation_retry",
    "cap14_standardized_formatting",
    "cap15_temporal_reasoning",
    "cap16_followup_suggestions",
    "cap17_memory_optimization",
    "cap18_metadata_queries",
    "cap19_multi_kpi_entity_hierarchy",
    "cap20_analytical_comparisons",
    "cap21_hierarchy_fallback",
    "cap22_metadata_discovery",
    "cap23_document_filtering",
    "cap24_transparent_reporting",
    "cap25_graceful_handling",
]

CAPABILITIES = []  # list of {number, slug, title, cases} in assignment order
for _name in _MODULE_NAMES:
    _mod = importlib.import_module(f"tests.live.cases.{_name}")
    CAPABILITIES.append({
        "number": _mod.CAPABILITY_NUMBER,
        "slug": _name,
        "title": _mod.TITLE,
        "cases": _mod.CASES,
    })

assert len(CAPABILITIES) == 25, f"expected 25 capabilities, found {len(CAPABILITIES)}"
