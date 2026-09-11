"""
Pluggable LLM client abstraction.

WHY THIS EXISTS (design decision, see docs/DESIGN_DECISIONS.md):
The orchestrator and sub-agents never import `anthropic` or `openai` directly.
They call `LLMClient.generate(...)`. This means:
  1. The whole system can be smoke-tested with `MockLLMClient` and NO API key
     and NO network access at all (used in scripts/smoke_test.py).
  2. Switching providers/models is an environment-variable change, not a
     code change -- relevant to the cost/latency trade-off discussion where
     we recommend different models for different sub-agents.
  3. Every call is instrumented (tokens, latency, estimated cost) through a
     single choke point, which is what makes docs/COST_LATENCY_TRADEOFFS.md
     numbers real rather than guessed.

Environment variables:
  LLM_PROVIDER         = "anthropic" | "openai" | "mock"   (default: mock if no key found)
  ANTHROPIC_API_KEY  or  OPENAI_API_KEY
  LLM_MODEL_CLASSIFY   model for orchestrator NLU/intent classification (cheap tier -- structured
                       JSON output against a small fixed schema, no deep reasoning needed)
  LLM_MODEL_GENERATE   model for sub-agent narrow generation: NL->SQL, code-snippet generation,
                       memory summarization (cheap tier -- templated output against a fixed schema)
  LLM_MODEL_SYNTHESIZE model for the final answer-synthesis + validation-retry pass (workhorse tier --
                       this is the one place multilingual fluency and judgment actually matter)
See docs/COST_LATENCY_TRADEOFFS.md for why these three are split rather than
using one model everywhere, or the two-tier (router/worker) split this
replaced: classify and generate together are the majority of call VOLUME in
this system but need the least reasoning; synthesize is the minority of
calls but is what the user actually judges answer quality by.
"""
from __future__ import annotations
import os
import re
import time
import json
from dataclasses import dataclass, field
from typing import Optional


# Illustrative per-million-token USD pricing. THESE ARE APPROXIMATE PUBLIC
# LIST PRICES AND WILL DRIFT FAST (this market is in an active price war) --
# treat as configurable and directionally-right, not authoritative. Verify
# against the provider's current pricing page before using this for a real
# budget decision. Kept here (not hardcoded in the cost doc) so the usage
# tracker and the written analysis always agree.
PRICING_PER_MTOK_USD = {
    "claude-opus":   {"input": 15.00, "output": 75.00},
    "claude-sonnet": {"input": 2.00, "output": 10.00},
    "claude-haiku":  {"input": 1.00, "output": 5.00},
    "gpt-5-mini":    {"input": 0.25, "output": 2.00},
    "gpt-4o":        {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":   {"input": 0.15, "output": 0.60},
    "mock":          {"input": 0.0, "output": 0.0},
}


def _price_bucket(model_name: str) -> str:
    name = (model_name or "").lower()
    for key in PRICING_PER_MTOK_USD:
        if key in name:
            return key
    return "mock"


@dataclass
class UsageEvent:
    caller: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    timestamp: float = field(default_factory=time.time)


class UsageTracker:
    """Single choke point for every LLM call's cost/latency, across all sub-agents."""

    def __init__(self):
        self.events: list[UsageEvent] = []

    def record(self, caller: str, model: str, input_tokens: int, output_tokens: int, latency_ms: float):
        bucket = _price_bucket(model)
        price = PRICING_PER_MTOK_USD[bucket]
        cost = (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]
        self.events.append(UsageEvent(caller, model, input_tokens, output_tokens, latency_ms, cost))

    def summary(self) -> dict:
        if not self.events:
            return {"calls": 0}
        total_cost = sum(e.estimated_cost_usd for e in self.events)
        total_lat = sum(e.latency_ms for e in self.events)
        by_caller = {}
        for e in self.events:
            b = by_caller.setdefault(e.caller, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "latency_ms": 0.0})
            b["calls"] += 1
            b["input_tokens"] += e.input_tokens
            b["output_tokens"] += e.output_tokens
            b["cost_usd"] += e.estimated_cost_usd
            b["latency_ms"] += e.latency_ms
        return {
            "calls": len(self.events),
            "total_cost_usd": round(total_cost, 6),
            "total_latency_ms": round(total_lat, 1),
            "avg_latency_ms": round(total_lat / len(self.events), 1),
            "by_caller": by_caller,
        }

    def reset(self):
        self.events.clear()


GLOBAL_USAGE = UsageTracker()


