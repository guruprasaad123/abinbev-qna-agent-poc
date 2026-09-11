"""
Unstructured document retrieval: hybrid lexical (BM25) + metadata retrieval
over the generated document corpus, with citations.

"Hybrid data retrieval" here means combining two independent signals rather
than lexical alone:
  1. BM25 relevance score over document title+body (semantic-ish keyword
     matching, robust to word order/frequency).
  2. Metadata match score: exact/alias-resolved hits against tags, brands,
     countries and source_type mentioned or implied by the query, plus a
     recency boost. Metadata filtering also supports being used standalone
     ("Support document filtering using metadata, tags, and recency") for
     queries like "show me the most recent sustainability updates".
These are combined with tunable weights. A production system would add a
third, genuinely semantic (embedding) signal here -- see
docs/DESIGN_DECISIONS.md for why that's flagged as a follow-up rather than
built now (no embedding endpoint available in this environment, see
llm_client.py for the parallel constraint on the LLM side).
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from src.tools.bm25 import BM25, tokenize

ROOT = Path(__file__).resolve().parents[2]
DOC_DIR = ROOT / "data" / "unstructured"
MANIFEST_PATH = DOC_DIR / "manifest.json"


@dataclass
class RetrievedDoc:
    doc_id: str
    title: str
    date: str
    source_type: str
    tags: list[str]
    brands: list[str]
    countries: list[str]
    score: float
    excerpt: str


class DocumentIndex:
    def __init__(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.docs = manifest["documents"]
        self.bodies = []
        for d in self.docs:
            text = (DOC_DIR / d["file"]).read_text(encoding="utf-8")
            self.bodies.append(text)
        corpus_tokens = [tokenize(d["title"] + " " + body) for d, body in zip(self.docs, self.bodies)]
        self.bm25 = BM25(corpus_tokens)

    def _metadata_score(self, doc: dict, brands: list[str], countries: list[str],
                         tags: list[str], source_types: list[str]) -> float:
        score = 0.0
        if brands:
            score += 2.0 * len(set(b.lower() for b in doc["brands"]) & set(b.lower() for b in brands))
        if countries:
            score += 2.0 * len(set(c.lower() for c in doc["countries"]) & set(c.lower() for c in countries))
        if tags:
            score += 1.5 * len(set(t.lower() for t in doc["tags"]) & set(t.lower() for t in tags))
        if source_types and doc["source_type"] in source_types:
            score += 1.0
        return score

    def _recency_boost(self, doc_date: str, recency_weight: float) -> float:
        if recency_weight <= 0:
            return 0.0
        try:
            d = date.fromisoformat(doc_date)
        except ValueError:
            return 0.0
        days_old = (date.today() - d).days
        # gentle decay: newer documents get a small additive boost, floor at 0
        return recency_weight * max(0.0, 1 - days_old / (365 * 3))

    def search(self, query: str, k: int = 5, brands: list[str] | None = None,
               countries: list[str] | None = None, tags: list[str] | None = None,
               source_types: list[str] | None = None, recency_weight: float = 0.5) -> list[RetrievedDoc]:
        brands, countries, tags, source_types = brands or [], countries or [], tags or [], source_types or []

        bm25_hits = dict(self.bm25.top_k(query, k=max(k * 3, 10)))
        candidate_idx = set(bm25_hits.keys())
        # Even if BM25 finds nothing (e.g. a pure metadata query like "show me
        # sustainability docs"), still consider all docs for metadata-only matching.
        if not candidate_idx and (brands or countries or tags or source_types):
            candidate_idx = set(range(len(self.docs)))

        scored = []
        for i in candidate_idx:
            doc = self.docs[i]
            lexical = bm25_hits.get(i, 0.0)
            meta = self._metadata_score(doc, brands, countries, tags, source_types)
            recency = self._recency_boost(doc["date"], recency_weight)
            total = lexical + meta + recency
            if total <= 0:
                continue
            scored.append((total, i))
        scored.sort(reverse=True)

        results = []
        for total, i in scored[:k]:
            doc = self.docs[i]
            body = self.bodies[i]
            excerpt = " ".join(body.split()[:60]) + ("..." if len(body.split()) > 60 else "")
            results.append(RetrievedDoc(
                doc_id=doc["doc_id"], title=doc["title"], date=doc["date"],
                source_type=doc["source_type"], tags=doc["tags"], brands=doc["brands"],
                countries=doc["countries"], score=round(total, 3), excerpt=excerpt,
            ))
        return results

    def get_full_text(self, doc_id: str) -> str | None:
        for d, body in zip(self.docs, self.bodies):
            if d["doc_id"] == doc_id:
                return body
        return None


_INDEX: DocumentIndex | None = None


def get_index() -> DocumentIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = DocumentIndex()
    return _INDEX
