# Meridian Brewing Group — Enterprise Q&A Agent (Prototype)

A multi-agent enterprise Q&A prototype over a synthetic global brewing
business: one orchestrator agent backed by four specialist sub-agents
(structured data, unstructured documents, internet search, coding),
answering natural-language questions with citations, safety controls, and
transparent limitations.

Built as a take-home assignment. See `docs/` for the full design writeup and
`notebooks/demo.ipynb` for a prerun demo covering every required capability.

## What's here

- **A synthetic FMCG (brewing) company** — Meridian Brewing Group — with 8
  brands across 3 categories / 5 sub-categories (International Premium,
  Craft & Specialty, Mainstream Lager, and a "Beyond Beer" segment of
  Non-Alcoholic and Hard Seltzer), 8 markets, 4 channels, and 8 KPIs,
  generated as a SQLite fact table (`data/db/meridian_brewing.db`, ~11k rows,
  Jan 2023–Aug 2026).
- **28 unstructured documents** (press releases, earnings commentary, market
  research, sustainability updates, competitor intel, strategy memos)
  deliberately overlapping in entities and themes with each other and with
  the structured data (`data/unstructured/`).
- **One orchestrator agent** (`src/orchestrator.py`) that understands intent,
  maintains conversation memory, routes to sub-agents, validates/retries, and
  synthesizes a final formatted answer.
- **Four sub-agents**: structured SQL retrieval (with SQL-injection-resistant
  safety controls), unstructured document retrieval (BM25 + metadata/tag/
  recency filtering, with citations), web search (pluggable, graceful
  degradation), and sandboxed Python code execution.
- **18 offline tests** (`tests/test_pipeline.py`) that run against a
  zero-cost, zero-network mock LLM — no API key required to verify the
  system's plumbing.
- **Full documentation** in `docs/`: architecture, design decisions/trade-offs,
  a capability-by-capability mapping to code, and a cost/latency/model-usage
  point of view.

## Quickstart

```bash
git clone <this-repo-url>
cd fmcg-qna-agent

# (Re)generate the datasets — deterministic, no dependencies needed.
python3 scripts/generate_structured_data.py
python3 scripts/generate_documents.py

# Run the offline test suite (no API key needed).
python3 -m unittest discover -s tests -v

# Try it from the terminal (defaults to a zero-cost mock LLM if no key is set).
python3 scripts/chat_cli.py

# Or run it "for real" with an actual model:
export LLM_PROVIDER=anthropic            # or: openai
export ANTHROPIC_API_KEY=sk-...          # or: export OPENAI_API_KEY=sk-...
python3 scripts/chat_cli.py

# Full demo + capability checklist, as a notebook:
pip install jupyter
jupyter notebook notebooks/demo.ipynb    # Restart Kernel & Run All
```

The system has **zero required third-party dependencies** in its core
runtime (pure Python standard library) — see `requirements.txt` and
`docs/DESIGN_DECISIONS.md` for why. Only the LLM provider SDK
(`anthropic` or `openai`) and, optionally, `duckduckgo-search`/`requests`
for the web-search sub-agent, are needed beyond that.

## Repository structure

```
src/
  config.py              # single source of truth: brands, geo, channels, KPIs, aliases
  llm_client.py          # pluggable LLM client (Anthropic/OpenAI/Mock) + usage tracker
  memory.py              # conversation memory: active filters + rolling summary
  formatting.py          # markdown tables, unit-aware number formatting
  orchestrator.py        # main agent: NLU, routing, synthesis, validation/retry
  tools/
    sql_tool.py          # safe, read-only, whitelisted SQL execution
    retrieval_tool.py     # BM25 + metadata/tag/recency document retrieval
    web_search_tool.py    # pluggable internet search (Tavily / DuckDuckGo / degraded)
    code_tool.py           # sandboxed Python execution
    bm25.py                # dependency-free BM25 implementation
  agents/
    structured_agent.py    # NL -> validated SQL -> rows
    unstructured_agent.py  # NL -> filtered document retrieval
    websearch_agent.py     # NL -> web search results
    coding_agent.py         # NL -> sandboxed calculation
scripts/
  generate_structured_data.py  # builds data/db/meridian_brewing.db
  generate_documents.py        # builds data/unstructured/*.md + manifest.json
  build_notebook.py            # builds notebooks/demo.ipynb
  chat_cli.py                  # interactive terminal chat
data/
  db/meridian_brewing.db           # generated structured dataset
  unstructured/*.md            # generated document corpus + manifest.json
notebooks/demo.ipynb           # prerun demo covering every required capability
tests/test_pipeline.py         # offline test suite (mock LLM, no API key needed)
docs/
  ARCHITECTURE.md              # system diagram + request flow
  DESIGN_DECISIONS.md          # why it's built this way, and what we'd change
  CAPABILITY_MAPPING.md        # every required capability -> exact code location
  COST_LATENCY_TRADEOFFS.md    # cost / latency / model-usage point of view
```

## Required capabilities

All 25 capabilities listed in the assignment are implemented; see
[`docs/CAPABILITY_MAPPING.md`](docs/CAPABILITY_MAPPING.md) for the full
table mapping each one to its exact implementation, and
[`notebooks/demo.ipynb`](notebooks/demo.ipynb) for each one exercised live.

## Known limitations

Documented candidly, not hidden — see
[`docs/DESIGN_DECISIONS.md` §11](docs/DESIGN_DECISIONS.md#11-what-we-would-change-with-more-time-explicit-not-hidden)
for the full list: sub-agent calls run sequentially rather than in parallel;
retrieval is lexical (BM25) + metadata, not embedding-based semantic search;
the code sandbox is prototype-grade, not hardened for untrusted multi-tenant
use; and the web-search sub-agent depends on an optional external
provider/package.

## License

MIT — see [LICENSE](LICENSE).
