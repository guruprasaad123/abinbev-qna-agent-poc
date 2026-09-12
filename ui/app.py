"""
Streamlit UI for the AB InBev Q&A agent.

Two modes, toggled in the sidebar:
  - Normal: a clean chat interface.
  - Developer mode: a live, step-by-step trace of the orchestrator's actual
    workflow for the turn being answered right now -- intent/entity
    resolution (including auto-corrected abbreviations/aliases/typos),
    routing to sub-agents, each sub-agent's tool usage and evidence, and
    synthesis (including whether a validation retry fired).

The trace is not a replay or a mock -- it's built on Orchestrator.handle_turn's
`on_step` callback (src/orchestrator.py), invoked live from inside the real,
blocking call, so what you see is what the orchestrator is actually doing,
in order, as it happens. `on_step` is purely observational: every other
caller (chat_cli.py, the notebook, the tests) omits it and is unaffected.

Run: streamlit run ui/app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

import streamlit as st

try:
    from dotenv import load_dotenv  # optional: picks up a .env file if python-dotenv is installed
    load_dotenv()
except ImportError:
    pass

from src.orchestrator import Orchestrator
from src.llm_client import GLOBAL_USAGE

st.set_page_config(page_title="AB InBev Q&A Agent", page_icon="🍺", layout="wide")

SUBAGENT_ICONS = {"structured": "📊", "unstructured": "📄", "web": "🌐", "coding": "🧮"}


def _init_state():
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator()
    if "history" not in st.session_state:
        st.session_state.history = []  # list of {role, content, meta?}


def _provider_label() -> str:
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        provider = ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                     else "openai" if os.environ.get("OPENAI_API_KEY") else "mock")
    return provider


def _render_trace_step(status, phase: str, detail: dict):
    """Called live, mid-turn, from Orchestrator.handle_turn's on_step hook."""
    if phase == "nlu":
        entities = detail.get("entities") or {}
        entity_bits = []
        for label, key in (("zone", "zones"), ("country", "countries"), ("brand", "brands")):
            if entities.get(key):
                entity_bits.append(f"{label}={entities[key]}")
        if entities.get("kpis"):
            entity_bits.append(f"kpi={entities['kpis']}")
        if entities.get("period"):
            entity_bits.append(f"period={entities['period']}")
        status.update(label=f"🧭 Orchestrator: classified intent = **{detail['intent']}**")
        with status:
            st.write(f"Language detected: `{detail.get('language', 'en')}`")
            if entity_bits:
                st.write("Resolved entities: " + ", ".join(entity_bits))
            for c in detail.get("corrections", []):
                st.write(
                    f":orange[**auto-corrected**] {c['dimension']} → normalized to "
                    f"**{c['resolved_to']}** (not written verbatim in your message — "
                    f"likely an abbreviation, alias, or typo the model resolved)"
                )
            if detail.get("needs_clarification"):
                st.write(":blue[Ambiguous/incomplete request — asking for clarification instead of guessing]")

    elif phase == "routing":
        needed = detail.get("needed_subagents", [])
        icons = " ".join(SUBAGENT_ICONS.get(n, "🛠️") for n in needed)
        status.update(label=f"🔀 Routing to sub-agent(s): {', '.join(needed) or 'none'} {icons}")

    elif phase == "subagent":
        name = detail["name"]
        icon = SUBAGENT_ICONS.get(name, "🛠️")
        status.update(label=f"{icon} {name.title()} agent: done")
        with status:
            st.markdown(f"**{name} agent — evidence retrieved:**")
            evidence = detail.get("evidence", "")
            st.code(evidence[:2000] + ("..." if len(evidence) > 2000 else ""), language="markdown")
            if detail.get("citations"):
                st.write("Citations: " + ", ".join(c.get("doc_id", "?") for c in detail["citations"]))
            for n in detail.get("notes") or []:
                st.write(f":gray[note] {n}")

    elif phase == "synthesis":
        if detail.get("status") == "start":
            status.update(label="✍️ Synthesizing final answer from gathered evidence...")
        elif detail.get("status") == "retry":
            status.update(label=f"🔁 Validation failed — retrying synthesis ({detail.get('reason', '')})")
        elif detail.get("status") == "done":
            note = " after 1 retry" if detail.get("retried") else ""
            status.update(label=f"✍️ Synthesis complete{note}")


def main():
    _init_state()

    with st.sidebar:
        st.title("AB InBev Q&A Agent")
        st.caption("Multi-agent enterprise Q&A prototype")
        dev_mode = st.toggle(
            "🛠️ Developer mode", value=False,
            help="Show the orchestrator's live workflow: intent/entity resolution "
                 "(incl. auto-corrections), sub-agent routing & tool usage, synthesis.",
        )
        st.divider()
        st.caption(f"LLM provider: `{_provider_label()}`")
        if st.button("Reset conversation"):
            st.session_state.orchestrator = Orchestrator()
            st.session_state.history = []
            st.rerun()
        if dev_mode:
            st.divider()
            st.caption("Cumulative usage this session")
            st.json(GLOBAL_USAGE.summary(), expanded=False)

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if dev_mode and msg.get("meta"):
                with st.expander("🔍 Full response metadata"):
                    st.json(msg["meta"])

    user_message = st.chat_input("Ask about AB InBev's revenue, volume, EBITDA, brands...")
    if not user_message:
        return

    st.session_state.history.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        meta = None
        if dev_mode:
            status = st.status("Working...", expanded=True)
            resp = st.session_state.orchestrator.handle_turn(
                user_message, on_step=lambda phase, detail: _render_trace_step(status, phase, detail)
            )
            status.update(label="✅ Turn complete", state="complete", expanded=False)
        else:
            with st.spinner("Thinking..."):
                resp = st.session_state.orchestrator.handle_turn(user_message)

        st.markdown(resp.answer)
        if resp.follow_up_suggestions:
            st.caption("💡 " + " · ".join(resp.follow_up_suggestions))

        meta = {
            "intent": resp.intent, "sub_agents_used": resp.sub_agents_used,
            "citations": resp.citations, "assumptions": resp.assumptions,
            "retried": resp.retried, "raw_nlu": resp.raw_nlu,
        }
        if dev_mode:
            with st.expander("🔍 Full response metadata"):
                st.json(meta)

    st.session_state.history.append({"role": "assistant", "content": resp.answer, "meta": meta})


if __name__ == "__main__":
    main()
