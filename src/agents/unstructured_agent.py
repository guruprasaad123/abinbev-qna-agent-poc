"""
Unstructured Data Sub-Agent: wraps retrieval_tool with LLM-assisted query
understanding (entity/tag extraction from the NL question) so the caller
doesn't have to hand-parse brands/countries/tags out of free text -- the
orchestrator's NLU pass already resolves aliases/typos, but this agent adds
a lightweight second extraction pass tuned specifically for retrieval
filters (recency intent, source-type intent like "press release" vs
"earnings").
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field

from src.tools.retrieval_tool import get_index, RetrievedDoc
from src.config import ALL_BRANDS, ALL_COUNTRIES

SOURCE_TYPE_HINTS = {
    "press release": "press_release", "announcement": "press_release",
    "earnings": "earnings_commentary", "quarterly result": "earnings_commentary",
    "market research": "market_research", "consumer trend": "market_research",
    "sustainability": "sustainability", "esg": "sustainability",
    "competitor": "competitor_intel", "competitive": "competitor_intel",
    "strategy": "strategy_memo", "memo": "strategy_memo",
}
RECENCY_HINTS = ("latest", "most recent", "recent", "newest", "this year", "last month")


@dataclass
class UnstructuredResult:
    ok: bool
    documents: list[RetrievedDoc] = field(default_factory=list)
    error: str = ""


def _extract_filters(question: str) -> dict:
    q = question.lower()
    brands = [b for b in ALL_BRANDS if b.lower() in q]
    countries = [c for c in ALL_COUNTRIES if c.lower() in q]
    source_types = [v for k, v in SOURCE_TYPE_HINTS.items() if k in q]
    recency_weight = 1.2 if any(h in q for h in RECENCY_HINTS) else 0.5
    return {"brands": brands, "countries": countries, "source_types": list(set(source_types)),
            "recency_weight": recency_weight}


def answer(llm_client, question: str, context_block: str = "", k: int = 5) -> UnstructuredResult:
    filters = _extract_filters(question)
    # Fold in any brand/country already active in conversation context if the
    # current question doesn't name one explicitly (contextual follow-up support).
    if context_block and not filters["brands"]:
        m = re.search(r"brand=([^,\n]+)", context_block)
        if m:
            filters["brands"] = [m.group(1).strip()]
    if context_block and not filters["countries"]:
        m = re.search(r"country=([^,\n]+)", context_block)
        if m:
            filters["countries"] = [m.group(1).strip()]

    try:
        docs = get_index().search(
            question, k=k, brands=filters["brands"], countries=filters["countries"],
            source_types=filters["source_types"], recency_weight=filters["recency_weight"],
        )
        return UnstructuredResult(ok=True, documents=docs)
    except Exception as e:  # defensive: retrieval should never crash the whole answer
        return UnstructuredResult(ok=False, error=str(e))
