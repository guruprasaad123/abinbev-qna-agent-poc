# AB InBev Q&A Agent (Prototype)

A multi-agent enterprise Q&A prototype over Anheuser-Busch InBev's **real,
publicly disclosed** financial results: one orchestrator agent backed by
four specialist sub-agents (structured data, unstructured documents,
internet search, coding), answering natural-language questions with
citations, safety controls, and transparent limitations.

Built as a take-home assignment. See `docs/` for the full design writeup and
`notebooks/demo.ipynb` for a prerun demo covering every required capability.

## What's here

- **AB InBev's real results, not synthetic data.** Every figure in
  `data/db/ab_inbev.db` is transcribed from AB InBev's own quarterly/annual
  BusinessWire results releases and SEC filings, cited by source and URL —
  see `docs/DESIGN_DECISIONS.md` §1 for the full rationale and what real
  disclosure limits versus a synthetic dataset. Structured grain: 5 real
  reporting zones (North America, Middle Americas, South America, EMEA,
  Asia Pacific) × quarter (Q1 2024–Q4 2025) or year (FY2022–FY2025), across
  6 KPIs (revenue, volume, normalized EBITDA, EBITDA margin, organic revenue
  growth, net profit). There is deliberately NO brand-level or country-level
  structured data — AB InBev doesn't disclose that granularity publicly.
- **15 real, sourced documents** (earnings commentary, filing excerpts,
  brand/country color, competitor landscape) — each a short analyst brief
  citing its real AB InBev source, carrying the country- and brand-level
  detail (e.g. Brazil's volume trend, Corona's growth outside Mexico) that
  has no structured-data equivalent (`data/unstructured/`).
- **One orchestrator agent** (`src/orchestrator.py`) that understands intent,
  maintains conversation memory, routes to sub-agents, validates/retries, and
  synthesizes a final formatted answer.
- **Four sub-agents**: structured SQL retrieval (with SQL-injection-resistant
  safety controls), unstructured document retrieval (BM25 + metadata/tag/
  recency filtering, with citations), web search (pluggable, graceful
  degradation), and sandboxed Python code execution.
- **24 offline tests** (`tests/test_pipeline.py`) that run against a
  zero-cost, zero-network mock LLM — no API key required to verify the
  system's plumbing.
- **185 real-LLM capability tests** (`tests/live/`, 8-10 per required
  capability) — a deliberately separate, opt-in suite (see Quickstart) that
  exercises every one of the 25 required capabilities against an actual
  model, with per-capability notebooks under `notebooks/capabilities/`.
- **Full documentation** in `docs/`: architecture, design decisions/trade-offs
  (including the real-vs-synthetic-data decision), a capability-by-capability
  mapping to code, and a cost/latency/model-usage point of view.

## Quickstart

### Option A: plain Python

```bash
git clone <this-repo-url>
cd fmcg-qna-agent

# (Re)build the datasets from the curated real figures/documents —
# deterministic, no network needed, no dependencies needed.
python3 scripts/generate_structured_data.py
python3 scripts/generate_documents.py

# Run the offline test suite (no API key needed).
python3 -m unittest discover -s tests -v

# Try it from the terminal (defaults to a zero-cost mock LLM if no key is set).
python3 scripts/chat_cli.py

# Or run it "for real" with an actual model -- export the vars, or put them
# in a .env file (auto-loaded if python-dotenv is installed). A real
# exported environment variable always takes priority over .env; .env only
# fills in whatever isn't already set in the shell:
export LLM_PROVIDER=anthropic            # or: openai
export ANTHROPIC_API_KEY=sk-...          # or: export OPENAI_API_KEY=sk-...
python3 scripts/chat_cli.py

# Full demo + capability checklist, as a notebook:
pip install jupyter
jupyter notebook notebooks/demo.ipynb    # Restart Kernel & Run All

# Optional, separate: 185 real-LLM tests covering all 25 required
# capabilities in depth (needs a real key/`.env` -- costs real tokens and
# takes real wall-clock time, NOT part of the fast offline suite above).
# This also auto-regenerates reports/capability_test_report.html (a single
# self-contained visual status page -- open it in any browser) and re-runs
# the free offline suite for a fresh number, every time -- no separate step:
python3 scripts/run_live_capability_tests.py
python3 scripts/run_live_capability_tests.py --capability 9   # just one, e.g. SQL safety
# then, to render the results as per-capability/high-level notebooks:
python3 scripts/build_capability_notebooks.py
python3 scripts/build_high_level_notebooks.py
```

