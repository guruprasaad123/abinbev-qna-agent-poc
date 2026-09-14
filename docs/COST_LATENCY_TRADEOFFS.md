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
| `orchestrator_nlu` (classify tier) | 30 | 35% |
| `orchestrator_synthesis` (synthesize tier) | 26 | 31% |
| `structured_agent` (generate tier, NL→SQL) | 23 | 27% |
| `memory_summarizer` (generate tier) | 5 | 6% |
| `coding_agent` (generate tier) | 1 | 1% |
| **Total** | **85** | over 25 user turns → **~3.4 LLM calls/turn** |

This confirms the design's shape: **every** turn costs at least 1 call
(NLU/classify), a **data-bearing** turn costs ~3 (classify + one generate-tier
retrieval call + synthesize), and only a minority of turns pay for anything
extra (retry, summarization, coding). Notably, `unstructured_agent` and
`websearch_agent` make **zero** LLM calls of their own (retrieval/search
only) — hybrid retrieval is "free" on top of a structured query in terms of
LLM cost.

## 2. Model-usage architecture: orchestrator + sub-agents + combinator

The mental model the assignment asks for — "orchestrator + subagents +
combinator" — maps onto this codebase as:

```
                         ┌─────────────────────────────────────────┐
 user turn  ──────────▶  │   ORCHESTRATOR  (src/orchestrator.py)    │
                         │                                           │
                         │  1. CLASSIFY  — NLU / intent / entities  │──▶ llm_classify
                         │     (_run_nlu)                            │
                         │                                           │
                         │  2. ROUTE — decide which sub-agents fire │  (no LLM call —
                         │     (needed_subagents from step 1)        │   deterministic)
                         │                                           │
                         │  3. dispatch to SUB-AGENTS (in parallel   │
                         │     if implemented that way — see         │
                         │     docs/DESIGN_DECISIONS.md §11):        │
                         │     ┌─────────────┐ ┌───────────────┐    │
                         │     │structured    │ │unstructured   │    │──▶ llm_generate
                         │     │ NL→SQL       │ │ NL→retrieval  │    │    (each sub-agent's
                         │     │ agent        │ │ query agent   │    │     own narrow call)
                         │     └─────────────┘ └───────────────┘    │
                         │     ┌─────────────┐ ┌───────────────┐    │
                         │     │web search    │ │coding         │    │──▶ llm_generate
                         │     │ agent (no    │ │ agent         │    │    (coding only;
                         │     │ LLM call)    │ │               │    │     web has none)
                         │     └─────────────┘ └───────────────┘    │
                         │                                           │
                         │  4. COMBINATOR — SYNTHESIZE the evidence  │──▶ llm_synthesize
                         │     from every sub-agent that fired into  │
                         │     one answer, cite sources, apply       │
                         │     transparency rules (handle_turn's     │
                         │     synth_prompt + SYNTHESIS_SYSTEM_PROMPT)│
                         │                                           │
                         │  5. VALIDATE — cheap deterministic number- │  (no LLM call unless
                         │     overlap check; retry synthesize once  │   the check fails)
                         │     if the draft looks like it hallucinated│──▶ llm_synthesize (retry)
                         └─────────────────────────────────────────┘
```

The "combinator" is not a separate model or agent — it's the synthesis step
inside the orchestrator that combines whatever the sub-agents returned. It's
called out as its own tier below because it has a distinct cost/quality
profile from classify and generate.

### The three-tier model split (`src/llm_client.py::get_llm_client(role=...)`)

The system used to split calls two ways ("router" vs. "worker"). It's now
split three ways because "router" was quietly bundling two very different
jobs — cheap intent classification and expensive final-answer judgment —
under one model choice:

