"""
Interactive terminal chat with the agent -- the fastest way to try it manually.

Usage:
    export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY / LLM_PROVIDER=mock
    python3 scripts/chat_cli.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import json

try:
    from dotenv import load_dotenv  # optional: picks up a .env file if python-dotenv is installed
    # override=False (the default, made explicit here) means a real
    # environment variable (e.g. `export OPENAI_API_KEY=...` in the shell)
    # always wins over .env -- .env only fills in whatever isn't already set.
    load_dotenv(override=False)
except ImportError:
    pass

from src.orchestrator import Orchestrator
from src.llm_client import GLOBAL_USAGE


def main():
    provider = os.environ.get("LLM_PROVIDER", "").lower() or (
        "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else
        "openai" if os.environ.get("OPENAI_API_KEY") else "mock"
    )
    print(f"[LLM provider: {provider}]" + ("  (mock mode -- set an API key for real answers)" if provider == "mock" else ""))
    print("Type your question ('usage' for cost/latency summary, 'exit' to quit).\n")

    orch = Orchestrator()
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit"):
            break
        if q.lower() == "usage":
            print(json.dumps(GLOBAL_USAGE.summary(), indent=2))
            continue

        resp = orch.handle_turn(q)
        print(f"\n[intent={resp.intent} | sub_agents={resp.sub_agents_used}]")
        if resp.assumptions:
            for a in resp.assumptions:
                print(f"  ! {a}")
        print(f"\nAgent: {resp.answer}")
        if resp.follow_up_suggestions:
            print(f"\n(you might also ask: {'; '.join(resp.follow_up_suggestions)})")
        print()


if __name__ == "__main__":
    main()
