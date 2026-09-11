# Architecture

## System overview

```
                              ┌─────────────────────────────┐
                              │           USER               │
                              └───────────────┬──────────────┘
                                              │ natural language (any language)
                                              ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                  │
│                        (src/orchestrator.py)                              │
│                                                                             │
│  1. ConversationMemory.add_turn()          -- record the turn             │
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
│ solara_fmcg.db │ │ documents + │ │  internet  │          │
│ (fact_monthly_ │ │ manifest.   │ │ (optional) │          │
│ kpi + dims)    │ │ json        │ │            │          │
└───────────────┘ └─────────────┘ └────────────┘          │
                                                    (no external data;
                                                     pure computation)
```

All four sub-agents share one `LLMClient` abstraction (`src/llm_client.py`) that
is swappable between Anthropic, OpenAI, and a dependency-free `MockLLMClient`
used for offline testing (`tests/test_pipeline.py`), and one `UsageTracker`
that records every call's tokens/latency/estimated cost — this is what makes
`docs/COST_LATENCY_TRADEOFFS.md` real numbers rather than guesses.

## Request flow, step by step

1. **User message arrives** → `Orchestrator.handle_turn(text)`.
2. **NLU pass** (`_run_nlu`): one LLM call, JSON-mode, given the schema/KPI/
   entity catalogs plus the current `ConversationMemory.context_block()`
   (rolling summary + active filters). Returns intent, detected language,
   extracted/aliased entities, an explicit clarification flag+question when
   needed, any entities that aren't in Solara's known lists, and which
   sub-agents are needed.
3. **Fast paths** for `greeting` / `capability_intro` / `out_of_scope` /
   `metadata_discovery` / `clarification_needed` answer immediately without
   touching any sub-agent — cheap and instant.
4. **Hierarchy fallback** (`_hierarchy_fallback_notes`): any city named by the
   user is resolved to its country (structured data's actual grain) with an
   explicit note; anything not in Solara's tracked brands/countries at all
   (e.g. a competitor) is flagged as unsupported, also explicitly.
5. **Routing**: the NLU's `needed_subagents` list (which can contain more than
   one — this is what makes retrieval "hybrid") drives which of the four
   sub-agent calls below actually run. Each sub-agent call is given the
   current `context_block()` so a follow-up question inherits prior filters.
6. **Synthesis**: one LLM call combines every evidence block (a markdown
   table for structured rows, cited excerpts for documents, web snippets,
   code results) into the final answer, in the user's own language, with
   inline `[DOC-xxx]` citations and explicit callouts for any assumption or
   limitation collected along the way.
7. **Validation/retry**: `_needs_retry` extracts every number the drafted
   answer states and checks what fraction also appears somewhere in the
   retrieved evidence text. Below a 50% overlap threshold, one corrective
   synthesis call is issued with the failure made explicit ("figures not
   found in the evidence — rewrite using only the numbers above").
8. **Follow-up suggestions**: template-based, derived from which
   dimensions/KPIs are and aren't yet present in the active filters (e.g. a
   single-KPI question suggests a second KPI; a single-period question
   suggests a YoY comparison).
9. **Memory update**: the turn is appended; if raw history exceeds the
   summarization threshold, the oldest turns are compressed into a rolling
   summary by one more (small, cheap) LLM call, bounding prompt growth in
   long sessions.

## Data model

- **Structured**: one SQLite DB (`data/db/solara_fmcg.db`), one fact table
  (`fact_monthly_kpi`, grain = brand × country × channel × month) plus three
  dimension tables. See `scripts/generate_structured_data.py` and
  `src/tools/sql_tool.py::schema_description()`.
- **Unstructured**: 28 generated markdown documents across 6 source types
  (press release, earnings commentary, market research, sustainability,
  competitor intel, strategy memo), indexed by `data/unstructured/
  manifest.json` with per-doc tags/brands/countries/date. See
  `scripts/generate_documents.py`.
- **Single source of truth**: `src/config.py` defines every brand, country,
  channel, KPI, and alias exactly once; both generators import from it, which
  is what guarantees the structured and unstructured corpora describe the
  *same* entities rather than two independently-invented worlds.