| Tier | Used by | Call volume | What it actually needs |
|---|---|---|---|
| **`classify`** | orchestrator NLU/intent (`_run_nlu`) | 35% of calls | Reliable structured JSON output against a small fixed schema (5 zones, 6 KPIs, one intent enum). No open-ended reasoning. |
| **`generate`** | structured agent (NL→SQL), unstructured agent (retrieval query), coding agent, memory summarizer | ~34% of calls | Narrow, close-to-templated generation against a small fixed schema/vocabulary. |
| **`synthesize`** | orchestrator combinator (final answer + validation retry) | ~31% of calls (but the *one* users actually read) | Combining multiple evidence sources into fluent, correctly-cited, multi-lingual prose; catching when evidence is thin/contradictory and saying so. This is where perceived answer quality is won or lost. |

**Why split at all, and why three instead of two:** `classify` + `generate`
together are ~69% of call volume in the measured profile above, and neither
needs frontier reasoning — they're bounded, schema-constrained tasks. Routing
both of them to a cheap/fast model, and reserving spend for the ~31% of calls
that are `synthesize`, is the single biggest lever in this system's cost
structure. Splitting `classify` out from `generate` (rather than merging them,
which is also defensible) mostly buys latency headroom and independent
tuning — e.g. you could push `classify` to an even cheaper/faster model than
`generate` if NLU accuracy holds up, without touching NL→SQL quality.

Set independently via three environment variables, so provider/model choice
never requires a code change: `LLM_MODEL_CLASSIFY`, `LLM_MODEL_GENERATE`,
`LLM_MODEL_SYNTHESIZE` (see `src/llm_client.py` module docstring).

### Worked example: spending a quota-limited model where it actually matters

Some free-tier model marketplaces offer a smarter model alongside a regular
one, gated as "limited" (a hard rate/quota cap) — e.g. `deepseek-v4.1-flash`
(higher benchmark intelligence) vs. the always-available `deepseek-v4-flash`.
The three-tier split above makes the placement decision straightforward
rather than a guess: `classify` fires on *every* turn (including greetings)
and only needs reliable schema-following, so it stays on the unlimited
model; `synthesize` fires once or twice per turn but is where answer
*quality* — multilingual fluency, correctly flagging thin/contradictory
evidence, avoiding hallucination — is actually won or lost. That's the one
role worth spending a limited-quota smarter model on:

```
LLM_MODEL_CLASSIFY=deepseek-v4-flash:free      # unlimited, high call volume, low reasoning need
LLM_MODEL_GENERATE=deepseek-v4-flash:free      # unlimited, high call volume, low reasoning need
LLM_MODEL_SYNTHESIZE=deepseek-v4.1-flash:free  # limited quota, spent on the role that most benefits
```

**The risk this creates, and how it's guarded:** a hard quota cap means the
`synthesize` call can legitimately fail mid-session in a way the unlimited
`classify`/`generate` calls won't. Without a guard, that would surface as an
unhandled exception crashing the turn — the same class of failure this
system already hardened against for token-truncation (§1 above).
`AnthropicLLMClient`/`OpenAILLMClient` (`src/llm_client.py`) both catch *any*
API-layer failure on the primary model (not narrowly a 429 rate limit —
this was widened after actually hitting a `402 confidence_level_required`
account-level block from a free gateway mid-session, a different error
class than rate-limiting but the same underlying risk) and retry once
against a configured `fallback_model` — for the `synthesize` role, that
fallback is whatever `generate` is configured to use (the always-available
baseline), wired automatically in `get_llm_client()`. `classify`/`generate`
themselves have no fallback configured, since they're already the baseline
tier — there's nowhere cheaper/more-available to fall back to. Usage/cost
is recorded against whichever model actually served the request, not the
one originally requested, so `GLOBAL_USAGE.summary()` stays accurate even
when a fallback fires.

**And if the fallback ALSO fails** (the account-level block above affected
*every* model on that gateway equally, so the fallback attempt failed too):
the client translates the final failure into one provider-agnostic
`LLMUnavailableError`, and `Orchestrator.handle_turn` (a thin wrapper around
the real turn-handling logic) catches it and returns a plain, honest
"I'm temporarily unable to reach the language model service..." answer
(`AgentResponse.unavailable=True`) instead of propagating an exception —
verified by forcing every underlying API call to fail and confirming
`handle_turn` still returns cleanly rather than crashing the caller (the
Streamlit UI, in the case that actually surfaced this gap). A narrower,
separate guard around the memory-summarization call specifically avoids the
opposite mistake: discarding an already-successfully-synthesized answer
just because the *unrelated*, best-effort summarization call happened to
fail afterward.

