# Architecture

## System Overview

```
                              ┌─────────────────────────────┐
                              │           USER               │
                              └───────────────┬──────────────┘
                                              │ natural language (any language)
                                              ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                  │
│                        (src/orchestrator.py)                              │
│                                                                           │
│  1. ConversationMemory.add_turn()          -- record user turn            │
│  2. NLU pass (1 LLM call, JSON mode)       -- intent, language, entities, │
│                                                clarification need,        │
│                                                needed sub-agents          │
│  3. Deterministic pre/post-processing:                                   │
│       - alias/typo table (src/config.py ENTITY_ALIASES)                  │
│       - hierarchy fallback (city->country, unsupported-entity flagging)  │
│       - active-filter merge (contextual follow-ups)                      │
│  4. Route to 0-4 sub-agents based on NLU's needed_subagents               │
│  5. Synthesis (1 LLM call)                 -- combine all evidence into  │
│                                                one formatted answer       │
│  6. Cheap deterministic validation check   -- numeric-hallucination scan │
│       -> retry synthesis once if it fails                                │
│  7. Follow-up suggestion generation (rule-based, from active filters)    │
│  8. ConversationMemory.add_turn() + summarize_overflow() if needed       │
└───────┬───────────────┬───────────────┬───────────────┬──────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌───────────────┐ ┌─────────────┐ ┌────────────┐ ┌─────────────┐
│  STRUCTURED    │ │ UNSTRUCTURED│ │    WEB      │ │   CODING    │
│  DATA AGENT    │ │ DATA AGENT  │ │  SEARCH     │ │   AGENT     │
│ (NL -> SQL)    │ │ (BM25+meta) │ │  AGENT      │ │ (sandboxed) │
├───────────────┤ ├─────────────┤ ├────────────┤ ├─────────────┤
│ src/agents/    │ │ src/agents/ │ │ src/agents/│ │ src/agents/ │
│ structured_    │ │ unstructured│ │ websearch_ │ │ coding_     │
│ agent.py       │ │ _agent.py   │ │ agent.py   │ │ agent.py    │
│       │        │ │      │      │ │     │      │ │      │      │
│       ▼        │ │      ▼      │ │     ▼      │ │      ▼      │
│ sql_tool.py    │ │ retrieval_  │ │ web_search_│ │ code_tool.py│
│ (safety-       │ │ tool.py     │ │ tool.py    │ │ (restricted │
│  validated,    │ │ (BM25 +     │ │ (Tavily /  │ │  exec,      │
│  read-only)    │ │  metadata   │ │  DuckDuckGo│ │  timeout)   │
│                │ │  filtering) │ │  /degraded)│ │             │
└───────┬───────┘ └──────┬──────┘ └─────┬──────┘ └──────┬──────┘
        ▼                ▼               ▼                │
┌───────────────┐ ┌─────────────┐ ┌────────────┐          │
│ SQLite:        │ │ 28 markdown │ │  public    │          │
│ abinbev.db    │ │ documents + │ │  internet  │          │
│ (fact_monthly_ │ │ manifest.   │ │ (optional) │          │
│ kpi + dims)    │ │ json        │ │            │          │
└───────────────┘ └─────────────┘ └────────────┘          │
                                                    (pure derived
                                                     computation)
```

All four sub-agents share one `LLMClient` abstraction (`src/llm_client.py`) that is swappable between Token Harbor, OpenAI, Anthropic, and a dependency-free `MockLLMClient` used for offline testing (`tests/test_pipeline.py`), and one `UsageTracker` that records every call's tokens, latency, and estimated cost — powering `docs/COST_LATENCY_TRADEOFFS.md` with measured telemetry.

## Request Flow, Step by Step

