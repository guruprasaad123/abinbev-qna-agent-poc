# Cost, Latency, and Model-Usage: Point of View

This is written to be defensible in an interview setting: what the system
actually costs and how fast it actually is (structurally measured), combined
with current public model pricing (which will drift — treat the dollar
figures as illustrative, the *call-count structure* as the real finding).

**For real, measured numbers from an actual run with a live model**, see the
output of notebook cell §18 (`GLOBAL_USAGE.summary()`) after running
`notebooks/demo.ipynb` with a real API key — every number below the
"structural" ones is empirically derived from that instrumentation
(`src/llm_client.py::UsageTracker`), not estimated after the fact.

## 1. Call structure per turn (measured, not estimated)

Running the full 25-turn notebook against `MockLLMClient` (zero cost, but
identical control flow to a real run) produced this call profile:

| Caller | Calls | Share of total calls |
|---|---|---|
| `orchestrator_nlu` (router model) | 30 | 35% |
| `orchestrator_synthesis` (router model) | 26 | 30% |
| `structured_agent` (worker model, NL→SQL) | 24 | 28% |
| `memory_summarizer` (worker model) | 5 | 6% |
| `coding_agent` (worker model) | 1 | 1% |
| **Total** | **86** | over 25 user turns → **~3.4 LLM calls/turn** |

This confirms the design's shape: **every** turn costs at least 1 call
(NLU), a **data-bearing** turn costs ~3 (NLU + one worker retrieval call +
synthesis), and only a minority of turns pay for anything extra (retry,
summarization, coding). Notably, `unstructured_agent` and `websearch_agent`
make **zero** LLM calls of their own (retrieval/search only) — hybrid
retrieval is "free" on top of a structured query in terms of LLM cost.

## 2. Two-tier model routing: the actual cost lever

`src/llm_client.py::get_llm_client(role=...)` splits calls into:
- **`router`** (NLU, synthesis, validation-retry): needs reliable
  instruction-following, JSON-mode compliance, multilingual handling, and
  combining several evidence sources into coherent prose. This is where
  answer quality is won or lost.
- **`worker`** (NL→SQL generation, code-snippet generation, memory
  summarization): narrow, close-to-templated tasks against a small, fixed
  schema. A much cheaper/faster model does this reliably.

Using illustrative public per-million-token pricing (`PRICING_PER_MTOK_USD`
in `llm_client.py`; verify against current provider pricing pages before
using this for a real budget):

| Role | Example tier | Input $/Mtok | Output $/Mtok |
|---|---|---|---|
| router | "Sonnet-class" | $3.00 | $15.00 |
| worker | "Haiku-class" | $0.80 | $4.00 |

**Worked example — a single structured-data query** ("What was Corona's
net revenue in the United States in 2025?"), using representative
token counts from the actual system prompts in this repo:

| Call | Model tier | Input tok | Output tok | Cost |
|---|---|---|---|---|
| NLU | router | ~900 | ~150 | $0.0050 |
| NL→SQL | worker | ~500 | ~50 | $0.0006 |
| Synthesis | router | ~1,200 | ~300 | $0.0081 |
| **Total** | | | | **≈ $0.014 / query** |

If the worker call instead ran on the router tier (no two-tier split), that
one call alone would cost ~3.75× more ($0.0023 vs $0.0006) — small in
isolation, but it's ~28% of all calls in the measured profile above, so at
volume (thousands of queries/day) the split is a real line item, not a
rounding error, with no measured accuracy cost on a narrow templated task
like NL→SQL against a fixed 4-table schema.

**Recommendation**: do not default everything to the strongest available
model. Reserve the top reasoning tier ("Opus-class") for neither role in
this system — the domain is bounded (8 KPIs, 8 brands, 8 countries, one
schema) and doesn't need frontier multi-step reasoning; spending there would
inflate cost with little measurable quality gain for this task shape. Revisit
if the domain grows to open-ended, ambiguous multi-hop reasoning.

## 3. Latency: where the time actually goes

Sub-agent *tool* latency is negligible: SQLite queries and BM25 search both
run in low single-digit milliseconds locally. **All meaningful latency is
LLM round-trips**, executed **sequentially** in the current implementation:

```
NLU (router, ~1-2s) → sub-agent LLM call(s) (worker, ~0.5-1s each) → synthesis (router, ~2-4s)
```

A simple structured query: **~4-7s end-to-end** (2 router calls + 1 worker
call). A hybrid query (structured + unstructured) costs **the same LLM
latency** as a plain structured query, because the unstructured sub-agent
does no LLM call of its own — only the *synthesis* call gets a bigger prompt
(more evidence to read), which adds output tokens but not another round-trip.

**The one latency decision we'd change first with more time**: sub-agent
calls are independent of each other (structured SQL-gen, unstructured
retrieval, and web search don't depend on each other's output) but run
sequentially in `Orchestrator.handle_turn()`. Parallelizing them
(asyncio/threading) would collapse a 4-sub-agent hybrid query's latency down
to roughly `NLU + max(sub-agent latencies) + synthesis` instead of `NLU +
sum(sub-agent latencies) + synthesis` — for a worst-case 4-sub-agent turn,
that's the difference between ~4 sequential legs and effectively 2. Not
implemented here in the interest of keeping the control flow simple and
reviewable under a hard deadline (see `docs/DESIGN_DECISIONS.md` §11).

**Retry path**: `_needs_retry` fires only when the numeric-overlap check
fails (in practice, rare) and costs one extra router round-trip (~2-4s) when
it does. **Memory summarization**: one extra worker round-trip (~0.5-1s),
amortized over ~7-turn windows, not on every turn.

## 4. Conversation memory: cost/latency shape over a long session

Without any memory optimization, a naive implementation resends the entire
raw transcript as context on every turn: turn *N*'s prompt grows
**O(N)**, and total tokens spent across an *N*-turn session grow **O(N²)**.
`ConversationMemory.summarize_overflow()` (src/memory.py) caps the raw window
at `RECENT_TURNS_KEPT` (6) and folds anything older into a single rolling
summary, capping each turn's context contribution at roughly **O(1)** and
total session cost at **O(N)** — linear instead of quadratic. This is the
concrete reason "conversation memory optimization for long-running sessions"
is a cost control, not just a UX nicety: on a 50-turn session the difference
between O(N) and O(N²) context tokens is the difference between a
predictable per-turn cost and one that keeps climbing.

## 5. Further optimizations we identified but did not implement

- **Prompt caching** for the static portion of the NLU/synthesis system
  prompts (the schema, KPI catalog, brand/country lists never change turn to
  turn) — most providers offer cache pricing well below standard input
  pricing for a repeated prefix; this system prompt is 100% cacheable and
  currently isn't cached. Straightforward to add through the same
  `LLMClient` abstraction without touching the orchestrator.
- **Parallel sub-agent execution** (§3 above).
- **Streaming** the synthesis call's output to the user instead of waiting
  for the full response — doesn't reduce cost, but materially improves
  *perceived* latency, which matters more than raw latency for a chat UX.

## 6. Honest caveat

Every dollar figure above is **illustrative** (public list pricing at time
of writing, which will change) applied to **measured call-count/shape**
data. The call-count structure (§1) is the durable finding; re-derive the
dollar/second figures against current pricing and a real model's actual
observed latency (via `GLOBAL_USAGE.summary()` after a real run) before
citing this as a production budget.
