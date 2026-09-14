"""
Builds a single, self-contained HTML report visualizing test status across
both suites -- WITHOUT re-running the expensive live LLM suite. Only the
free/instant offline suite is re-run (for a fresh, verified number); the 185
live-case results are read from the already-captured tests/live/reports/cap*.json.

Run: python3 scripts/build_test_report.py
Output: reports/capability_test_report.html
"""
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.high_level.rollup import build_rollup, REPORTS_DIR

TEMPLATE_PATH = ROOT / "scripts" / "_test_report_template.html"
OUT_PATH = ROOT / "reports" / "capability_test_report.html"


def run_offline_suite() -> dict:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    result = runner.run(suite)
    return {
        "total": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }


def load_full_capabilities() -> list:
    by_number = {}
    for path in sorted(REPORTS_DIR.glob("cap*.json")):
        data = json.loads(path.read_text())
        for cap in data.get("capabilities", []):
            by_number[cap["number"]] = cap
    return [by_number[n] for n in sorted(by_number)]


def load_models() -> dict:
    env_path = ROOT / ".env"
    values = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.startswith("LLM_MODEL_") or k == "LLM_PROVIDER":
                values[k] = v
    return values


def main():
    print("Running offline suite (fresh, free, instant)...")
    offline = run_offline_suite()
    print(f"  {offline['passed']}/{offline['total']} passed")

    print("Loading already-captured live capability reports...")
    capabilities = load_full_capabilities()
    rollup = build_rollup()

    total_cases = sum(c["total"] for c in capabilities)
    total_passed = sum(c["passed"] for c in capabilities)
    total_cost = sum(sum(cs.get("cost_usd", 0.0) for cs in c["cases"]) for c in capabilities)
    total_latency = sum(sum(cs.get("latency_s", 0.0) for cs in c["cases"]) for c in capabilities)

    clusters = []
    for slug, entry in rollup.items():
        clusters.append({
            "slug": slug, "title": entry["title"], "description": entry["description"],
            "passed": entry["passed"], "total_cases": entry["total_cases"],
            "total_cost_usd": entry["total_cost_usd"], "total_latency_s": entry["total_latency_s"],
            "capability_numbers": [c["number"] for c in entry["capabilities"]],
        })

    payload = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "offline_tests": offline,
        "live_suite": {"total_cases": total_cases, "passed": total_passed,
                        "cost_usd": round(total_cost, 4), "latency_s": round(total_latency, 1)},
        "clusters": clusters,
        "capabilities": capabilities,
        "models": load_models(),
    }

    template = TEMPLATE_PATH.read_text()
    # Real answer text is arbitrary LLM output -- guard against a future
    # rebuild where some answer happens to contain the literal substring
    # "</script", which would otherwise prematurely close the script tag
    # this JSON is embedded in and corrupt the page.
    data_json = json.dumps(payload).replace("</script", "<\\/script")
    html = template.replace("/*__REPORT_DATA__*/{}", data_json)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html)
    print(f"\nWrote {OUT_PATH} ({len(html) / 1024:.0f} KB)")
    print(f"Offline: {offline['passed']}/{offline['total']} | Live: {total_passed}/{total_cases} | Cost: ${total_cost:.4f}")


if __name__ == "__main__":
    main()
