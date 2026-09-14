# Design Decisions & Trade-offs

This document explains *why* the system is built the way it is, including constraints that shaped it and what a production enterprise version would evolve. Read alongside `docs/ARCHITECTURE.md` (system layout) and `docs/COST_LATENCY_TRADEOFFS.md` (cost and latency analysis).

## 1. Grounded in FMCG Giant Anheuser-Busch InBev (AB InBev)

The assignment requires an enterprise Q&A prototype over an FMCG company. We centered this solution directly on **Anheuser-Busch InBev (AB InBev)**, the world's largest brewing company. Grounding the agent in AB InBev's real business architecture provides authentic commercial context:
- **Portfolio Architecture**: Global Megabrands (Corona, Stella Artois, Budweiser, Michelob ULTRA), regional champions (Brahma in Latin America, Bud Light in North America), specialty craft (Hoegaarden), and high-growth Beyond Beer moderation (Corona Cero 0.0%, official Worldwide Olympic Partner).
- **Digital B2B Ecosystem (BEES)**: Incorporating AB InBev's proprietary B2B marketplace platform (BEES), which serves over 3.2 million active monthly retailers and generates >$35B in annualized GMV.
- **Reporting Hierarchy**: Regional zones (North America, Middle Americas, South America, Europe, APAC) with country-grain facts and city-level entity rollup.

## 2. Generation-Time Overlap and 100% Reproducibility

The assignment requires overlapping entities and themes across datasets and documents. Rather than generating structured facts and unstructured documents independently:
- Both generators import from a single source of truth (`src/config.py`).
- Synthetic datasets use explicit, fixed random seeds (`random.seed(42)`) to ensure **100% deterministic reproducibility** across evaluation runs.
- The document generator organizes 28 documents into 10 cohesive corporate storylines (e.g. Corona Cero Olympic rollout, BEES marketplace adoption, water watershed restoration in Monterrey and Leuven, Michelob ULTRA active-lifestyle expansion).
- Several documents pull **live quantitative figures** directly from `data/db/abinbev.db` at generation time (such as YoY growth, market share %, and ACV reach). This allows the agent's hybrid retrieval and answer validation capabilities to be meaningfully evaluated.

## 3. Custom Lightweight Orchestration, Not a Heavy Agent Framework

We avoided heavy agent frameworks (LangGraph, CrewAI, AutoGen). A clean, modular orchestrator (`src/orchestrator.py`) with a readable `handle_turn()` lifecycle provides:
- Complete auditability and zero external dependency risk.
- Deterministic guardrails (NLU intent check, alias resolution, city $\rightarrow$ country rollup) before calling sub-agents.
- Fast execution and simple line-by-line review.

*Production follow-up*: A production enterprise implementation would add parallelized sub-agent execution (`asyncio.gather`) and streaming response tokens.

## 4. Pluggable Client with Two-Tier Token Harbor Model Routing

