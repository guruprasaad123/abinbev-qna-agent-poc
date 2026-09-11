"""
Minimal, dependency-free BM25 implementation.

WHY WRITE OUR OWN: the obvious `rank_bm25` PyPI package was not resolvable
through this environment's package mirror at build time, and rather than
block the whole retrieval sub-agent on that (or reach for a heavier
embedding-model dependency that needs a model download we can't guarantee
network access to either), BM25 is ~40 lines of well-understood, auditable
math. It has zero runtime dependencies, which also makes the *deliverable*
more portable for whoever runs it. See docs/DESIGN_DECISIONS.md for the
full trade-off discussion (BM25 vs TF-IDF vs embeddings).
"""
from __future__ import annotations
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.documents = documents
        self.doc_lens = [len(d) for d in documents]
        self.avgdl = sum(self.doc_lens) / len(documents) if documents else 0.0
        self.term_freqs: list[Counter] = [Counter(d) for d in documents]
        self.doc_freq: Counter = Counter()
        for tf in self.term_freqs:
            for term in tf:
                self.doc_freq[term] += 1
        self.n_docs = len(documents)
        self.idf: dict[str, float] = {
            term: math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            for term, df in self.doc_freq.items()
        }

    def score(self, query_tokens: list[str], idx: int) -> float:
        tf = self.term_freqs[idx]
        dl = self.doc_lens[idx] or 1
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            idf = self.idf.get(term, 0.0)
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            score += idf * (freq * (self.k1 + 1)) / (denom or 1)
        return score

    def top_k(self, query: str, k: int = 5, candidate_indices: list[int] | None = None) -> list[tuple[int, float]]:
        q_tokens = tokenize(query)
        indices = candidate_indices if candidate_indices is not None else range(self.n_docs)
        scored = [(i, self.score(q_tokens, i)) for i in indices]
        scored = [s for s in scored if s[1] > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
