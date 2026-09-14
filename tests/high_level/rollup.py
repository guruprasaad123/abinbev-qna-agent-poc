"""
Builds the High-Level Tier rollup: aggregates the already-executed
tests/live/reports/cap*.json (written by scripts/run_live_capability_tests.py)
into per-cluster summaries, per tests/high_level/clusters.py's grouping.

Pure data aggregation -- no LLM calls, no network. Reads whatever reports
already exist; a capability whose report hasn't been run yet is simply
reported as "not yet run" rather than causing an error, so this can be run
at any point during a partial rollout of the live suite.
"""
from __future__ import annotations
import json
from pathlib import Path

from tests.high_level.clusters import CLUSTERS

REPORTS_DIR = Path(__file__).resolve().parents[1] / "live" / "reports"


def _load_capability_reports() -> dict:
    """number -> capability report dict, for every cap*.json report found."""
    by_number = {}
    if not REPORTS_DIR.exists():
        return by_number
    for path in sorted(REPORTS_DIR.glob("cap*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for cap_report in data.get("capabilities", []):
            by_number[cap_report["number"]] = cap_report
    return by_number


def build_rollup() -> dict:
    """Returns {cluster_slug: {title, description, capabilities: [...],
    total_cases, passed, failed, not_run: [capability numbers with no report
    yet], total_cost_usd, total_latency_s}}"""
    reports_by_number = _load_capability_reports()
    rollup = {}
    for slug, cluster in CLUSTERS.items():
        entry = {
            "slug": slug, "title": cluster["title"], "description": cluster["description"],
            "capabilities": [], "total_cases": 0, "passed": 0, "failed": 0,
            "not_run": [], "total_cost_usd": 0.0, "total_latency_s": 0.0,
        }
        for number in cluster["capability_numbers"]:
            report = reports_by_number.get(number)
            if report is None:
                entry["not_run"].append(number)
                continue
            case_cost = sum(c.get("cost_usd", 0.0) for c in report["cases"])
            case_latency = sum(c.get("latency_s", 0.0) for c in report["cases"])
            entry["capabilities"].append({
                "number": number, "title": report["title"], "slug": report["slug"],
                "passed": report["passed"], "total": report["total"],
                "cost_usd": case_cost, "latency_s": case_latency,
                "failed_cases": [c for c in report["cases"] if not c["passed"]],
            })
            entry["total_cases"] += report["total"]
            entry["passed"] += report["passed"]
            entry["failed"] += report["total"] - report["passed"]
            entry["total_cost_usd"] += case_cost
            entry["total_latency_s"] += case_latency
        rollup[slug] = entry
    return rollup


def print_rollup_summary(rollup: dict) -> None:
    grand_total = grand_passed = 0
    grand_cost = 0.0
    for slug, entry in rollup.items():
        status = "" if not entry["not_run"] else f"  (not yet run: capabilities {entry['not_run']})"
        print(f"{entry['title']:35s} {entry['passed']:3d}/{entry['total_cases']:3d} passed"
              f"  ${entry['total_cost_usd']:.4f}{status}")
        grand_total += entry["total_cases"]
        grand_passed += entry["passed"]
        grand_cost += entry["total_cost_usd"]
    print(f"\n{'TOTAL':35s} {grand_passed:3d}/{grand_total:3d} passed  ${grand_cost:.4f}")


if __name__ == "__main__":
    print_rollup_summary(build_rollup())
