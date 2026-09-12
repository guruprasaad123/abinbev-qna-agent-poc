# Walkthrough: Transitioning FMCG Q&A Agent to AB InBev

The enterprise Q&A prototype has been re-centered around **Anheuser-Busch InBev (AB InBev)** with **100% deterministic reproducibility**, native **Token Harbor** (`https://tokenharbor.ai/v1`) & `.env` integration, and a fully pre-executed demo notebook (`notebooks/demo.ipynb`).

---

## Key Achievements

### 1. Authentic AB InBev Business Domain
- **Portfolio Architecture**:
  - **Premium & Above**: Corona, Stella Artois, Michelob ULTRA, Hoegaarden
  - **Core & Value**: Budweiser, Bud Light, Brahma
  - **Beyond Beer**: Corona Cero 0.0% (official Worldwide Olympic Partner)
- **Geographic Footprint**: United States (St. Louis, New York, Los Angeles), Canada, Mexico (Monterrey, Mexico City), Brazil (Sao Paulo, Rio de Janeiro), United Kingdom (London), Belgium (Brussels, Leuven — global headquarters), China (Shanghai), India (Mumbai, Bengaluru).
- **Commercial Channels**: Modern Trade, Traditional Trade, On-Premise, and the proprietary **BEES & E-commerce** digital marketplace.
- **KPI Catalog**: Net Revenue ($USD), Volume in standard brewing hectoliters (`hL`), Market Share %, Net Revenue per hL (ASP), Distribution ACV / BEES Reach %, Marketing Spend, Promotion Spend, Gross Margin %.

### 2. Deterministic & Reproducible Data Generation
- **Structured SQLite Database** (`data/db/abinbev.db`):
  - Fixed seed (`random.seed(42)`).
  - 11,264 fact rows generated deterministically across 8 brands $\times$ 8 countries $\times$ 4 channels $\times$ 44 months (Jan 2023–Aug 2026).
  - Real-world brewing dynamics: summer seasonality, high growth for Corona Cero & Michelob ULTRA, On-Premise draft premiums, and BEES digital efficiency.
- **28 Corporate Documents & Manifest** (`data/unstructured/`):
  - 10 realistic storylines: Corona Cero Olympic Partnership, BEES B2B digital marketplace, Michelob ULTRA active-lifestyle premiumization, TaDa Delivery D2C cold beer expansion, Monterrey/Leuven water watershed stewardship, Budweiser FIFA World Cup sponsorships, and competitor benchmarking (Heineken, Carlsberg, Molson Coors).
  - Documents query `data/db/abinbev.db` live during generation to ensure qualitative statements match quantitative facts.

### 3. Token Harbor & `.env` Support
- Added automatic `.env` loading from the repo root on startup.
- Configured OpenAI-compatible client for Token Harbor (`https://tokenharbor.ai/v1`) with `api_key=hk_live_...`.
- Implemented cached authentication error handling so that if an API key is revoked or offline, calls seamlessly degrade to the deterministic `MockLLMClient` without repetitive HTTP timeouts or session crashes.

### 4. Prerun Demo Notebook (`notebooks/demo.ipynb`)
- Re-authored all 18 sections / 47 cells around AB InBev scenarios and questions.
- Executed via `ExecutePreprocessor` so that **all 27 functional code cells have rich pre-computed outputs saved directly into the notebook**.
- Demonstrates every single required capability: greeting, capability intro, out-of-scope, metadata discovery, clarification for ambiguous queries, single/multi-turn SQL retrieval with unit-aware tables (`hL`, `$USD`, `%%`), multilingual responses (Spanish, French, Hindi-English), SQL injection safety, hybrid retrieval with citations `[DOC-xxx]`, competitor web search, sandboxed coding for CAGR/multiples, city-to-country rollups, and session memory optimization.

---

## Verification Results

### Unit Tests
```bash
python3 main.py --test
```
**Output**:
```
Ran 19 tests in 0.019s
OK
```
All 19 tests pass, covering:
- SQL safety (read-only, statement whitelist, table whitelist, row caps, step budgets)
- BM25 hybrid document retrieval & metadata filtering
- Code execution sandbox isolation & timeouts
- Orchestrator NLU (greetings, out-of-scope, clarification, metadata discovery)
- City rollup hierarchy fallback (St. Louis $\rightarrow$ United States)
- External competitor detection (Heineken)
- Multi-turn conversation filter persistence

### Notebook Telemetry (Cell §18)
```json
{
  "calls": 86,
  "by_caller": {
    "orchestrator_nlu_mock_fallback": { "calls": 30 },
    "structured_agent_mock_fallback": { "calls": 25 },
    "orchestrator_synthesis_mock_fallback": { "calls": 25 },
    "memory_summarizer_mock_fallback": { "calls": 5 },
    "coding_agent_mock_fallback": { "calls": 1 }
  }
}
```
86 calls across 25 user turns ($\approx 3.4$ calls/turn), perfectly validating the call profile in `docs/COST_LATENCY_TRADEOFFS.md`.
