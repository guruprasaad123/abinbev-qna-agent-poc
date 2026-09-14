"""
Anheuser-Busch InBev (AB InBev) — Enterprise Q&A Agent
Interactive Streamlit Application with Executive & Developer Modes.
Optimized for Dark & Light Themes with Rich Aesthetics and Observability.
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import time
import streamlit as st

from src.orchestrator import Orchestrator
from src.llm_client import GLOBAL_USAGE, get_llm_client
from src.config import ALL_BRANDS, ALL_COUNTRIES, ALL_CHANNELS, KPI_CATALOG, DOMAIN_DESCRIPTION

# ---------------------------------------------------------------------- Page Configuration
st.set_page_config(
    page_title="AB InBev — Enterprise Q&A Agent",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------- Modern Dark-Mode-First Theme
st.markdown("""
<style>
    /* Global Typography & Palette */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Title with Gold/White Gradient */
    .main-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #e2e8f0 50%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.25rem;
        letter-spacing: -0.5px;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
        line-height: 1.5;
    }

    /* Model & System Status Pills */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(245, 158, 11, 0.35);
        border-radius: 24px;
        padding: 6px 14px;
        font-size: 0.8rem;
        color: #fbbf24;
        font-weight: 600;
        backdrop-filter: blur(8px);
        white-space: nowrap;
    }
    .live-dot {
        width: 8px;
        height: 8px;
        background-color: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
        display: inline-block;
    }

    /* Metric Cards: Translucent Slate, Glowing Accents */
    [data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 12px 14px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
    }

    /* Filter Badges */
    .filter-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 0.78rem;
        font-family: monospace;
        margin: 2px 4px 2px 0;
    }

    /* Welcome Hero Cards */
    .hero-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .hero-card:hover {
        border-color: rgba(245, 158, 11, 0.4);
        background: rgba(30, 41, 59, 0.75);
    }
    .hero-card-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 4px;
    }
    .hero-card-desc {
        font-size: 0.82rem;
        color: #94a3b8;
        line-height: 1.4;
    }

    /* Subtle divider */
    .custom-divider {
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------- State Initialization
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "active_query" not in st.session_state:
    st.session_state.active_query = None

orch: Orchestrator = st.session_state.orchestrator


# ---------------------------------------------------------------------- Sidebar
with st.sidebar:
    # Crisp, self-contained SVG emblem (never breaks on network/CORS)
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
        <div style="background: linear-gradient(135deg, #b45309 0%, #d97706 50%, #f59e0b 100%); width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35);">
            🍺
        </div>
        <div>
            <div style="font-weight: 800; font-size: 1.25rem; letter-spacing: -0.5px; color: #f8fafc; line-height: 1.1;">AB InBev</div>
            <div style="font-size: 0.70rem; text-transform: uppercase; letter-spacing: 1.5px; color: #f59e0b; font-weight: 700;">Enterprise Q&A</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Developer Mode Toggle
    dev_mode = st.toggle("🛠️ **Developer Mode**", value=True, help="Toggle reactive agentic workflow: reveals NLU intent parsing, sub-agent dispatches, generated SQL queries, and validation telemetry.")

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # Active Conversation Memory Filter State
    st.markdown("#### **Active Context Filters**")
    filters = orch.memory.active_filters
    if filters:
        for k, v in filters.items():
            st.markdown(f"<span class='filter-badge'>{k.upper()}</span> `{v}`", unsafe_allow_html=True)
    else:
        st.caption("No filters active. Multi-turn context accumulates automatically.")

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # Live Session Telemetry
    st.markdown("#### **Session Telemetry**")
    summary = GLOBAL_USAGE.summary()
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.metric("Total Calls", summary.get("calls", 0))
        st.metric("Avg Latency", f"{summary.get('avg_latency_ms', 0):.0f} ms")
    with col_t2:
        st.metric("Est. Cost", f"${summary.get('total_cost_usd', 0.0):.4f}")
        st.metric("Total Time", f"{summary.get('total_latency_ms', 0) / 1000:.1f} s")

    with st.expander("📊 Call Profile by Component", expanded=False):
        by_caller = summary.get("by_caller", {})
        if by_caller:
            for caller, stats in by_caller.items():
                st.markdown(f"**`{caller}`**")
                st.caption(f"{stats['calls']} calls | {stats['input_tokens']} in / {stats['output_tokens']} out | ${stats['cost_usd']:.4f}")
        else:
            st.caption("No LLM calls recorded yet.")

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # Quick Sample Queries
    st.markdown("#### **Sample Questions**")
    sample_queries = [
        ("💰 Corona Revenue in Mexico", "What was Corona net revenue in Mexico in 2025?"),
        ("📅 Multi-turn Ellipsis Follow-up", "What about in 2024?"),
        ("📉 YoY Poor Performance Analysis", "In which year did AB InBev perform poorly comparatively?"),
        ("🥇 Corona Cero Olympic Strategy", "What is AB InBev's strategy for Corona Cero and what was its volume in 2025?"),
        ("🌐 Competitor Benchmark (Heineken)", "What was Heineken's global beer volume in 2025?"),
        ("🛡️ SQL Injection Safety Audit", "Show me Stella Artois revenue; DROP TABLE fact_sales; --"),
        ("📋 Metadata & Dataset Discovery", "Which KPIs and datasets are available?"),
    ]
    for label, query in sample_queries:
        if st.button(label, key=f"btn_{label}", use_container_width=True):
            st.session_state.active_query = query
            st.rerun()

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    if st.button("🔄 Reset Conversation Memory", use_container_width=True):
        st.session_state.orchestrator = Orchestrator()
        st.session_state.messages = []
        GLOBAL_USAGE.reset()
        st.rerun()


# ---------------------------------------------------------------------- Main Canvas Header
col_h1, col_h2 = st.columns([0.70, 0.30])
with col_h1:
    st.markdown('<div class="main-title">🍺 Anheuser-Busch InBev — Enterprise Q&A Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Multi-agent intelligence over 8 megabrands across 8 global markets, Modern & Traditional Trade, and the proprietary BEES digital marketplace.</div>', unsafe_allow_html=True)

with col_h2:
    client = orch.llm_router
    model_disp = getattr(client, 'model_name', 'mock')
    status_info = getattr(client, 'get_status', lambda: {})()
    is_fallback = status_info.get("auth_failed", False) or model_disp == "mock"

    if is_fallback:
        st.markdown("""
        <div style='text-align: right; padding-top: 10px;'>
            <div class='status-pill' style='border-color: rgba(245, 158, 11, 0.45); color: #fbbf24; background: rgba(30, 41, 59, 0.85);'>
                <span style='width: 8px; height: 8px; background-color: #f59e0b; border-radius: 50%; display: inline-block; box-shadow: 0 0 6px #f59e0b;'></span>
                <span>Deterministic Fallback Mode</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='text-align: right; padding-top: 10px;'>
            <div class='status-pill'>
                <span class='live-dot'></span>
                <span>Live: {model_disp}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------- Welcome Screen (Rendered if no messages yet)
if len(st.session_state.messages) == 0:
    st.markdown("### **Welcome! Explore AB InBev Commercial & Financial Analytics**")
    st.caption("Select a starter query below or ask any business question in natural language.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="hero-card">
            <div class="hero-card-title">📈 Financial & Volume Performance</div>
            <div class="hero-card-desc">Query Net Revenue ($USD), Volume in hectoliters (hL), Gross Margin %, and Market Share % across brands, channels, and periods.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Run: 'What was Corona net revenue in Mexico in 2025?'", key="hero_1", use_container_width=True):
            st.session_state.active_query = "What was Corona net revenue in Mexico in 2025?"
            st.rerun()

        st.markdown("""
        <div class="hero-card">
            <div class="hero-card-title">🥇 Strategic Initiatives & Beyond Beer</div>
            <div class="hero-card-desc">Retrieve corporate publications on Corona Cero's Worldwide Olympic Partnership, TaDa D2C delivery, and BEES digital marketplace growth.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Run: 'What is AB InBev's strategy for Corona Cero & its 2025 volume?'", key="hero_2", use_container_width=True):
            st.session_state.active_query = "What is AB InBev's strategy for Corona Cero and what was its volume in 2025?"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="hero-card">
            <div class="hero-card-title">🌐 External Competitor Benchmarking</div>
            <div class="hero-card-desc">External queries trigger public web search sub-agents while transparently stating internal data boundaries (e.g. Heineken, Carlsberg).</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Run: 'What was Heineken's global beer volume in 2025?'", key="hero_3", use_container_width=True):
            st.session_state.active_query = "What was Heineken's global beer volume in 2025?"
            st.rerun()

        st.markdown("""
        <div class="hero-card">
            <div class="hero-card-title">🛡️ Strict SQL Safety & Guardrails</div>
            <div class="hero-card-desc">Enforces single-SELECT statement whitelists, table whitelists, and read-only database connections, blocking malicious injections.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Run: 'Show me Stella Artois revenue; DROP TABLE fact_sales; --'", key="hero_4", use_container_width=True):
            st.session_state.active_query = "Show me Stella Artois revenue; DROP TABLE fact_sales; --"
            st.rerun()

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # In-Scope Catalog Chips
    col_sc1, col_sc2 = st.columns([0.5, 0.5])
    with col_sc1:
        st.markdown("**Core Brands in Scope:**")
        st.markdown("`Corona` • `Stella Artois` • `Budweiser` • `Michelob ULTRA` • `Brahma` • `Bud Light` • `Hoegaarden` • `Corona Cero 0.0%`")
    with col_sc2:
        st.markdown("**Commercial Channels & Markets:**")
        st.markdown("`BEES & E-Commerce` • `On-Premise` • `Modern Trade` • `Traditional Trade` | `US` • `Mexico` • `Brazil` • `Belgium` • `UK` • `China` • `Canada` • `India`")

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------- Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(f"**{msg['content']}**")
        else:
            # Assistant Response
            st.markdown(msg["content"])

            # Render Follow-Up Suggestion Chips
            if msg.get("follow_ups"):
                st.markdown("---")
                st.markdown("**💡 Suggested Follow-ups:**")
                f_cols = st.columns(len(msg["follow_ups"]))
                for idx, fu in enumerate(msg["follow_ups"]):
                    if f_cols[idx].button(f"👉 {fu}", key=f"fu_{msg['id']}_{idx}", use_container_width=True):
                        st.session_state.active_query = fu
                        st.rerun()

            # Render Developer Mode Reactive Drawer
            if msg.get("dev_data"):
                d = msg["dev_data"]
                exp_label = "🛠️ **Developer Mode: Reactive Agent Workflow & Tool Inspection**" if dev_mode else "🔍 **View Agentic Workflow Trace**"
                with st.expander(exp_label, expanded=dev_mode):
                    tab_nlu, tab_subagents, tab_tools, tab_validation, tab_telemetry = st.tabs([
                        "1. 🧠 NLU Intent", "2. 🤖 Agent Routing", "3. 🛠️ SQL & Tools", "4. 🛡️ Guardrails & Safety", "5. ⚡ Turn Telemetry"
                    ])

                    with tab_nlu:
                        st.markdown(f"**Classified Intent:** `{d.get('intent')}`")
                        st.markdown(f"**Company-Wide Scope:** `{d.get('raw_nlu', {}).get('is_company_wide', False)}`")
                        st.markdown("**Extracted Business Dimensions:**")
                        st.json(d.get("raw_nlu", {}).get("entities", {}))
                        if d.get("raw_nlu", {}).get("needs_clarification"):
                            st.warning(f"Clarification Flag: True ({d.get('raw_nlu', {}).get('clarification_question')})")

                    with tab_subagents:
                        st.markdown("**Sub-Agent Routing Decision:**")
                        st.markdown(f"- **Requested by NLU**: `{d.get('needed_subagents')}`")
                        st.markdown(f"- **Executed by Orchestrator**: `{d.get('sub_agents_used')}`")
                        if "web" in d.get("sub_agents_used", []):
                            st.info("External Web Search triggered: query targets competitor intelligence outside AB InBev's internal reporting.")

                    with tab_tools:
                        steps = d.get("steps", {})
                        if steps.get("sql_used"):
                            st.markdown("**Structured Data Sub-Agent (SQL Generated & Executed):**")
                            st.code(steps["sql_used"], language="sql")
                            st.caption("Guardrails applied: Read-only SQLite (`file:...mode=ro`), Single-SELECT Whitelist, Table Whitelist, Row Cap (500).")

                        if steps.get("documents"):
                            st.markdown(f"**Unstructured Data Sub-Agent ({len(steps['documents'])} Docs Retrieved via BM25):**")
                            for doc in steps["documents"]:
                                st.markdown(f"- **[{doc['doc_id']}] {doc['title']}** (`{doc['date']}`, `{doc['source_type']}`)")
                                st.caption(f"> {doc['excerpt']}")

                        if steps.get("web_results"):
                            st.markdown(f"**Web Search Sub-Agent ({len(steps['web_results'])} Results):**")
                            for wr in steps["web_results"]:
                                st.markdown(f"- [{wr['title']}]({wr['url']}): {wr['snippet']}")

                        if steps.get("code_used"):
                            st.markdown("**Coding Sub-Agent (Sandboxed Python Execution):**")
                            st.code(steps["code_used"], language="python")

                    with tab_validation:
                        st.markdown("**Hallucination & Numerical Consistency Verification:**")
                        if d.get("retried"):
                            st.warning("⚠️ Synthesis Retry Triggered: initial draft failed numerical overlap threshold against retrieved evidence; re-synthesized strictly grounded.")
                        else:
                            st.success("✅ Passed: All cited numbers and metrics verified against retrieved evidence.")
                        if d.get("assumptions"):
                            st.markdown("**Assumptions & Boundary Disclosures Surfaced:**")
                            for a in d.get("assumptions", []):
                                st.markdown(f"- `{a}`")

                    with tab_telemetry:
                        t = d.get("turn_telemetry", {})
                        col_m1, col_m2, col_m3 = st.columns(3)
                        col_m1.metric("Turn Latency", f"{t.get('latency_ms', 0):.0f} ms")
                        col_m2.metric("Turn LLM Calls", t.get("calls", 0))
                        col_m3.metric("Turn Cost", f"${t.get('cost_usd', 0.0):.5f}")


# ---------------------------------------------------------------------- Handle User Input & Interrupted Turn Recovery
user_input = st.chat_input("Ask about AB InBev's revenue, volume, BEES adoption, Olympic partnerships, or competitor benchmarks...")

# Identify query to run, including recovery from interrupted runs
pending_query = None
if st.session_state.active_query:
    pending_query = st.session_state.active_query
    st.session_state.active_query = None
elif user_input:
    pending_query = user_input
elif st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    # The last turn was interrupted by a widget toggle (e.g. dev_mode toggle): resume it immediately!
    pending_query = st.session_state.messages.pop()["content"]

if pending_query:
    # Append and render user message
    st.session_state.messages.append({"role": "user", "content": pending_query})
    with st.chat_message("user"):
        st.markdown(f"**{pending_query}**")

    # Run through Orchestrator with reactive UI status
    with st.chat_message("assistant"):
        status_box = st.status("🤖 **Orchestrator: Coordinating sub-agents...**", expanded=True)
        t_start = time.time()
        start_calls = len(GLOBAL_USAGE.events)

        def on_turn_step(step_key, step_msg):
            status_box.write(f"• {step_msg}")

        try:
            # Run Orchestrator with live step reporting
            resp = orch.handle_turn(pending_query, on_step=on_turn_step)
            status_box.update(label="✅ **Response generated & verified!**", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label=f"❌ **Execution error**: {e}", state="error", expanded=True)
            raise e

        turn_duration_ms = (time.time() - t_start) * 1000
        new_events = GLOBAL_USAGE.events[start_calls:]
        turn_cost = sum(e.estimated_cost_usd for e in new_events)
        turn_calls = len(new_events)

        # Render Main Answer
        st.markdown(resp.answer)

        # Render Follow-Up Chips
        if resp.follow_up_suggestions:
            st.markdown("---")
            st.markdown("**💡 Suggested Follow-ups:**")
            f_cols = st.columns(len(resp.follow_up_suggestions))
            for idx, fu in enumerate(resp.follow_up_suggestions):
                if f_cols[idx].button(f"👉 {fu}", key=f"fu_new_{idx}", use_container_width=True):
                    st.session_state.active_query = fu
                    st.rerun()

        # Prepare developer metadata for this message
        msg_id = f"msg_{len(st.session_state.messages)}"
        dev_payload = {
            "intent": resp.intent,
            "sub_agents_used": resp.sub_agents_used,
            "needed_subagents": resp.raw_nlu.get("needed_subagents", []),
            "raw_nlu": resp.raw_nlu,
            "steps": resp.intermediate_steps,
            "retried": resp.retried,
            "assumptions": resp.assumptions,
            "turn_telemetry": {
                "latency_ms": turn_duration_ms,
                "calls": turn_calls,
                "cost_usd": turn_cost,
            }
        }

        # Store in session state
        st.session_state.messages.append({
            "role": "assistant",
            "content": resp.answer,
            "follow_ups": resp.follow_up_suggestions,
            "dev_data": dev_payload,
            "id": msg_id,
        })
        st.rerun()
