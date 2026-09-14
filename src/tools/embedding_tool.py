"""
Optional, lightweight LOCAL embedding support for semantic document
retrieval -- a genuine third signal alongside BM25 (lexical) and metadata
matching in src/tools/retrieval_tool.py, not a replacement for either.

WHY LOCAL, NOT A HOSTED API: the LLM gateway this project is configured
against (tokenharbor.ai) has zero embedding models among its ~34 available
models -- checked directly, not assumed. Adding a second provider just for
embeddings means a new account/key/cost; a local model keeps this within
the existing single-key setup at the cost of a real, measured RAM/dependency
footprint instead. See docs/DESIGN_DECISIONS.md for the full trade-off,
including real numbers (not estimates): ~332MB process RSS once the model
is loaded (vs ~44MB for the rest of this app), ~11.6s cold boot (first run,
downloads the ~196MB model from Hugging Face Hub), ~0.46s warm boot
(subsequent runs, model cached locally), ~4ms per document/query embedded.

WHY GRACEFUL DEGRADATION, NOT A HARD DEPENDENCY: `fastembed` is optional
(pyproject.toml `embeddings` extra) -- if it isn't installed, or the model
fails to load for any reason (no network on first run, disk space, etc.),
retrieval silently falls back to BM25 + metadata only (the system's
original, fully offline-testable behavior). tests/test_pipeline.py never
requires this module to be importable.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Optional

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # smallest fastembed-supported model: 384 dims, ~67MB
ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = ROOT / "data" / "unstructured" / "embeddings_cache.json"

_MODEL = None  # lazy-loaded singleton -- paid for once per process, not per query/user


def embeddings_available() -> bool:
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    global _MODEL
    if _MODEL is None:
        from fastembed import TextEmbedding
        _MODEL = TextEmbedding(model_name=MODEL_NAME)
    return _MODEL


def embed_texts(texts: list[str]) -> Optional[list[list[float]]]:
    """Returns one embedding vector per input text, or None if embeddings
    are unavailable for any reason (not installed, model failed to load) --
    callers must treat None as "fall back to lexical-only", never raise."""
    if not texts:
        return []
    try:
        model = _get_model()
        return [list(map(float, v)) for v in model.embed(texts)]
    except Exception:
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def load_cached_document_embeddings(doc_ids: list[str]) -> Optional[dict[str, list[float]]]:
    """Loads the precomputed corpus embeddings (built by
    scripts/generate_embeddings.py) if the cache exists AND covers exactly
    this document set -- a stale/partial cache (corpus regenerated since)
    is treated as unavailable rather than silently used incorrectly."""
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("model") != MODEL_NAME:
        return None
    vectors = data.get("vectors", {})
    if set(vectors.keys()) != set(doc_ids):
        return None
    return vectors