### Going further: dynamic per-turn routing *within* the synthesize role

The three-role split (classify/generate/synthesize) is static -- set once via
env vars, same model for every turn. Once a paid pass unlocked several
models at different price/quality points on one account (rather than one
quota-limited model to spend carefully), a further, *dynamic* split became
worth adding: not every `synthesize` call is equally hard, so not every one
should cost the same.

`Orchestrator._classify_complexity()` picks a tier -- `simple` / `moderate` /
`complex` -- per turn, from signals already available after NLU + routing,
with **no extra LLM call**:

| Tier | Trigger | Model (this deployment) | Real Artificial Analysis Intelligence Index |
|---|---|---|---|
| `simple` | single zone/KPI, one sub-agent | `deepseek-v4-flash:free` | 35.0 |
| `moderate` | comparison intent, OR 2 sub-agents, OR multi-zone/multi-KPI question | `deepseek-v4.1-flash:free` | 39.5 |
| `complex` | 3+ sub-agents (hybrid retrieval), OR a validation retry already fired once | `glm-5.3-flash` | ~42-46 |

The `complex` tier is also what a validation retry escalates to,
unconditionally -- if the cheaper tier's draft already got flagged as
citing numbers not present in the evidence, retrying with the *same* tier
that just got it wrong is a worse bet than escalating.

Mechanically, this reuses the existing single `llm_synthesize` client
(constructed once, not re-instantiated per turn) via a new
`generate(..., model_override=...)` parameter -- the client's own
rate-limit/outage fallback (above) still applies underneath whichever tier
is requested, so a `complex`-tier call that fails still falls back to
`generate`'s model rather than crashing.

Verified live against the real gateway: a single-zone/single-KPI question
routed to `deepseek-v4-flash:free`; a two-zone comparison routed to
`deepseek-v4.1-flash:free`; a 3-sub-agent hybrid question (structured +
web + coding) routed to `glm-5.3-flash`, including on its validation retry.
`Orchestrator._classify_complexity()` itself is pure/deterministic and unit
tested (`tests/test_pipeline.py::TestSynthesisComplexityRouting`) without
needing a live model call to verify the *routing decision* -- only the
worked example above needed a real call, to verify the *plumbing*.

## 3. Which APIs are affordable, and how they map onto the three tiers

Public per-token API pricing changes fast (multiple vendors cut prices in
2025-2026) — treat exact numbers as **directionally right, verify same-day
before quoting a real budget**. `PRICING_PER_MTOK_USD` in `src/llm_client.py`
is the single source of truth this doc's numbers are computed from; update
it, don't hand-edit the numbers below.

| Model (illustrative) | Input $/Mtok | Output $/Mtok | Tier fit |
|---|---|---|---|
| Claude Haiku | $1.00 | $5.00 | `classify`, `generate` — cheap, fast, easily good enough for schema-constrained JSON/SQL/summarization |
| GPT-4o-mini / GPT-5-mini class | $0.15–$0.25 | $0.60–$2.00 | `classify`, `generate` — the cheapest tier available; a reasonable default if the OpenAI ecosystem is already in use |
| Claude Sonnet | $2.00 | $10.00 | `synthesize` — the workhorse: strong instruction-following and multilingual fluency at a fraction of the top tier's cost |
| GPT-4o | $2.50 | $10.00 | `synthesize` alternative in the OpenAI ecosystem |
| Claude Opus / GPT-5 (frontier) | $15.00+ | $75.00+ | **Not recommended for any tier here.** The domain is bounded (6 KPIs, 5 zones, one schema) and doesn't need frontier multi-step reasoning. Revisit only if the domain grows to open-ended, ambiguous multi-hop reasoning that a Sonnet/GPT-4o-class model demonstrably gets wrong. |

**What this deployment actually runs** (live gateway, real published rates
checked Sept 2026 — not illustrative):

