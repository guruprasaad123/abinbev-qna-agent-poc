# Anheuser-Busch InBev (AB InBev) — Enterprise Q&A Agent (Prototype)

A multi-agent enterprise Q&A prototype centered on the global brewing giant **Anheuser-Busch InBev (AB InBev)**: one orchestrator agent backed by four specialist sub-agents (structured SQL data, unstructured documents, internet search, and sandboxed Python coding), answering complex natural-language business questions with verified citations, strict SQL safety controls, and transparent reporting of limitations.

Built for the FMCG AI Engineer prototype assignment. See `docs/` for the architecture, design decisions, cost/latency analysis, and `notebooks/demo.ipynb` for a fully prerun demonstration covering all 25 required capabilities.

## What's here

- **Realistic, Reproducible AB InBev Universe** — 8 representative brands across 3 portfolios (**Corona**, **Stella Artois**, **Michelob ULTRA**, **Hoegaarden**, **Budweiser**, **Bud Light**, **Brahma**, and **Corona Cero 0.0%**), 8 major global markets (United States, Canada, Mexico, Brazil, United Kingdom, Belgium, China, India), 4 commercial channels (Modern Trade, Traditional Trade, On-Premise, and the proprietary BEES B2B digital marketplace), and 8 KPIs (Net Revenue, Volume in hectoliters (hL), Market Share %, Net Revenue/hL, Distribution ACV/BEES Reach %, Marketing Spend, Promotion Spend, Gross Margin %). Generated deterministically with a fixed seed as a SQLite database (`data/db/abinbev.db`, 11,264 fact rows, Jan 2023–Aug 2026).
- **28 Unstructured Documents** — Press releases, earnings commentary, market research, sustainability updates, strategy memos, and competitor briefings (Heineken, Carlsberg, Molson Coors) organized into 10 realistic corporate storylines (including the Corona Cero Worldwide Olympic Partnership, BEES digital expansion, and Monterrey/Leuven water watershed stewardship), pulling live quantitative numbers directly from the database at generation time (`data/unstructured/`).
- **One Orchestrator Agent** (`src/orchestrator.py`) — Manages intent validation, entity extraction, alias resolution, multi-turn conversation memory (active filters + rolling summarization), sub-agent routing, hallucination verification (numeric overlap check with retry), and final answer synthesis.
- **Four Specialist Sub-Agents**:
  1. **Structured Data Sub-Agent** (`src/agents/structured_agent.py`): Natural language to validated, read-only SQL with strict safety controls (table whitelist, single-statement enforcement, row caps, execution step budget).
  2. **Unstructured Data Sub-Agent** (`src/agents/unstructured_agent.py`): Hybrid lexical (BM25) + metadata/tag/recency filtering over corporate documents with inline `[DOC-xxx]` citations.
  3. **Internet Search Sub-Agent** (`src/agents/websearch_agent.py`): Pluggable search (Tavily / DuckDuckGo / graceful degradation) for external benchmarking outside AB InBev's internal reporting.
  4. **Coding Sub-Agent** (`src/agents/coding_agent.py`): In-process sandboxed Python execution for derived calculations (CAGR, multi-year projections).
- **340 Offline Tests** (`tests/`) — Comprehensive test coverage across **`tests/high_level/`** (195 tests across 6 domain suites), **`tests/capabilities/`** (124 tests across all 25 individual capability attributes), and **`tests/test_pipeline.py`** (21 regression tests). All pass deterministically in ~9 seconds without requiring API keys or network access.
- **12 Modular Notebooks** (`notebooks/`) — Pre-computed, interactive Jupyter notebooks organized into **`notebooks/high_level/`** (6 domain notebooks) and **`notebooks/capabilities/`** (6 capability notebooks), alongside the master executive showcase in `notebooks/demo.ipynb`.
- **Interactive Streamlit Web UI** (`app.py`) — Executive & Developer Mode interface with real-time agentic step inspection, SQL audit, and session telemetry.
- **Full Documentation** in `docs/`: Architecture diagrams, design trade-offs, capability checklist mapping, and a comprehensive cost/latency/token telemetry analysis.