1. **User message arrives** $\rightarrow$ `Orchestrator.handle_turn(text)`.
2. **NLU pass** (`_run_nlu`): one LLM call in JSON-mode, given the schema/KPI/entity catalogs plus the current `ConversationMemory.context_block()` (rolling summary + active filters). Returns intent, detected language, extracted/aliased entities, an explicit clarification flag + question when needed, any entities that aren't in AB InBev's known lists, and which sub-agents are needed.
3. **Fast paths** for `greeting` / `capability_intro` / `out_of_scope` / `metadata_discovery` / `clarification_needed` answer immediately without invoking any sub-agent — instant and cost-free.
4. **Hierarchy fallback** (`_hierarchy_fallback_notes`): any city named by the user (e.g. St. Louis, Monterrey, Leuven) is resolved to its country (structured data's actual grain) with an explicit disclosure; anything not in AB InBev's tracked entities at all (e.g. competitor Heineken or Carlsberg) is flagged as external/unsupported.
5. **Routing**: the NLU's `needed_subagents` list (which can contain multiple sub-agents — powering "hybrid retrieval") drives which sub-agent calls run. Each sub-agent call receives the current `context_block()` so follow-ups seamlessly inherit prior conversation dimensions.
6. **Synthesis**: one LLM call combines all retrieved evidence blocks (markdown table for structured rows, cited excerpts for documents, web snippets, code execution results) into a unified final answer in the user's language, with inline `[DOC-xxx]` citations and explicit callouts for any assumptions or limitations.
7. **Validation / Retry**: `_needs_retry` extracts every standalone number from the drafted answer and verifies what fraction appears in the retrieved evidence text. Below a 50% overlap threshold, one corrective synthesis call is issued with the specific discrepancy explained.
8. **Follow-up suggestions**: rule-based, derived from which dimensions/KPIs are present in active filters versus still unexplored (e.g. suggesting an adjacent brand, YoY comparison, or channel breakdown).
9. **Memory update**: the turn is appended; if raw history exceeds `SUMMARIZE_TRIGGER_TURNS`, older turns are compressed into a rolling summary by a single compact LLM call, bounding prompt token growth in long multi-turn sessions.

## Data Model

- **Structured**: one SQLite DB (`data/db/abinbev.db`), one fact table (`fact_monthly_kpi`, grain = brand $\times$ country $\times$ channel $\times$ month) plus three dimension tables (`dim_brand`, `dim_geo`, `dim_channel`). See `scripts/generate_structured_data.py` and `src/tools/sql_tool.py::schema_description()`.
- **Unstructured**: 28 generated markdown documents across 6 source types (press release, earnings commentary, market research, sustainability, competitor intel, strategy memo), indexed by `data/unstructured/manifest.json` with per-doc tags, brands, countries, and dates. See `scripts/generate_documents.py`.
- **Single Source of Truth**: `src/config.py` defines every brand, country, channel, KPI, and alias exactly once; both generators import from it, guaranteeing that the structured and unstructured corpora describe the *same* entities and cross-validate each other.

## Model Allocation & Intelligence Tiers

To balance cognitive accuracy against provider rate limits, the orchestrator divides work into two distinct LLM tiers:

| Tier | Model in `.env` | Intelligence Index | Responsibilities |
|---|---|---|---|
| **Router Tier** | `deepseek-v4.1-flash:free` | **39.5** (Rank #21) | • NLU intent classification & multi-agent routing<br>• Ambiguous query clarification generation<br>• Multi-source evidence synthesis with inline citations<br>• Corrective synthesis retry upon numeric mismatch |
| **Worker Tier** | `deepseek-v4-flash:free` | **35.0** (Rank #32) | • Natural Language $\rightarrow$ SQL query generation against fixed 4-table schema<br>• Conversation transcript summarization (`memory_summarizer`)<br>• Sandboxed Python snippet generation (`coding_agent`) |

*Rationale*: High-volume, narrow tasks run on unconstrained V4, while scarce V4.1 quota is preserved exclusively for nuanced reasoning and answer synthesis.

## Multimodal Architectural Extension (MiMo V2.5)

For omnimodal enterprise scenarios, Token Harbor's **MiMo V2.5 (`mimo-v2.5:free`)** (Intelligence Index 22.3, text/image/audio/video) is decoupled from text reasoning and allocated to field ingestion:
1. **BEES Retail Cooler Audits**: Ingesting store photos to calculate cooler facing share and tap handle compliance.
2. **Investor Presentation OCR**: Converting graphic-heavy earnings slides into structured tables for the BM25 index.
3. **Field Voice Notes**: Transcribing audio dictations from on-the-road sales representatives.
