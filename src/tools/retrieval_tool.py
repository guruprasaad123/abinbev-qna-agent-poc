"""
Unstructured document retrieval: hybrid lexical (BM25) + metadata + optional
semantic (embedding) retrieval over the generated document corpus, with
citations.

"Hybrid data retrieval" here means combining independent signals rather
than lexical alone:
  1. BM25 relevance score over document title+body (keyword matching,
     robust to word order/frequency, but blind to paraphrase/synonymy).
  2. Metadata match score: exact/alias-resolved hits against tags, brands,
     countries and source_type mentioned or implied by the query, plus a
     recency boost. Metadata filtering also supports being used standalone
     ("Support document filtering using metadata, tags, and recency") for
     queries like "show me the most recent sustainability updates".
  3. Semantic (embedding) similarity, OPTIONAL and gracefully degraded if
     unavailable -- see src/tools/embedding_tool.py for the local-model
     choice and the real, measured cost/latency numbers, and
     docs/DESIGN_DECISIONS.md §6 for the full trade-off writeup. When a
     precomputed embeddings cache exists (scripts/generate_embeddings.py)
     and `fastembed` is installed, every document is scored regardless of
     lexical overlap -- the whole point of adding this signal is to surface
     a paraphrased match BM25 would score zero on. When unavailable, this
     silently falls back to exactly the original BM25 + metadata behavior.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from src.tools.bm25 import BM25, tokenize
from src.tools.embedding_tool import (
    embed_texts, cosine_similarity, load_cached_document_embeddings,
)

SEMANTIC_WEIGHT = 3.0  # tunable: puts a typical 0.3-0.8 cosine similarity on
                        # a roughly comparable additive scale to this corpus's
                        # typical BM25 scores -- not a principled calibration,
                        # just a reasonable blend for a 15-document corpus.

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
        # Optional semantic signal -- None means "unavailable", checked once
        # at index-build time (not per query) so search() has a cheap,
        # consistent True/False to branch on.
        doc_ids = [d["doc_id"] for d in self.docs]
        cached = load_cached_document_embeddings(doc_ids)
        self.doc_embeddings: dict[str, list[float]] | None = cached

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

        # Query-time embedding: computed fresh (can't be precomputed like the
        # corpus), ~4ms locally -- negligible next to this system's LLM call
        # latencies. A failure here (fastembed not installed, or a transient
        # model error) means query_embedding is None and we transparently
        # fall back to the original BM25 + metadata behavior for this call.
        query_embedding = None
        if self.doc_embeddings is not None:
            vecs = embed_texts([query])
            query_embedding = vecs[0] if vecs else None

        # Even if BM25 finds nothing (e.g. a pure metadata query like "show me
        # sustainability docs"), or embeddings are in play (a paraphrase match
        # can score zero on BM25 but high on semantic similarity -- the whole
        # point of adding this signal), consider every document.
        if not candidate_idx and (brands or countries or tags or source_types or query_embedding):
            candidate_idx = set(range(len(self.docs)))
        elif query_embedding:
            candidate_idx |= set(range(len(self.docs)))

        scored = []
        for i in candidate_idx:
            doc = self.docs[i]
            lexical = bm25_hits.get(i, 0.0)
            meta = self._metadata_score(doc, brands, countries, tags, source_types)
            recency = self._recency_boost(doc["date"], recency_weight)
            semantic = 0.0
            if query_embedding is not None:
                doc_vec = self.doc_embeddings.get(doc["doc_id"])
                if doc_vec is not None:
                    semantic = SEMANTIC_WEIGHT * cosine_similarity(query_embedding, doc_vec)
            total = lexical + meta + recency + semantic
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
