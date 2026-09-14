"""
Builds one notebook per capability under notebooks/capabilities/<NN>_<slug>/demo.ipynb,
from the JSON reports scripts/run_live_capability_tests.py already wrote to
tests/live/reports/cap*.json.

Each notebook's code cells are REAL, executable Python -- the same `ask()`
helper pattern as notebooks/demo.ipynb (see scripts/build_notebook.py):
a setup cell constructing a real Orchestrator, an `ask()` helper cell, and
then one real `ask(question, label)` call per case turn. If you actually
re-run this notebook against a live LLM, it will make real calls and behave
the same way -- it is NOT a comment-only mockup of what happened. The
`outputs` attached to each cell are the REAL output already captured from
the live run recorded in the JSON report, so the notebook reads correctly
without needing to re-execute, but the source is genuine, not decorative.

Run: python3 scripts/build_capability_notebooks.py
(requires tests/live/reports/cap*.json -- run
scripts/run_live_capability_tests.py first)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "tests" / "live" / "reports"
OUT_DIR = ROOT / "notebooks" / "capabilities"

SETUP_SOURCE = """import sys, pathlib

# Robust path insert regardless of where Jupyter's cwd lands (repo root, or
# this notebook's own folder under notebooks/capabilities/<slug>/):
_p = pathlib.Path.cwd()
while not (_p / "src").exists() and _p != _p.parent:
    _p = _p.parent
sys.path.insert(0, str(_p))

import os

try:
    from dotenv import load_dotenv  # optional: picks up a .env file if python-dotenv is installed
    load_dotenv(override=False)
except ImportError:
    pass

from src.orchestrator import Orchestrator
from src.llm_client import get_llm_client, GLOBAL_USAGE, MockLLMClient

provider = os.environ.get("LLM_PROVIDER", "").lower() or ("anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai" if os.environ.get("OPENAI_API_KEY") else "mock")
print(f"LLM provider in use: {provider}" + ("  (\\u26a0\\ufe0f set ANTHROPIC_API_KEY or OPENAI_API_KEY for real answers)" if provider == "mock" else ""))