def _approx_tokens(text: str) -> int:
    # Cheap approximation (~4 chars/token) used only when the provider SDK
    # doesn't return exact usage (e.g. our own MockLLMClient). Real providers
    # return exact input/output token counts, which we use when available.
    return max(1, len(text) // 4)


class LLMClient:
    """Base interface every provider implementation and MockLLMClient conforms to."""

    model_name: str = "mock"

    def generate(self, system: str, user: str, history: Optional[list[dict]] = None,
                 json_mode: bool = False, max_tokens: int = 1024, caller: str = "unknown") -> str:
        raise NotImplementedError


class AnthropicLLMClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        import anthropic  # lazy import: only required if this provider is actually selected
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model

    def generate(self, system, user, history=None, json_mode=False, max_tokens=1024, caller="unknown") -> str:
        messages = list(history or [])
        messages.append({"role": "user", "content": user})
        t0 = time.time()
        resp = self._client.messages.create(
            model=self.model_name, system=system, messages=messages, max_tokens=max_tokens,
        )
        latency_ms = (time.time() - t0) * 1000
        text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
        GLOBAL_USAGE.record(caller, self.model_name, resp.usage.input_tokens, resp.usage.output_tokens, latency_ms)
        return text


class OpenAILLMClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        import openai  # lazy import
        self._client = openai.OpenAI(api_key=api_key)
        self.model_name = model

    def generate(self, system, user, history=None, json_mode=False, max_tokens=1024, caller="unknown") -> str:
        messages = [{"role": "system", "content": system}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": user})
        t0 = time.time()
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(
            model=self.model_name, messages=messages, max_tokens=max_tokens, **kwargs,
        )
        latency_ms = (time.time() - t0) * 1000
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        GLOBAL_USAGE.record(caller, self.model_name, usage.prompt_tokens, usage.completion_tokens, latency_ms)
        return text


class MockLLMClient(LLMClient):
    """
    Deterministic, offline, zero-cost stand-in used for CI / smoke-testing the
    pipeline plumbing (routing, retrieval, SQL safety, formatting) WITHOUT a
    real API key. It is intentionally simple/rule-based -- it proves the
    system architecture works end-to-end, but the actual quality of natural-
    language understanding and synthesis requires swapping in a real model
    (see README "Running with a real model").
    """
    model_name = "mock"

    def generate(self, system, user, history=None, json_mode=False, max_tokens=1024, caller="unknown") -> str:
        t0 = time.time()
        text = self._route(system, user, json_mode)
        latency_ms = (time.time() - t0) * 1000
        GLOBAL_USAGE.record(caller, self.model_name, _approx_tokens(system + user), _approx_tokens(text), latency_ms)
        return text

    def _route(self, system: str, user: str, json_mode: bool) -> str:
        s = system.lower()
        if "classify" in s and json_mode:
            # Extremely naive keyword-based intent classifier used only offline.
            # Pull just the actual user message out of the "Latest user message: ..."
            # wrapper the orchestrator adds, so short greetings aren't padded past
            # our word-count heuristics by that wrapper text.
            u = user.lower()
            m = re.search(r"latest user message:\s*(.*)", u, re.DOTALL)
            if m:
                u = m.group(1).strip()

            if any(g in u for g in ("hi", "hello", "hey")) and len(u.split()) < 4:
                intent = "greeting"
            elif "what can you" in u or ("help" in u and "with" in u):
                intent = "capability_intro"
            elif any(w in u for w in ("weather", "joke", "stock price of apple")):
                intent = "out_of_scope"
            elif any(w in u for w in ("compare", "vs", "versus", "difference between")):
                intent = "comparison"
            elif any(w in u for w in ("available", "which kpis", "what kpis", "what data",
                                       "metadata", "what can i ask", "what metrics")):
                intent = "metadata_discovery"
            else:
                intent = "data_query"

            # Lightweight entity extraction (substring match against the known
            # lists) purely so the OFFLINE smoke test exercises routing,
            # hierarchy-fallback and hybrid-retrieval logic realistically.
            # A real LLM does this far more robustly via the NLU prompt.
            from src.config import ALL_ZONES, ALL_COUNTRIES, ALL_BRANDS, KNOWN_COMPETITORS
            zones = [z for z in ALL_ZONES if z.lower() in u]
            countries = [c for c in ALL_COUNTRIES if c.lower() in u]
            brands = [b for b in ALL_BRANDS if b.lower() in u]
            KPI_KEYWORDS = {
                "revenue": "revenue_usd_m", "sales": "revenue_usd_m",
                "volume": "volume_k_hl",
                "ebitda margin": "ebitda_margin_pct", "margin": "ebitda_margin_pct",
                "ebitda": "normalized_ebitda_usd_m",
                "organic growth": "organic_revenue_growth_pct", "growth": "organic_revenue_growth_pct",
                "net profit": "net_profit_usd_m", "profit": "net_profit_usd_m",
            }
            kpis = list(dict.fromkeys(v for k, v in KPI_KEYWORDS.items() if k in u))
            unsupported = [c for c in KNOWN_COMPETITORS if c.lower() in u]

            needed = []
            if any(w in u for w in ("news", "press release", "announce", "sustainab", "strategy",
                                      "why", "market research", "trend", "earnings", "commentary",
                                      "filing", "document", "glossary")) or brands:
                needed.append("unstructured")
            if any(w in u for w in ("competitor", "industry", "public")) or unsupported:
                needed.append("web")
            if any(w in u for w in ("cagr", "projection", "if it grew", "calculate")):
                needed.append("coding")
            if not needed or zones or countries or kpis:
                needed.insert(0, "structured")

            return json.dumps({
                "language": "en", "intent": intent, "needs_clarification": False,
                "clarification_question": None,
                "entities": {"zones": zones, "countries": countries, "brands": brands,
                             "kpis": kpis, "period": None, "comparison_period": None},
                "unsupported_entities": unsupported, "needed_subagents": needed or ["structured"],
            })
        if "sql generation" in s:
            return "SELECT zone, period_label, revenue_usd_m FROM fact_kpi WHERE grain='quarterly' ORDER BY year, quarter LIMIT 20;"
        if "answer-synthesis" in s:
            return ("[mock-llm placeholder answer] The retrieved data is summarized above. "
                    "Swap in a real ANTHROPIC_API_KEY / OPENAI_API_KEY to get an actual synthesized answer here.")
        if "python snippet" in s or "you write short python" in s:
            return "result = 42"
        return "[mock-llm output]"


_ROLE_ENV_VAR = {
    "classify": "LLM_MODEL_CLASSIFY",
    "generate": "LLM_MODEL_GENERATE",
    "synthesize": "LLM_MODEL_SYNTHESIZE",
}
_ROLE_DEFAULT_MODEL = {
    "anthropic": {
        "classify": "claude-haiku-4-5",       # cheap tier: JSON-mode intent/entity extraction
        "generate": "claude-haiku-4-5",       # cheap tier: NL->SQL, code snippets, memory summaries
        "synthesize": "claude-sonnet-5",      # workhorse tier: final multilingual answer
    },
    "openai": {
        "classify": "gpt-5-mini",
        "generate": "gpt-5-mini",
        "synthesize": "gpt-5",
    },
}


def get_llm_client(role: str = "synthesize") -> LLMClient:
    """
    role is one of three tiers, matched to what each job actually needs
    (see docs/COST_LATENCY_TRADEOFFS.md for the full reasoning and measured
    call-volume split):
      - "classify": orchestrator NLU/intent/entity extraction. Structured
        JSON output against a small fixed schema, no deep reasoning --
        cheapest tier.
      - "generate": sub-agent narrow generation (NL->SQL, code snippets,
        memory summarization). Templated output against a fixed schema --
        also cheapest tier; kept as a separate env var from "classify" only
        so the two can be tuned independently later, not because they need
        different models today.
      - "synthesize": the final answer-synthesis and validation-retry pass.
        Needs multilingual fluency and judgment (what's an assumption, what's
        a limitation) -- the one tier worth paying for a stronger model.
    "classify"/"generate" together are the MAJORITY of call volume in this
    system (~60%+, per the measured profile) but need the least reasoning;
    "synthesize" is the minority of calls but the one the user judges answer
    quality by. Model IDs and prices below are illustrative placeholders --
    this space moves fast; pin the exact model string available on your
    account and verify current pricing before treating PRICING_PER_MTOK_USD
    as a real budget number.
    """
    if role not in _ROLE_ENV_VAR:
        raise ValueError(f"Unknown LLM role {role!r}; expected one of {sorted(_ROLE_ENV_VAR)}")

    provider = os.environ.get("LLM_PROVIDER", "").lower()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not provider:
        provider = "anthropic" if anthropic_key else "openai" if openai_key else "mock"

    if provider == "anthropic" and anthropic_key:
        model = os.environ.get(_ROLE_ENV_VAR[role], _ROLE_DEFAULT_MODEL["anthropic"][role])
        return AnthropicLLMClient(model=model, api_key=anthropic_key)
    if provider == "openai" and openai_key:
        model = os.environ.get(_ROLE_ENV_VAR[role], _ROLE_DEFAULT_MODEL["openai"][role])
        return OpenAILLMClient(model=model, api_key=openai_key)
    return MockLLMClient()
