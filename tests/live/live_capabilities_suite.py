"""
Live (real-LLM) test suite covering all 25 required capabilities from the
assignment brief, 185 cases total across tests/live/cases/cap01..cap25.

This is DELIBERATELY separate from tests/test_pipeline.py, which stays
offline/mock-based/zero-cost/zero-network as documented in
docs/DESIGN_DECISIONS.md and is the suite that gates CI. This suite:
  - Requires a real LLM_PROVIDER + API key (or LLM_BASE_URL gateway) to be
    configured -- it is SKIPPED ENTIRELY, not failed, if none is found
    (has_live_llm() in tests/live/runner.py), so a fresh checkout or CI
    without credentials still passes cleanly.
  - Costs real tokens and takes real wall-clock time (185 cases, most doing
    2-4 sequential LLM calls each) -- run deliberately, not as part of a
    fast feedback loop.
  - Is DELIBERATELY named live_capabilities_suite.py, NOT test_*.py --
    unittest's default discovery pattern is "test*.py", so this file is
    invisible to a plain `python3 -m unittest discover -s tests`. That's
    intentional: if this were auto-discovered, someone who configures a
    real API key and then runs the normal "quick, free" test command would
    unknowingly kick off an hours-long, real-money live run. Run it only
    via the explicit invocation below (or scripts/run_live_capability_tests.py).

Run explicitly:
    python3 -m unittest discover -s tests/live -p "live_capabilities_suite.py" -v
Or a single capability:
    python3 -m unittest tests.live.live_capabilities_suite.Test03_intent_validation -v
Or, friendlier (progress output, capability filtering):
    python3 scripts/run_live_capability_tests.py
    python3 scripts/run_live_capability_tests.py --capability 9
"""
from __future__ import annotations
import unittest

from tests.live.runner import has_live_llm, run_case
from tests.live.cases import CAPABILITIES

_SKIP_REASON = "requires a real LLM (set LLM_PROVIDER + ANTHROPIC_API_KEY/OPENAI_API_KEY, or .env)"


def _make_test_method(case):
    def _test(self):
        result = run_case(case)
        detail = (
            f"\n  case: {case.id} -- {case.description}"
            f"\n  turns: {case.turns}"
            f"\n  reason: {result.reason}"
            f"\n  latency: {result.latency_s:.1f}s"
        )
        if result.responses:
            detail += f"\n  final answer: {result.responses[-1].answer[:300]!r}"
        self.assertTrue(result.passed, detail)
    _test.__doc__ = case.description
    return _test


def _build_test_class(capability: dict) -> type:
    attrs = {}
    for case in capability["cases"]:
        attrs[f"test_{case.id}_{case.description[:40].replace(' ', '_').replace('/', '_')}"] = \
            _make_test_method(case)
    class_name = f"Test{capability['number']:02d}_{capability['slug'].split('_', 1)[1]}"
    cls = type(class_name, (unittest.TestCase,), attrs)
    cls.__doc__ = f"Capability {capability['number']}: {capability['title']}"
    return unittest.skipUnless(has_live_llm(), _SKIP_REASON)(cls)


# Build one TestCase subclass per capability and register it in this
# module's namespace so `python3 -m unittest discover` finds them all.
# The loop variables themselves must NOT be left in module scope afterward --
# `_cls` would otherwise be picked up by discovery as its own (duplicate)
# TestCase, double-counting the last capability built.
for _capability in CAPABILITIES:
    _cls = _build_test_class(_capability)
    globals()[_cls.__name__] = _cls
del _capability, _cls


if __name__ == "__main__":
    unittest.main()