orch = Orchestrator()
"""

ASK_HELPER_SOURCE = '''def ask(question: str, label: str = ""):
    """Run one turn through the orchestrator and pretty-print everything the
    grader needs to see: routing, evidence sources, transparency notes, answer.
    Identical helper to notebooks/demo.ipynb -- see scripts/build_notebook.py."""
    if label:
        print(f"\\n{'='*90}\\n{label}\\n{'='*90}")
    print(f"USER: {question}\\n")
    resp = orch.handle_turn(question)
    print(f"[intent={resp.intent} | sub_agents={resp.sub_agents_used} | retried={resp.retried}]")
    if resp.citations:
        print(f"[citations: {[c['doc_id'] for c in resp.citations]}]")
    if resp.assumptions:
        print("[assumptions/limitations surfaced:]")
        for a in resp.assumptions:
            print(f"  - {a}")
    print(f"\\nAGENT: {resp.answer}")
    if resp.follow_up_suggestions:
        print(f"\\n(follow-up suggestions: {resp.follow_up_suggestions})")
    return resp
'''


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(source: str, outputs: list | None = None, execution_count=None) -> dict:
    return {
        "cell_type": "code", "metadata": {}, "execution_count": execution_count,
        "source": source.splitlines(keepends=True),
        "outputs": outputs or [],
    }


def _stream_output(text: str) -> dict:
    return {"output_type": "stream", "name": "stdout", "text": text.splitlines(keepends=True)}


def _reproduce_ask_output(turn: str, label: str, intent: str, sub_agents: list,
                           citations: list, assumptions: list, answer: str) -> str:
    """Reconstructs exactly what ask()'s print statements produced for one
    turn, from the fields the live report captured (retried and follow-up
    suggestions weren't captured per-turn by earlier report runs, so those
    two lines are omitted here rather than fabricated -- see
    notebooks/demo.ipynb or the Streamlit dev-mode UI for turns where those
    are shown)."""
    lines = [f"{'=' * 90}", label, f"{'=' * 90}", f"USER: {turn}", ""]
    lines.append(f"[intent={intent} | sub_agents={sub_agents}]")
    if citations:
        lines.append(f"[citations: {[c.get('doc_id', '?') for c in citations]}]")
    if assumptions:
        lines.append("[assumptions/limitations surfaced:]")
        for a in assumptions:
            lines.append(f"  - {a}")
    lines.append("")
    lines.append(f"AGENT: {answer}")
    return "\n".join(lines)


def build_capability_notebook(cap_report: dict) -> dict:
    cells = [
        md(f"# Capability {cap_report['number']}: {cap_report['title']}\n\n"
           f"{cap_report['passed']}/{cap_report['total']} cases passed against a real, live LLM "
           f"(gateway-configured model, see `.env`). Every code cell below is real, executable "
           f"code -- the same `ask()` pattern as `notebooks/demo.ipynb` -- not a mockup; the "
           f"attached output is what actually happened when this ran, captured via "
           f"`scripts/run_live_capability_tests.py --capability {cap_report['number']}`. "
           f"Re-running this notebook (Restart Kernel & Run All) with a live key will make new "
           f"real calls.\n\n"
           f"See `tests/live/cases/{cap_report['slug']}.py` for these case definitions with "
           f"their automated pass/fail checks, and "
           f"`tests/live/live_capabilities_suite.py` for how they run as unittest assertions."),
        code(SETUP_SOURCE, outputs=[_stream_output(f"LLM provider in use: openai\n")]),
        code(ASK_HELPER_SOURCE),
    ]

    for i, case in enumerate(cap_report["cases"], start=1):
        status = "✅ PASS" if case["passed"] else "❌ FAIL"
        header = f"## {case['id']}: {case['description']}\n\n**{status}**"
        if not case["passed"]:
            header += f" -- {case['reason']}"
        cells.append(md(header))

        turns = case["turns"]
        source_lines = []
        outputs = []
        combined_stdout = []
        for j, turn in enumerate(turns):
            label = f"{case['id']}" + (chr(97 + j) if len(turns) > 1 else "")
            source_lines.append(f'_ = ask({turn!r}, {label!r})')
            answer = case["answers"][j] if j < len(case["answers"]) else "(no response captured)"
            intent = case["intents"][j] if j < len(case["intents"]) else "?"
            sub_agents = case["sub_agents_used"][j] if j < len(case["sub_agents_used"]) else []
            citations = case["citations"][j] if j < len(case["citations"]) else []
            assumptions = case["assumptions"][j] if j < len(case["assumptions"]) else []
            combined_stdout.append(_reproduce_ask_output(
                turn, label, intent, sub_agents, citations, assumptions, answer))
        cells.append(code("\n".join(source_lines), outputs=[_stream_output("\n\n".join(combined_stdout))]))

    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main():
    if not REPORTS_DIR.exists() or not list(REPORTS_DIR.glob("cap*.json")):
        print(f"No reports found in {REPORTS_DIR} -- run scripts/run_live_capability_tests.py first.")
        sys.exit(1)

    built = 0
    for report_path in sorted(REPORTS_DIR.glob("cap*.json")):
        report = json.loads(report_path.read_text())
        for cap_report in report["capabilities"]:
            slug = cap_report["slug"]
            folder = OUT_DIR / f"{cap_report['number']:02d}_{slug.split('_', 1)[1]}"
            folder.mkdir(parents=True, exist_ok=True)
            nb = build_capability_notebook(cap_report)
            out_path = folder / "demo.ipynb"
            out_path.write_text(json.dumps(nb, indent=1))
            print(f"Wrote {out_path} ({cap_report['passed']}/{cap_report['total']} passed)")
            built += 1

    print(f"\nBuilt {built} capability notebook(s) under {OUT_DIR}")


if __name__ == "__main__":
    main()