## Quickstart

```bash
# 1. (Re)generate the datasets — deterministic & 100% reproducible
python3 scripts/generate_structured_data.py
python3 scripts/generate_documents.py

# 2. Run the offline test suites (no API key needed)
python3 main.py --test-all          # Runs all 340 offline tests (~9s)
python3 main.py --test-high-level   # Runs 195 tests in tests/high_level/
python3 main.py --test-capabilities # Runs 124 tests in tests/capabilities/
python3 main.py --test              # Runs 21 regression tests in tests/test_pipeline.py

# 3. Run the live LLM integration tests (uses Token Harbor / OpenAI from .env)
python3 main.py --test-live-html  # Runs 12 live capability tests & outputs live_test_report.html
python3 main.py --test-live       # Standard unittest runner for live tests

# 4. Interactive Web UI (Executive & Developer Mode)
streamlit run app.py

# 5. Interactive CLI chat (auto-loads .env if present; defaults to mock if no key found)
python3 main.py

# 6. Notebooks & capability inspection:
# - Master demo: notebooks/demo.ipynb
# - High-level domain notebooks: notebooks/high_level/ (6 notebooks)
# - Fine-grained capability notebooks: notebooks/capabilities/ (6 notebooks)
```

## Repository Structure

```
src/
  config.py              # single source of truth: AB InBev brands, geo, channels, KPIs, aliases
  llm_client.py          # pluggable LLM client (Token Harbor / OpenAI / Anthropic / Mock) + usage tracker
  memory.py              # conversation memory: active filters + rolling summary
  formatting.py          # markdown tables, unit-aware formatting ($USD, hL volume, %)
  orchestrator.py        # main agent: NLU, routing, synthesis, validation/retry
  tools/
    sql_tool.py          # safe, read-only, whitelisted SQL execution over abinbev.db
    retrieval_tool.py     # BM25 + metadata/tag/recency document retrieval
    web_search_tool.py    # pluggable internet search (Tavily / DuckDuckGo / degraded)
    code_tool.py           # sandboxed Python execution
    bm25.py                # dependency-free BM25 implementation
  agents/
    structured_agent.py    # NL -> validated SQL -> rows
    unstructured_agent.py  # NL -> filtered document retrieval with citations
    websearch_agent.py     # NL -> external search results
    coding_agent.py         # NL -> sandboxed calculation
scripts/
  generate_structured_data.py  # builds data/db/abinbev.db (11,264 fact rows)
  generate_documents.py        # builds data/unstructured/*.md + manifest.json
  build_notebook.py            # builds notebooks/demo.ipynb
  chat_cli.py                  # interactive terminal chat
main.py                        # main entry point for CLI and tests
data/
  db/abinbev.db                # generated structured dataset
  unstructured/*.md            # generated 28-document corpus + manifest.json
notebooks/demo.ipynb           # prerun demo covering all 25 required capabilities
tests/test_pipeline.py         # offline test suite (19 tests)
docs/
  ARCHITECTURE.md              # system diagram + request flow
  DESIGN_DECISIONS.md          # design rationale & architectural trade-offs
  CAPABILITY_MAPPING.md        # every required capability -> exact code location
  COST_LATENCY_TRADEOFFS.md    # cost / latency / model-usage point of view
```

## Required Capabilities

All 25 capabilities listed in the assignment specification are implemented and verified; see [`docs/CAPABILITY_MAPPING.md`](docs/CAPABILITY_MAPPING.md) for the complete traceability matrix and [`notebooks/demo.ipynb`](notebooks/demo.ipynb) for live demonstrations of each capability.

## License

MIT — see [LICENSE](LICENSE).