Install only the extras you actually need — see `requirements.txt` for exactly which
package each capability requires and why.

### Option B: uv (one command, no manual installs)

`pyproject.toml`/`uv.lock` pin every optional dependency (LLM SDKs, notebook, web search) as a
dev-convenience group, so [uv](https://docs.astral.sh/uv/) installs everything automatically:

```bash
git clone <this-repo-url>
cd fmcg-qna-agent

uv run python3 scripts/generate_structured_data.py
uv run python3 scripts/generate_documents.py
uv run python3 -m unittest discover -s tests -v
uv run python3 scripts/chat_cli.py        # set LLM_PROVIDER/*_API_KEY (or .env) first for real answers
uv run jupyter notebook notebooks/demo.ipynb
```

---

Either way, the core runtime (`src/`) has **zero required third-party dependencies** (pure
Python standard library) — see `docs/DESIGN_DECISIONS.md` for why. Only the LLM provider SDK
(`anthropic` or `openai`) and, optionally, `duckduckgo-search`/`requests` for the web-search
sub-agent, are needed beyond that — `pyproject.toml`'s base `dependencies` list is empty for
exactly this reason; everything else lives in `[project.optional-dependencies]` / the `dev`
dependency group.

**Optional: semantic document retrieval.** `src/tools/retrieval_tool.py` blends BM25 +
metadata with an optional local-embedding similarity signal — off by default (falls back to
BM25 + metadata only, the original behavior), since the model adds a real, measured ~288MB of
process memory (see `docs/DESIGN_DECISIONS.md` §6 for the full cost/benefit, including a real
before/after example). Deliberately **not** in `requirements.txt` (which a default Streamlit
Community Cloud deploy installs unconditionally, with no concept of "optional") — enable it by
adding `requirements-embeddings.txt`'s contents, or `uv sync --extra embeddings` locally, then
`python3 scripts/generate_embeddings.py` (or just use the committed
`data/unstructured/embeddings_cache.json`, already generated).

## Repository structure

```
src/
  config.py              # single source of truth: zones, countries, brands, KPIs, aliases
  llm_client.py          # pluggable LLM client (Anthropic/OpenAI/Mock) + usage tracker
  memory.py              # conversation memory: active filters + rolling summary
  formatting.py          # markdown tables, unit-aware number formatting
  orchestrator.py        # main agent: NLU, routing, synthesis, validation/retry
  tools/
    sql_tool.py          # safe, read-only, whitelisted SQL execution
    retrieval_tool.py     # BM25 + metadata/tag/recency + optional semantic document retrieval
    embedding_tool.py      # optional local embedding model (graceful degradation if absent)
    web_search_tool.py    # pluggable internet search (Tavily / DuckDuckGo / degraded)
    code_tool.py           # sandboxed Python execution
    bm25.py                # dependency-free BM25 implementation
  agents/
    structured_agent.py    # NL -> validated SQL -> rows
    unstructured_agent.py  # NL -> filtered document retrieval
    websearch_agent.py     # NL -> web search results
    coding_agent.py         # NL -> sandboxed calculation
ui/app.py                      # Streamlit developer-mode UI (see Quickstart)
scripts/
  generate_structured_data.py  # builds data/db/ab_inbev.db from real, cited figures
  generate_documents.py        # builds data/unstructured/*.md + manifest.json (real, cited)
  generate_embeddings.py       # optional: builds data/unstructured/embeddings_cache.json
                                #   (needs the `embeddings` extra -- see Quickstart)
  build_notebook.py            # builds notebooks/demo.ipynb
  build_capability_notebooks.py # renders notebooks/capabilities/ from a live test run's report
  build_high_level_notebooks.py # renders notebooks/high_level/ (6 cluster rollups)
  build_test_report.py         # renders reports/capability_test_report.html (visual status page)
  run_live_capability_tests.py # CLI for tests/live/ (progress output, --capability filter,
                                #   auto-regenerates the HTML report when it finishes)
  chat_cli.py                  # interactive terminal chat
data/
  db/ab_inbev.db                # real, cited structured dataset
  unstructured/*.md            # real, cited document corpus + manifest.json
  unstructured/embeddings_cache.json  # precomputed corpus embeddings (optional signal, see above)
requirements-embeddings.txt    # optional -- NOT auto-installed by requirements.txt, see above
notebooks/
  demo.ipynb                   # prerun demo covering every required capability, end-to-end
  capabilities/<NN>_<slug>/demo.ipynb  # one notebook per capability, built from tests/live/ results
  high_level/<slug>/demo.ipynb # one notebook per enterprise domain cluster (rollup over the above)
reports/capability_test_report.html  # single-page visual test status (see build_test_report.py)
tests/
  test_pipeline.py             # offline test suite (mock LLM, no API key needed)
  live/                        # real-LLM capability suite (opt-in, see Quickstart)
    runner.py                  # Case/run_case + reusable assertion helpers
    cases/cap01..cap25_*.py    # 185 cases, one file per required capability
    reports/cap*.json          # captured results from the most recent live run per capability
    live_capabilities_suite.py # unittest suite (NOT auto-discovered -- see docs/DESIGN_DECISIONS.md §4)
  high_level/                  # 6-cluster rollup over the 25 capabilities (clusters.py, rollup.py)
docs/
  ARCHITECTURE.md              # system diagram + request flow
  DESIGN_DECISIONS.md          # why it's built this way (incl. real-vs-synthetic data), and what we'd change
  CAPABILITY_MAPPING.md        # every required capability -> exact code location
  COST_LATENCY_TRADEOFFS.md    # cost / latency / model-usage point of view
progress/                      # dated development log (what changed, why, and what was verified)
pyproject.toml, uv.lock, .python-version   # optional uv-based setup (see Quickstart Option B)
```

## Required capabilities

All 25 capabilities listed in the assignment are implemented; see
[`docs/CAPABILITY_MAPPING.md`](docs/CAPABILITY_MAPPING.md) for the full
table mapping each one to its exact implementation, and
[`notebooks/demo.ipynb`](notebooks/demo.ipynb) for each one exercised live.

## Known limitations

Documented candidly, not hidden. The biggest one: **structured data has no
brand-level, country-level, or channel-level rows** — AB InBev doesn't
publicly disclose that granularity, so those questions route to document
retrieval instead, with an explicit note (see
[`docs/DESIGN_DECISIONS.md` §1](docs/DESIGN_DECISIONS.md#1-real-ab-inbev-data-not-a-synthetic-company--and-what-that-trades-away)
for the full trade-off, and §12 for how this closes in production with
licensed/internal data). Beyond that, see
[`docs/DESIGN_DECISIONS.md` §11](docs/DESIGN_DECISIONS.md#11-what-we-would-change-with-more-time-explicit-not-hidden)
for the rest: sub-agent calls run sequentially rather than in parallel;
retrieval is lexical (BM25) + metadata, not embedding-based semantic search;
the code sandbox is prototype-grade, not hardened for untrusted multi-tenant
use; and the web-search sub-agent depends on an optional external
provider/package.

## License

MIT — see [LICENSE](LICENSE).