| Model | Input $/Mtok | Output $/Mtok | Tier fit | Source |
|---|---|---|---|---|
| DeepSeek V4 Flash | $0.22 (off-peak) / $0.44 (peak) | $0.66 / $1.32 | `classify`, `generate`, and the `synthesize` fallback | [BenchLM](https://benchlm.ai/deepseek/api-pricing), [TechJack](https://techjacksolutions.com/ai-tools/deepseek/deepseek-pricing/) |
| DeepSeek V4.1 Flash | $0.15 (cache miss) / $0.003 (cache hit) | $0.60 | `synthesize` moderate tier | [TechBriefly](https://techbriefly.com/2026/09/11/deepseek-v4-1-flash-api-pricing/), [AIPricing Guru](https://www.aipricing.guru/deepseek-pricing/) |
| GLM-5.3-Flash | $0.15 (list) | $0.50 | `synthesize` complex tier | [eesel AI](https://www.eesel.ai/blog/glm-5-3-flash-pricing) |

DeepSeek's peak window is Mon-Fri 01:00-04:00 & 06:00-10:00 UTC (roughly
doubles both rates); a cache hit is far cheaper on either DeepSeek model.
`PRICING_PER_MTOK_USD` uses the off-peak/cache-miss rate as a reasonable
upper-bound estimate rather than tracking peak/cache state. Note this
gateway currently offers both DeepSeek models at $0 (the ":free"/"limited"
tiers used for `classify`/`generate` and, until upgraded, `synthesize`) —
the table still prices them at real open-market rates, since the point of
tracking cost is "what this traffic is actually worth," not "what happens
to be free on one gateway today."

**Practical recommendation for this system**: Haiku-class (or GPT-4o-mini/
GPT-5-mini-class) for `classify` and `generate`, Sonnet-class (or GPT-4o-class)
for `synthesize`. That's the two real price points that matter — the
frontier tier buys reasoning depth this task doesn't need, at 7-15× the cost.

**Beyond model selection, two more levers reduce cost regardless of which
API is used:**
- **Prompt caching** (offered by both Anthropic and OpenAI): the static
  portion of every system prompt in this repo — the zone/country/brand/KPI
  catalog, the schema description, the instructions themselves — never
  changes turn to turn. Cached input tokens typically price at **~10% of
  standard input cost**. Since `classify` and `generate` prompts are 100%
  cacheable (only the short "latest user message" + a few lines of context
  actually change), this is close to a 90% discount on the *majority* of
  input tokens this system sends. Not implemented here (see §5) but a
  one-line addition through the existing `LLMClient` abstraction.
- **Batch APIs** (offered by both providers, ~50% off list price): irrelevant
  to this system's interactive chat use case (answers must return
  synchronously), but relevant if this were extended to a nightly bulk job
  (e.g. pre-generating a digest for every zone every morning).

### Worked example — a single structured-data query

("What was North America's revenue in Q1 2024?"), using representative token
counts from the actual system prompts in this repo and the tier→model
mapping above (Haiku for classify/generate, Sonnet for synthesize):

| Call | Tier | Model | Input tok | Output tok | Cost |
|---|---|---|---|---|---|
| NLU | classify | Haiku-class | ~900 | ~150 | $0.0017 |
| NL→SQL | generate | Haiku-class | ~500 | ~50 | $0.0008 |
| Synthesis | synthesize | Sonnet-class | ~1,200 | ~300 | $0.0054 |
| **Total** | | | | | **≈ $0.0078 / query** |

If `classify` and `generate` instead ran on the `synthesize` tier (no split
at all — one model everywhere), those same two calls would cost ~2-2.5×
more (Sonnet-class pricing on Haiku-class work): the NLU call alone goes
from $0.0017 to ~$0.0033, and NL→SQL from $0.0008 to ~$0.0016. That's a
small absolute delta per query, but `classify`+`generate` are ~69% of all
calls in the measured profile above — at volume (thousands of queries/day)
the split is a real line item, not a rounding error, with no measured
accuracy cost on tasks this narrow and schema-constrained.

**With prompt caching added** (§ above) on the classify/generate system
prompts, the NLU and NL→SQL rows would drop further still, since most of
their ~900 and ~500 input tokens respectively are the static schema/catalog
text, not the per-turn user message.

**Recommendation**: do not default everything to the strongest available
model. Reserve the top reasoning tier ("Opus-class"/GPT-5-frontier) for none
of the three roles in this system — spending there would inflate cost with
little measurable quality gain for this task shape.

## 4. Latency: where the time actually goes

Sub-agent *tool* latency is negligible: SQLite queries and BM25 search both
run in low single-digit milliseconds locally. **All meaningful latency is
LLM round-trips**, executed **sequentially** in the current implementation:

```
classify (~1-2s) → sub-agent generate call(s) (~0.5-1s each) → synthesize (~2-4s)
```

A simple structured query: **~4-7s end-to-end** (1 classify call + 1 generate
call + 1 synthesize call). A hybrid query (structured + unstructured) costs
**the same LLM latency** as a plain structured query, because the
unstructured sub-agent does no LLM call of its own — only the *synthesize*
call gets a bigger prompt (more evidence to read), which adds output tokens
but not another round-trip.

**The one latency decision we'd change first with more time**: sub-agent
calls are independent of each other (structured SQL-gen, unstructured
retrieval, and web search don't depend on each other's output) but run
sequentially in `Orchestrator.handle_turn()`. Parallelizing them
(asyncio/threading) would collapse a 4-sub-agent hybrid query's latency down
to roughly `classify + max(sub-agent latencies) + synthesize` instead of
`classify + sum(sub-agent latencies) + synthesize` — for a worst-case
4-sub-agent turn, that's the difference between ~4 sequential legs and
effectively 2. Not implemented here in the interest of keeping the control
flow simple and reviewable under a hard deadline (see
`docs/DESIGN_DECISIONS.md` §11).

**Retry path**: `_needs_retry` fires only when the numeric-overlap check
fails (in practice, rare) and costs one extra `synthesize` round-trip
(~2-4s) when it does. **Memory summarization**: one extra `generate`
round-trip (~0.5-1s), amortized over ~7-turn windows, not on every turn.

## 5. Conversation memory: cost/latency shape over a long session

Without any memory optimization, a naive implementation resends the entire
raw transcript as context on every turn: turn *N*'s prompt grows
**O(N)**, and total tokens spent across an *N*-turn session grow **O(N²)**.
`ConversationMemory.summarize_overflow()` (src/memory.py) caps the raw window
at `RECENT_TURNS_KEPT` (6) and folds anything older into a single rolling
summary (a `generate`-tier call), capping each turn's context contribution at
roughly **O(1)** and total session cost at **O(N)** — linear instead of
quadratic. This is the concrete reason "conversation memory optimization for
long-running sessions" is a cost control, not just a UX nicety: on a 50-turn
session the difference between O(N) and O(N²) context tokens is the
difference between a predictable per-turn cost and one that keeps climbing.

## 6. Further optimizations we identified but did not implement

- **Prompt caching** for the static portion of the classify/generate/
  synthesize system prompts (the schema, KPI catalog, zone/country/brand
  lists never change turn to turn) — see §3 above. This system prompt is
  100% cacheable and currently isn't cached. Straightforward to add through
  the same `LLMClient` abstraction without touching the orchestrator.
- **Parallel sub-agent execution** (§4 above).
- **Streaming** the synthesis call's output to the user instead of waiting
  for the full response — doesn't reduce cost, but materially improves
  *perceived* latency, which matters more than raw latency for a chat UX.
- **Batch APIs** for any future non-interactive/bulk use case (§3 above).

## 7. Honest caveat

Every dollar figure above is **illustrative** (public list pricing at time
of writing, which will change fast in an actively competitive market)
applied to **measured call-count/shape** data. The call-count structure
(§1) and the three-tier architecture (§2) are the durable findings;
re-derive the dollar/second figures against current pricing and a real
model's actual observed latency (via `GLOBAL_USAGE.summary()` after a real
run) before citing this as a production budget.
