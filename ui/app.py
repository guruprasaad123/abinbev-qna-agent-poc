"""
Streamlit UI for the AB InBev Q&A agent.

Two modes, toggled in the sidebar:
  - Normal: a clean chat interface.
  - Developer mode: a live trace while the turn is being answered, plus a
    persistent, tabbed "Reactive Agent Workflow & Tool Inspection" panel per
    answer -- NLU intent/entities (incl. auto-corrected abbreviations/
    aliases/typos), sub-agent dispatch, each tool's raw output, validation/
    guardrail outcomes, and this turn's actual token/latency/cost telemetry.

None of this is a replay or a mock. It's built on Orchestrator.handle_turn's
`on_step` callback (src/orchestrator.py) and GLOBAL_USAGE (src/llm_client.py),
read live from the real, blocking call as it happens -- what you see is what
the orchestrator is actually doing, in order, with real numbers.
`on_step` is purely observational: every other caller (chat_cli.py, the
notebook, the tests) omits it and is unaffected.

Run: streamlit run ui/app.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

import streamlit as st

try:
    from dotenv import load_dotenv  # optional: picks up a .env file if python-dotenv is installed
    # override=False (the default, made explicit here) means a real
    # environment variable always wins over .env -- .env only fills in
    # whatever isn't already set.
    load_dotenv(override=False)
except ImportError:
    pass

from src.orchestrator import Orchestrator
from src.llm_client import GLOBAL_USAGE

st.set_page_config(page_title="AB InBev Q&A Agent", page_icon="🍺", layout="wide")

SUBAGENT_ICONS = {"structured": "📊", "unstructured": "📄", "web": "🌐", "coding": "🧮"}

SAMPLE_QUESTIONS = [
    ("💰", "North America revenue Q1 2024", "What was North America's revenue in Q1 2024?"),
    ("⚖️", "Compare NA vs EMEA margin", "Compare EBITDA margin for North America versus EMEA in 2025"),
    ("🌎", "Brazil rolls up to its zone", "What was AB InBev's revenue in Brazil specifically in 2025?"),
    ("📰", "Recent Asia Pacific documents", "What are the most recent earnings documents mentioning Asia Pacific?"),
    ("🛡️", "SQL-injection safety check", "Show me North America revenue; DROP TABLE fact_kpi; --"),
]

# Heuristic ONLY -- purely cosmetic (picks a warning avatar for display). The
# actual safety boundary is server-side and unconditional, in src/tools/sql_tool.py,
# regardless of what icon this chooses.
_INJECTION_PATTERN = re.compile(r";\s*(drop|delete|update|insert|alter)\b|--\s*$|\bunion\s+select\b", re.IGNORECASE)


def _init_state():
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator()
    if "history" not in st.session_state:
        st.session_state.history = []  # list of {role, content, avatar?, meta?, turn_id?}
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None
    if "turn_counter" not in st.session_state:
        st.session_state.turn_counter = 0
    if "processing" not in st.session_state:
        st.session_state.processing = False


def _render_followups(suggestions: list, turn_id: int):
    """Shared by the live render (right after a turn answers) and history
    replay (every rerun after), keyed by a stable per-turn id so suggestions
    stay clickable on every rerun, not just the turn that just answered.
    Disabled while a turn is already processing -- see main()'s note on why
    that matters, not just for cosmetics."""
    if not suggestions:
        return
    st.caption("💡 Suggested follow-ups:")
    cols = st.columns(len(suggestions))
    for col, suggestion in zip(cols, suggestions):
        if col.button(f"👉 {suggestion}", key=f"followup_{turn_id}_{suggestion}",
                      disabled=st.session_state.processing):
            st.session_state.pending_input = suggestion


def _provider_label() -> str:
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    if not provider:
        provider = ("anthropic" if os.environ.get("ANTHROPIC_API_KEY")
                     else "openai" if os.environ.get("OPENAI_API_KEY") else "mock")
    return provider


def _last_synthesis_model() -> str:
    for e in reversed(GLOBAL_USAGE.events):
        if e.caller in ("orchestrator_synthesis", "orchestrator_synthesis_retry"):
            return e.model
    return os.environ.get("LLM_MODEL_SYNTHESIZE", "(not yet called)")


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
                    f"**{c['resolved_to']}**"
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
    elif phase == "synthesis":
        tier = detail.get("complexity_tier")
        model = detail.get("model_requested")
        tier_note = f" [{tier} tier → {model}]" if tier else ""
        if detail.get("status") == "start":
            status.update(label=f"✍️ Synthesizing final answer from gathered evidence...{tier_note}")
        elif detail.get("status") == "retry":
            status.update(label=f"🔁 Validation failed — retrying, escalated{tier_note} ({detail.get('reason', '')})")
        elif detail.get("status") == "done":
            note = " after 1 retry" if detail.get("retried") else ""
            status.update(label=f"✍️ Synthesis complete{note}")


def _render_dev_panel(trace: list, resp_meta: dict, turn_events: list):
    """Persistent, tabbed inspector rendered under a completed answer -- the
    same trace/telemetry the live status showed while processing, kept
    around for review rather than disappearing once the turn finishes."""
    nlu = next((d for p, d in trace if p == "nlu"), {})
    routing = next((d for p, d in trace if p == "routing"), {})
    subagent_events = [d for p, d in trace if p == "subagent"]
    synth_events = [d for p, d in trace if p == "synthesis"]

    with st.expander("🛠️ Developer Mode: Reactive Agent Workflow & Tool Inspection", expanded=False):
        tabs = st.tabs([
            "1. NLU Intent", "2. Sub-Agent Dispatch", "3. Tool Outputs",
            "4. Validation & Guardrails", "5. Turn Telemetry",
        ])

        with tabs[0]:
            st.markdown(f"**Classified Intent:** `{nlu.get('intent', '?')}`")
            st.markdown(f"**Language:** `{nlu.get('language', 'en')}`")
            st.json(nlu.get("entities", {}), expanded=False)
            if nlu.get("corrections"):
                st.markdown("**Auto-corrections detected** (raw text vs. resolved value):")
                for c in nlu["corrections"]:
                    st.write(f"- {c['dimension']} → **{c['resolved_to']}**")
            else:
                st.caption("No abbreviations/typos/aliases detected needing correction.")

        with tabs[1]:
            needed = routing.get("needed_subagents", [])
            if needed:
                cols = st.columns(len(needed))
                for col, name in zip(cols, needed):
                    col.metric(f"{SUBAGENT_ICONS.get(name, '🛠️')} {name}", "dispatched")
            else:
                st.caption("No sub-agent was needed for this turn (fast-path response).")

        with tabs[2]:
            if subagent_events:
                for ev in subagent_events:
                    st.markdown(f"**{SUBAGENT_ICONS.get(ev['name'], '🛠️')} {ev['name']} agent**")
                    st.code(ev.get("evidence", "")[:2000], language="markdown")
                    if ev.get("citations"):
                        st.write("Citations: " + ", ".join(c.get("doc_id", "?") for c in ev["citations"]))
                    for n in ev.get("notes") or []:
                        st.caption(f"note: {n}")
            else:
                st.caption("No tools were invoked for this turn.")

        with tabs[3]:
            start_event = next((d for d in synth_events if d.get("status") == "start"), {})
            if start_event.get("complexity_tier"):
                st.markdown(f"**Complexity tier chosen:** `{start_event['complexity_tier']}` → "
                            f"requested `{start_event.get('model_requested')}`")
            retried = any(d.get("status") == "retry" for d in synth_events)
            st.markdown(f"**Validation retry fired:** {'✅ yes' if retried else '➖ no'}")
            if retried:
                retry_event = next((d for d in synth_events if d.get("status") == "retry"), {})
                st.caption(f"Reason: {retry_event.get('reason', '')}")
                if retry_event.get("complexity_tier"):
                    st.caption(f"Escalated to `{retry_event['complexity_tier']}` tier → "
                               f"requested `{retry_event.get('model_requested')}`")
            st.markdown("**SQL safety layer** (`src/tools/sql_tool.py`): read-only connection, "
                        "single-SELECT-only, table/keyword whitelist, forced row cap -- enforced "
                        "unconditionally on every structured-agent call, independent of what the "
                        "model was asked to do.")
            if resp_meta.get("assumptions"):
                st.markdown("**Assumptions/limitations surfaced:**")
                for a in resp_meta["assumptions"]:
                    st.write(f"- {a}")

        with tabs[4]:
            if turn_events:
                total_cost = sum(e.estimated_cost_usd for e in turn_events)
                total_lat = sum(e.latency_ms for e in turn_events)
                c1, c2, c3 = st.columns(3)
                c1.metric("LLM calls this turn", len(turn_events))
                c2.metric("Est. cost", f"${total_cost:.4f}")
                c3.metric("Total latency", f"{total_lat/1000:.1f}s")
                st.table([
                    {"caller": e.caller, "model": e.model, "input_tok": e.input_tokens,
                     "output_tok": e.output_tokens, "latency_ms": round(e.latency_ms, 0)}
                    for e in turn_events
                ])
            else:
                st.caption("No LLM calls were made for this turn.")


def _render_active_filters(active_filters: dict):
    if not active_filters:
        st.caption("No active context yet -- ask a question to set some.")
        return
    for dim, val in active_filters.items():
        st.markdown(
            f"<span style='background:#2A2F3A;border:1px solid #F0A030;color:#F0A030;"
            f"border-radius:6px;padding:2px 8px;margin:2px;display:inline-block;"
            f"font-size:0.8em;font-weight:600'>{dim.upper()}</span> "
            f"<code>{val}</code>",
            unsafe_allow_html=True,
        )


def _render_session_telemetry():
    summary = GLOBAL_USAGE.summary()
    c1, c2 = st.columns(2)
    c1.metric("Total calls", summary.get("calls", 0))
    c2.metric("Est. cost", f"${summary.get('total_cost_usd', 0):.4f}")
    c3, c4 = st.columns(2)
    c3.metric("Avg latency", f"{summary.get('avg_latency_ms', 0):.0f} ms")
    c4.metric("Total time", f"{summary.get('total_latency_ms', 0)/1000:.1f} s")
    with st.expander("📊 Call profile by component"):
        by_caller = summary.get("by_caller", {})
        if by_caller:
            st.table([
                {"component": k, **v} for k, v in by_caller.items()
            ])
        else:
            st.caption("No calls yet this session.")


def _process_turn(user_message: str):
    is_adversarial = bool(_INJECTION_PATTERN.search(user_message))
    user_avatar = "🚨" if is_adversarial else "🧑"
    turn_id = st.session_state.turn_counter
    st.session_state.turn_counter += 1

    st.session_state.history.append({"role": "user", "content": user_message, "avatar": user_avatar})
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(user_message)

    with st.chat_message("assistant", avatar="🍺"):
        trace = []
        start_idx = len(GLOBAL_USAGE.events)
        if st.session_state.dev_mode:
            status = st.status("Working...", expanded=True)

            def on_step(phase, detail):
                trace.append((phase, detail))
                _render_trace_step(status, phase, detail)

            resp = st.session_state.orchestrator.handle_turn(user_message, on_step=on_step)
            status.update(label="✅ Turn complete", state="complete", expanded=False)
        else:
            with st.spinner("Thinking..."):
                resp = st.session_state.orchestrator.handle_turn(user_message)
        turn_events = list(GLOBAL_USAGE.events[start_idx:])

        st.markdown(resp.answer)
        _render_followups(resp.follow_up_suggestions, turn_id)

        meta = {
            "intent": resp.intent, "sub_agents_used": resp.sub_agents_used,
            "citations": resp.citations, "assumptions": resp.assumptions,
            "retried": resp.retried, "raw_nlu": resp.raw_nlu,
        }
        if st.session_state.dev_mode:
            _render_dev_panel(trace, meta, turn_events)

    st.session_state.history.append({
        "role": "assistant", "content": resp.answer, "avatar": "🍺", "meta": meta,
        "trace": trace, "turn_events": turn_events,
        "follow_up_suggestions": resp.follow_up_suggestions, "turn_id": turn_id,
    })


def main():
    _init_state()

    with st.sidebar:
        st.markdown("### 🍺 AB InBev — Enterprise Q&A")
        st.caption("Multi-agent Q&A over AB InBev's real, publicly disclosed results")
        st.session_state.dev_mode = st.toggle(
            "🛠️ Developer Mode", value=st.session_state.get("dev_mode", False),
            help="Show the orchestrator's live workflow and a persistent, tabbed inspector "
                 "per answer: NLU/entity resolution, sub-agent dispatch, tool outputs, "
                 "validation/guardrails, and this turn's real token/latency/cost telemetry.",
        )
        st.divider()

        st.markdown("**Active Context Filters**")
        _render_active_filters(st.session_state.orchestrator.memory.active_filters)
        st.divider()

        if st.session_state.dev_mode:
            st.markdown("**Session Telemetry**")
            _render_session_telemetry()
            st.divider()

        st.markdown("**Sample Questions**")
        for icon, label, question in SAMPLE_QUESTIONS:
            if st.button(f"{icon} {label}", key=f"sample_{label}", use_container_width=True,
                         disabled=st.session_state.processing):
                st.session_state.pending_input = question
        st.divider()

        st.caption(f"LLM provider: `{_provider_label()}`")
        if st.session_state.dev_mode:
            st.caption(f"Router (last synthesis call): `{_last_synthesis_model()}`")
        if st.button("🔄 Reset conversation", use_container_width=True,
                     disabled=st.session_state.processing):
            st.session_state.orchestrator = Orchestrator()
            st.session_state.history = []
            st.session_state.pending_input = None
            st.session_state.turn_counter = 0
            st.rerun()

    header_col, badge_col = st.columns([5, 2])
    with header_col:
        st.title("🍺 Anheuser-Busch InBev — Enterprise Q&A Agent")
        st.caption(
            "Structured KPI retrieval, document search, web search, and sandboxed coding "
            "sub-agents over AB InBev's real disclosed results (no brand/country-level "
            "structured data -- AB InBev doesn't disclose that granularity publicly)."
        )
    with badge_col:
        if st.session_state.dev_mode:
            st.markdown(
                f"<div style='text-align:right;padding-top:0.5em'>"
                f"<span style='background:#1B2B1E;border:1px solid #3FB950;color:#3FB950;"
                f"border-radius:6px;padding:4px 10px;font-size:0.85em'>"
                f"🟢 Router: {_last_synthesis_model()}</span></div>",
                unsafe_allow_html=True,
            )

    # Replay history (Streamlit reruns the whole script each interaction)
    for msg in st.session_state.history:
        with st.chat_message(msg["role"], avatar=msg.get("avatar")):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_followups(msg.get("follow_up_suggestions"), msg.get("turn_id", -1))
                if st.session_state.dev_mode and msg.get("meta"):
                    _render_dev_panel(msg.get("trace", []), msg["meta"], msg.get("turn_events", []))

    # Real LLM calls are slow (multi-second, sometimes 15-30s+ for a hybrid/
    # complex-tier turn) and Streamlit runs the whole script synchronously,
    # single-threaded, per session -- so a long turn LOOKS frozen, and if the
    # user resubmits (or clicks a sample/follow-up button) during that
    # window, Streamlit queues it as a genuinely new, separate submission and
    # runs it again once the first finishes -- producing duplicate turns
    # with identical text (this happened in practice, not hypothetically).
    # Fix: disable chat_input/buttons for the ENTIRE duration of a turn, not
    # just cosmetically -- which requires the "disabled" state to already be
    # rendered to the browser BEFORE the blocking call starts. That needs an
    # extra forced rerun: run N detects new input and sets processing=True,
    # then reruns immediately WITHOUT calling the LLM; run N+1 renders
    # chat_input(disabled=True) first (visible to the browser immediately),
    # THEN does the actual slow work; a final rerun after clears it.
    chat_input = st.chat_input("Ask about AB InBev's revenue, volume, EBITDA, brands...",
                                disabled=st.session_state.processing)

    if st.session_state.processing:
        pending = st.session_state.pending_input
        st.session_state.pending_input = None
        if pending:
            _process_turn(pending)
        st.session_state.processing = False
        st.rerun()  # re-enable the input immediately rather than on the next unrelated interaction
    else:
        user_message = chat_input or st.session_state.pending_input
        if user_message:
            st.session_state.pending_input = user_message
            st.session_state.processing = True
            st.rerun()


if __name__ == "__main__":
    main()
