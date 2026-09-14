"""
Shared infrastructure for the "live" (real-LLM) capability test suite.

Design: each of the 25 required capabilities (see the assignment brief, and
docs/CAPABILITY_MAPPING.md) gets its own case file under tests/live/cases/,
defining a CASES list of `Case` objects. A Case describes one or more
conversational turns run in sequence against a fresh Orchestrator, plus a
`check` callable that inspects the resulting AgentResponse(s) *and* the
orchestrator's own state (e.g. memory.active_filters) and returns
(passed: bool, reason: str).

This same CASES list is consumed by two different renderers, so there is
ONE source of truth per capability, not two:
  - tests/live/test_live_capabilities.py: turns each Case into a real
    unittest assertion (skipped automatically if no live LLM is configured
    -- see requires_live_llm()).
  - scripts/build_capability_notebooks.py: turns each Case into notebook
    cells showing the real question(s) and answer(s), for human review.

These are REAL, live-LLM-calling tests -- a deliberate, separate addition
from tests/test_pipeline.py, which stays offline/mock-based/zero-cost as
documented in docs/DESIGN_DECISIONS.md. Running this suite costs real
tokens and takes real wall-clock time; it is not part of the zero-cost CI
gate.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.orchestrator import Orchestrator, AgentResponse

CheckFn = Callable[[list[AgentResponse], Orchestrator], tuple]


@dataclass
class Case:
    id: str
    description: str
    turns: list[str]
    check: CheckFn
    note: str = ""  # optional extra context shown in the notebook (why this case matters)


@dataclass
class CaseRun:
    case: Case
    responses: list[AgentResponse] = field(default_factory=list)
    passed: bool = False
    reason: str = ""
    latency_s: float = 0.0
    error: str = ""


def has_live_llm() -> bool:
    """True if a real (non-mock) provider is actually configured -- used to
    skip the live test suite automatically rather than fail when no API key
    is present, e.g. in CI or a fresh checkout."""
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        provider = ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                     else "openai" if os.environ.get("OPENAI_API_KEY") else "mock")
    return provider != "mock"


def run_case(case: Case, orchestrator: Optional[Orchestrator] = None) -> CaseRun:
    """Runs `case.turns` in sequence against a fresh Orchestrator (unless one
    is passed in), then applies `case.check` to (responses, orchestrator).
    Never raises -- an exception during execution or checking is captured
    into CaseRun.error/reason rather than propagating, so one bad case
    doesn't abort a whole capability's run."""
    orch = orchestrator or Orchestrator()
    t0 = time.time()
    responses: list[AgentResponse] = []
    try:
        for turn in case.turns:
            responses.append(orch.handle_turn(turn))
        latency_s = time.time() - t0
        passed, reason = case.check(responses, orch)
        return CaseRun(case=case, responses=responses, passed=passed, reason=reason, latency_s=latency_s)
    except Exception as e:
        latency_s = time.time() - t0
        return CaseRun(case=case, responses=responses, passed=False,
                        reason=f"raised {type(e).__name__}: {e}", latency_s=latency_s,
                        error=f"{type(e).__name__}: {e}")


# ----------------------------------------------------------- assertion helpers
# Small, composable, reused across capability files rather than re-implemented
# per case -- keeps each case's `check` a short call to one of these (or
# all_of(...) to combine several). Every helper has signature
# (responses, orch) -> (bool, str), even the ones that ignore `orch`, so
# Case.check is always called uniformly by run_case().

def _last(responses: list[AgentResponse]) -> AgentResponse:
    return responses[-1]


def intent_is(*expected: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return r.intent in expected, f"intent={r.intent!r}, expected one of {expected}"
    return _check


def used_subagent(name: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return name in r.sub_agents_used, f"sub_agents_used={r.sub_agents_used}, expected {name!r} present"
    return _check


def used_subagents_all(*names: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        ok = all(n in r.sub_agents_used for n in names)
        return ok, f"sub_agents_used={r.sub_agents_used}, expected all of {names}"
    return _check


def no_subagent_used() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return len(r.sub_agents_used) == 0, f"sub_agents_used={r.sub_agents_used}, expected none (fast-path)"
    return _check


def answer_contains_any(*words: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        text = r.answer.lower()
        ok = any(w.lower() in text for w in words)
        return ok, f"answer did not contain any of {words}: {r.answer[:200]!r}"
    return _check


def citations_nonempty() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return len(r.citations) > 0, f"citations={r.citations}, expected at least one"
    return _check


def assumptions_contains(*substrings: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        joined = " | ".join(r.assumptions).lower()
        ok = any(s.lower() in joined for s in substrings)
        return ok, f"assumptions={r.assumptions}, expected one containing any of {substrings}"
    return _check


def not_crashed_and_answered() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        ok = bool(r.answer) and not r.unavailable
        return ok, f"unavailable={r.unavailable}, answer={r.answer[:100]!r}"
    return _check


def clarification_asked() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return r.intent == "clarification_needed" and bool(r.answer), f"intent={r.intent!r}"
    return _check


def has_markdown_table() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        ok = "|" in r.answer and "---" in r.answer
        return ok, f"no markdown table detected: {r.answer[:200]!r}"
    return _check


def has_follow_up_suggestions() -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return len(r.follow_up_suggestions) > 0, f"follow_up_suggestions={r.follow_up_suggestions}"
    return _check


def retried_is(expected: bool) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        return r.retried == expected, f"retried={r.retried}, expected {expected}"
    return _check


def active_filter_contains(dim: str, substring: str) -> CheckFn:
    """Checks the ORCHESTRATOR's own memory state after the final turn --
    for capabilities where the interesting assertion is about what got
    remembered, not just the literal answer text (context preservation,
    contextual follow-ups)."""
    def _check(responses, orch):
        val = orch.memory.active_filters.get(dim, "")
        ok = substring.lower() in val.lower()
        return ok, f"active_filters[{dim!r}]={val!r}, expected to contain {substring!r}"
    return _check


def rolling_summary_present() -> CheckFn:
    def _check(responses, orch):
        ok = bool(orch.memory.rolling_summary)
        return ok, f"rolling_summary present={ok}, raw_turns kept={len(orch.memory.raw_turns)}"
    return _check


def language_is(*codes: str) -> CheckFn:
    def _check(responses, orch):
        r = _last(responses)
        lang = (r.raw_nlu or {}).get("language", "")
        ok = lang in codes
        return ok, f"detected language={lang!r}, expected one of {codes}"
    return _check


def all_of(*checks: CheckFn) -> CheckFn:
    def _check(responses, orch):
        reasons = []
        for c in checks:
            ok, reason = c(responses, orch)
            reasons.append(reason)
            if not ok:
                return False, reason
        return True, "; ".join(reasons)
    return _check


def any_of(*checks: CheckFn) -> CheckFn:
    def _check(responses, orch):
        reasons = []
        for c in checks:
            ok, reason = c(responses, orch)
            if ok:
                return True, reason
            reasons.append(reason)
        return False, " | ".join(reasons)
    return _check
