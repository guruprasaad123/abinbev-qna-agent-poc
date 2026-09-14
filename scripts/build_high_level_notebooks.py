"""
Builds one notebook per enterprise domain cluster under
notebooks/high_level/<slug>/demo.ipynb -- an executive-level rollup over the
25 granular capability notebooks under notebooks/capabilities/, grouped per
tests/high_level/clusters.py.

Like scripts/build_capability_notebooks.py, this renders ALREADY-CAPTURED
real results (via tests/high_level/rollup.py, itself reading
tests/live/reports/cap*.json) -- no new LLM calls, no re-running anything.
Each cluster notebook shows: the cluster's pass/fail/cost summary, then per
member capability a condensed summary plus 1-2 representative real Q&A
examples (the full case-by-case detail lives in the per-capability
notebooks this rolls up from -- see the "Deeper detail" link in each).

Run: python3 scripts/build_high_level_notebooks.py
(requires tests/live/reports/cap*.json -- run
scripts/run_live_capability_tests.py first)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.high_level.clusters import CLUSTERS
from tests.high_level.rollup import build_rollup, REPORTS_DIR
from scripts.build_capability_notebooks import SETUP_SOURCE, ASK_HELPER_SOURCE, _reproduce_ask_output

OUT_DIR = ROOT / "notebooks" / "high_level"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(source: str, outputs: list | None = None) -> dict:
    return {
        "cell_type": "code", "metadata": {}, "execution_count": None,
        "source": source.splitlines(keepends=True),
        "outputs": outputs or [],
    }


def _stream_output(text: str) -> dict:
    return {"output_type": "stream", "name": "stdout", "text": text.splitlines(keepends=True)}


def _load_full_capability_report(number: int) -> dict | None:
    """The high-level rollup only keeps aggregate numbers -- for a couple of
    representative example Q&As per capability, read that capability's full
    report directly (same already-captured data, just more detail)."""
    for path in REPORTS_DIR.glob("cap*.json"):
        data = json.loads(path.read_text())
        for cap_report in data.get("capabilities", []):
            if cap_report["number"] == number:
                return cap_report
    return None


def _example_cell(cap_report: dict, n: int = 2) -> dict:
    """Real, executable ask() calls for 1-2 representative cases from this
    capability -- same genuine-code principle as
    scripts/build_capability_notebooks.py, just fewer cases per capability
    since this is the condensed executive view."""
    source_lines = []
    outputs_text = []
    for case in cap_report["cases"][:n]:
        turn = case["turns"][0] if case["turns"] else ""
        label = case["id"]
        source_lines.append(f'_ = ask({turn!r}, {label!r})')
        answer = case["answers"][0] if case["answers"] else "(no response captured)"
        intent = case["intents"][0] if case["intents"] else "?"
        sub_agents = case["sub_agents_used"][0] if case["sub_agents_used"] else []
        citations = case["citations"][0] if case["citations"] else []
        assumptions = case["assumptions"][0] if case["assumptions"] else []
        outputs_text.append(_reproduce_ask_output(turn, label, intent, sub_agents, citations, assumptions, answer))
    return code("\n".join(source_lines), outputs=[_stream_output("\n\n".join(outputs_text))])


def build_cluster_notebook(slug: str, entry: dict) -> dict:
    header = (
        f"# {entry['title']}\n\n"
        f"{entry['description']}\n\n"
        f"**Rollup: {entry['passed']}/{entry['total_cases']} cases passed** across "
        f"{len(entry['capabilities'])} required capabilities, est. cost "
        f"${entry['total_cost_usd']:.4f}, {entry['total_latency_s']:.0f}s total.\n\n"
        f"This is an executive-level summary over already-captured real-LLM results -- "
        f"see `docs/CAPABILITY_MAPPING.md` for the full 25-capability table, and "
        f"`notebooks/capabilities/<NN>_<slug>/demo.ipynb` for every case in full detail "
        f"per capability."
    )
    if entry["not_run"]:
        header += f"\n\n**Not yet run:** capabilities {entry['not_run']} (no report found)."
    cells = [
        md(header),
        code(SETUP_SOURCE, outputs=[_stream_output("LLM provider in use: openai\n")]),
        code(ASK_HELPER_SOURCE),
    ]

    for cap in entry["capabilities"]:
        cells.append(md(f"## {cap['number']}. {cap['title']}\n\n"
                         f"{cap['passed']}/{cap['total']} passed — "
                         f"${cap['cost_usd']:.4f}, {cap['latency_s']:.0f}s"))
        full_report = _load_full_capability_report(cap["number"])
        if full_report:
            cells.append(_example_cell(full_report))
        else:
            cells.append(md("_(report not found)_"))
        if cap["failed_cases"]:
            fail_text = "\n".join(f"[{fc['id']}] {fc['description']} -- {fc['reason'][:200]}"
                                   for fc in cap["failed_cases"])
            cells.append(md(f"**Failed cases in this capability:**\n```\n{fail_text}\n```"))

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def main():
    rollup = build_rollup()
    built = 0
    for slug, entry in rollup.items():
        if entry["total_cases"] == 0:
            print(f"Skipping {slug}: no reports found for any member capability yet.")
            continue
        folder = OUT_DIR / slug
        folder.mkdir(parents=True, exist_ok=True)
        nb = build_cluster_notebook(slug, entry)
        out_path = folder / "demo.ipynb"
        out_path.write_text(json.dumps(nb, indent=1))
        print(f"Wrote {out_path} ({entry['passed']}/{entry['total_cases']} passed)")
        built += 1
    print(f"\nBuilt {built} high-level cluster notebook(s) under {OUT_DIR}")


if __name__ == "__main__":
    main()
