"""
Friendlier CLI for tests/live/live_capabilities_suite.py -- runs the 185
real-LLM capability cases with live progress output and a final summary
(pass/fail counts per capability, total cost, total latency), since a bare
`python3 -m unittest` run gives no visibility into a job this size until it
finishes entirely.

Also writes a JSON report (--report, default tests/live/last_run_report.json)
that scripts/build_capability_notebooks.py can optionally read to avoid
re-running cases just to render a notebook from an already-completed pass.

Usage:
    python3 scripts/run_live_capability_tests.py                  # all 25 capabilities
    python3 scripts/run_live_capability_tests.py --capability 9   # just SQL safety
    python3 scripts/run_live_capability_tests.py --capability 9 --case 01
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

from tests.live.runner import has_live_llm, run_case
from tests.live.cases import CAPABILITIES
from src.llm_client import GLOBAL_USAGE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", type=int, default=None,
                         help="Run only this capability number (1-25)")
    parser.add_argument("--case", type=str, default=None,
                         help="Run only this case id within the selected capability (requires --capability)")
    parser.add_argument("--report", type=str,
                         default=str(Path(__file__).resolve().parents[1] / "tests/live/last_run_report.json"))
    args = parser.parse_args()

    if not has_live_llm():
        print("No real LLM configured (LLM_PROVIDER/API key) -- nothing to run. "
              "This is expected/safe in an offline environment; see tests/live/runner.py::has_live_llm().")
        return 0

    capabilities = CAPABILITIES
    if args.capability is not None:
        capabilities = [c for c in capabilities if c["number"] == args.capability]
        if not capabilities:
            print(f"No capability numbered {args.capability}")
            return 2

    report = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "capabilities": []}
    grand_total = grand_passed = 0
    t_start = time.time()

    for cap in capabilities:
        cases = cap["cases"]
        if args.case:
            cases = [c for c in cases if c.id == args.case]
        print(f"\n{'=' * 90}\n{cap['number']:2d}. {cap['title']}  ({len(cases)} cases)\n{'=' * 90}")
        cap_report = {"number": cap["number"], "title": cap["title"], "slug": cap["slug"], "cases": []}
        cap_passed = 0

        for case in cases:
            usage_start = len(GLOBAL_USAGE.events)
            result = run_case(case)
            usage_events = GLOBAL_USAGE.events[usage_start:]
            cost = sum(e.estimated_cost_usd for e in usage_events)
            status = "PASS" if result.passed else "FAIL"
            grand_total += 1
            cap_passed += int(result.passed)
            grand_passed += int(result.passed)
            print(f"  [{status}] {case.id} {case.description}  ({result.latency_s:.1f}s, ${cost:.5f})")
            if not result.passed:
                print(f"         reason: {result.reason}")
            cap_report["cases"].append({
                "id": case.id, "description": case.description, "turns": case.turns,
                "passed": result.passed, "reason": result.reason,
                "latency_s": round(result.latency_s, 2), "cost_usd": round(cost, 6),
                "answers": [r.answer for r in result.responses],
                "intents": [r.intent for r in result.responses],
                "sub_agents_used": [r.sub_agents_used for r in result.responses],
                "assumptions": [r.assumptions for r in result.responses],
                "citations": [r.citations for r in result.responses],
            })

        print(f"  -- {cap_passed}/{len(cases)} passed")
        cap_report["passed"] = cap_passed
        cap_report["total"] = len(cases)
        report["capabilities"].append(cap_report)

    elapsed = time.time() - t_start
    total_cost = sum(e.estimated_cost_usd for e in GLOBAL_USAGE.events)
    report["summary"] = {
        "total_cases": grand_total, "passed": grand_passed, "failed": grand_total - grand_passed,
        "elapsed_s": round(elapsed, 1), "total_cost_usd": round(total_cost, 4),
    }

    print(f"\n{'=' * 90}\nTOTAL: {grand_passed}/{grand_total} passed "
          f"in {elapsed/60:.1f} min, est. cost ${total_cost:.4f}\n{'=' * 90}")

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, default=str))
    print(f"Report written to {args.report}")

    return 0 if grand_passed == grand_total else 1


if __name__ == "__main__":
    sys.exit(main())
