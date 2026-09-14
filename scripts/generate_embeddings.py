"""
Precomputes embeddings for the document corpus (data/unstructured/*.md) and
caches them to data/unstructured/embeddings_cache.json, so retrieval never
needs to re-embed the (fixed) corpus at query time -- only the query itself
gets embedded live, per search() call.

Requires the optional `embeddings` extra (`pip install fastembed` or
`uv sync --extra embeddings`). Safe to skip entirely: retrieval_tool.py
falls back to BM25 + metadata only if this cache doesn't exist.

Run: python3 scripts/generate_embeddings.py
Re-run whenever data/unstructured/*.md or manifest.json changes.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOC_DIR = ROOT / "data" / "unstructured"
MANIFEST_PATH = DOC_DIR / "manifest.json"
CACHE_PATH = DOC_DIR / "embeddings_cache.json"


def main():
    from src.tools.embedding_tool import embed_texts, MODEL_NAME, embeddings_available

    if not embeddings_available():
        print("fastembed is not installed -- run `uv sync --extra embeddings` or "
              "`pip install fastembed` first. Retrieval works fine without this "
              "(falls back to BM25 + metadata), this just skips the embedding cache.")
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    docs = manifest["documents"]
    texts = []
    for d in docs:
        body = (DOC_DIR / d["file"]).read_text(encoding="utf-8")
        texts.append(d["title"] + "\n\n" + body)

    print(f"Embedding {len(docs)} documents with {MODEL_NAME}...")
    t0 = time.time()
    vectors = embed_texts(texts)
    elapsed = time.time() - t0
    if vectors is None:
        print("Embedding failed (model load or inference error) -- see traceback above if any.")
        sys.exit(1)

    cache = {
        "model": MODEL_NAME,
        "vectors": {d["doc_id"]: v for d, v in zip(docs, vectors)},
    }
    CACHE_PATH.write_text(json.dumps(cache))
    print(f"Wrote {CACHE_PATH} ({len(docs)} vectors, dim={len(vectors[0])}, {elapsed:.2f}s)")


if __name__ == "__main__":
    main()