All LLM calls flow through `src/llm_client.py`:
- Automatically loads credentials from `.env` (`TOKEN_HARBOR_API_KEY=thk_live_...`, OpenAI, Anthropic, or Mock).
- Supports **Token Harbor** (`https://tokenharbor.ai/v1`) using an intelligent two-tier allocation:
  - **Router Model (`deepseek-v4.1-flash:free`)**: With an Intelligence Index of 39.5 (Rank #21), this higher-reasoning tier is allocated to NLU classification, multi-evidence synthesis, and hallucination retry prompts where instruction-following and citation fidelity matter most.
  - **Worker Model (`deepseek-v4-flash:free`)**: With an Intelligence Index of 35.0 (Rank #32) and unconstrained rate limits, this model handles high-volume, templated tasks (NL-to-SQL generation and conversation memory summarization). This prevents burning through the stricter rate limits of V4.1.
- Includes graceful error-handling: on invalid/revoked keys or network outage, seamlessly falls back to the deterministic offline mock engine (`MockLLMClient`) to prevent session crashing.
- Centralized usage telemetry (`GLOBAL_USAGE`) tracks tokens, latency, and estimated cost across all router and worker calls.

## 5. SQL Safety: Whitelist, Not Blacklist

`src/tools/sql_tool.py`:
- Opens the SQLite database in strict **read-only** mode (`file:...mode=ro`).
- Enforces a single-statement `SELECT` whitelist, rejecting stacked queries (`;`), DDL/DML keywords (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`), and unrecognized tables.
- Automatically caps returned rows (`LIMIT 500`) to prevent context window overflow.
- Employs a SQLite step-budget progress handler to terminate runaway queries.

## 6. Self-Contained Hybrid Document Retrieval (BM25 + Metadata)

Document retrieval in `src/tools/retrieval_tool.py` combines:
1. **BM25 lexical scoring** over title and body text (implemented without third-party dependencies in `src/tools/bm25.py`).
2. **Metadata filtering & scoring** matching brands, countries, and document tags.
3. **Recency decay boost** prioritizing newer announcements and earnings releases.

*Production follow-up*: In production, dense vector embeddings with cross-encoder reranking would be layered on top of BM25 for deeper semantic paraphrase matching.

## 7. Sandboxed Python Code Execution

The Coding Sub-Agent (`src/tools/code_tool.py`) handles derived calculations (CAGR, multi-year multiples):
- Restricted execution environment: `__builtins__` stripped of filesystem, import, and network operations; safe modules (`math`, `statistics`, `datetime`) injected directly.
- Hard wall-clock timeout via `SIGALRM` (5 seconds).
- Generated code is displayed alongside computed results for full audit transparency.

## 8. Two-Tier Conversation Memory

`src/memory.py` maintains:
1. `active_filters`: A structured dictionary tracking the brand, market, channel, KPI, and period in focus. This resolves contextual follow-ups ("what about last year?") without reparsing the entire transcript.
2. `raw_turns`: Verbatim recent exchange window.
3. `rolling_summary`: When session length exceeds `SUMMARIZE_TRIGGER_TURNS`, older turns are compressed into a compact summary, bounding token growth from $O(N^2)$ to $O(N)$ in long sessions.

## 9. Deterministic Validation and Retry Mechanism

To prevent hallucinations without incurring a 2x LLM cost on every turn:
- `_needs_retry` performs a deterministic check verifying that numerical claims in the drafted answer match numbers present in the retrieved evidence.
- If overlap is below 50%, a corrective synthesis prompt is triggered, directing the model to rewrite the answer using strictly retrieved figures.

## 10. Web Search with Graceful Degradation

For questions concerning external competitors (Heineken NV, Carlsberg Group, Molson Coors):
- Routes to Tavily (if configured) or free DuckDuckGo search.
- Cleanly silences internal library rename warnings while handling network timeouts.
- If network or provider is unavailable, surfaces a clear, transparent explanation rather than fabricating answers.

## 11. Multimodal Strategy: Why and Where to Deploy MiMo V2.5

Token Harbor provides access to **MiMo V2.5 (`mimo-v2.5:free`)**, an omnimodal model handling text, images, audio, and video with an Intelligence Index of 22.3.
- **Why NOT in Core Text Reasoning**: With an intelligence index of 22.3, deploying MiMo on NLU intent parsing or SQL generation introduces unacceptable risks of malformed JSON or SQL syntax errors compared to DeepSeek V4 (35.0) and V4.1 (39.5).
- **Where MiMo Fits in FMCG / AB InBev Operations**:
  1. **Retail Execution & Cooler Audits (Vision)**: Processing store photos uploaded via the BEES B2B app to calculate facing share (e.g. Corona vs. Heineken shelf presence) and detect promotional compliance.
  2. **PDF Financial Chart Extraction (Vision OCR)**: Inspecting quarterly investor presentation slide graphics and converting non-textual waterfall charts into structured markdown tables for the document index.
  3. **Voice Input for Field Sales Reps (Audio)**: Enabling on-the-road sales and distribution reps to query brand inventory and pricing via voice notes.

## 12. Production Evolution Roadmap

With additional development time:
1. **Parallelized Sub-Agent Calls**: Run structured SQL, unstructured retrieval, and web search concurrently via `asyncio`.
2. **Multimodal Ingestion Pipeline**: Wire MiMo V2.5 to ingest store audit photos and investor presentation slides.
3. **Dense Vector Embeddings**: Integrate an enterprise vector store (e.g. pgvector or Qdrant) with hybrid BM25 search.
4. **Containerized Sandbox**: Run coding execution in ephemeral gVisor/Docker containers with strict cgroups.
5. **Streaming UX**: Stream synthesized answers token-by-token for lower perceived latency.
