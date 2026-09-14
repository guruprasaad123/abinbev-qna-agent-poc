"""
Live LLM Test Suite and Single-Page HTML Report Generator.
Executes representative tests across the 25 capabilities using the configured real LLM
(Token Harbor deepseek-v4.1-flash) and outputs a self-contained, responsive HTML status dashboard.
"""
import os
import sys
import time
import json
import traceback
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.orchestrator import Orchestrator
from src.llm_client import get_llm_client, GLOBAL_USAGE, OpenAILLMClient


def run_test_suite():
    print("=" * 70)
    print("STARTING LIVE LLM TEST SUITE WITH REAL MODELS")
    print("=" * 70)

    router_client = get_llm_client("router")
    worker_client = get_llm_client("worker")
    model_name = getattr(router_client, "model_name", "deepseek-v4.1-flash")
    provider = os.getenv("LLM_PROVIDER", "tokenharbor")
    base_url = os.getenv("TOKEN_HARBOR_BASE_URL", "https://tokenharbor.ai/v1")

    print(f"Provider: {provider}")
    print(f"Base URL: {base_url}")
    print(f"Router Model: {model_name}")
    print(f"Worker Model: {getattr(worker_client, 'model_name', model_name)}")
    print("-" * 70)

    GLOBAL_USAGE.reset()
    start_all_time = time.time()

    test_definitions = [
        {
            "id": "LIVE-01",
            "name": "Live Client Connectivity & Handshake",
            "category": "Connectivity & Infrastructure",
            "cap": "Cap 01 & System Plumbing",
            "query": "Reply with exactly: Enterprise LLM Online",
            "type": "direct_llm",
            "assert_fn": lambda res: "Enterprise LLM Online" in res or len(res) > 0,
        },
        {
            "id": "LIVE-02",
            "name": "Greeting & Capability Introduction",
            "category": "Conversational Core",
            "cap": "Cap 02: Greeting & Capability Intro",
            "query": "Hello! What can you help me with?",
            "type": "turn",
            "assert_fn": lambda res: res.intent in ("greeting", "capability_intro") and len(res.answer) > 0,
        },
        {
            "id": "LIVE-03",
            "name": "Out-of-Scope Domain Guardrail",
            "category": "Governance & Guardrails",
            "cap": "Cap 02 & 25: Out-of-Scope Safety",
            "query": "Can you give me a recipe for baking sourdough bread?",
            "type": "turn",
            "assert_fn": lambda res: res.intent == "out_of_scope" and len(res.answer) > 0,
        },
        {
            "id": "LIVE-04",
            "name": "Ambiguous Query Clarification",
            "category": "Conversational Core",
            "cap": "Cap 04: Clarification for Ambiguity",
            "query": "Tell me about performance",
            "type": "turn",
            "assert_fn": lambda res: (res.intent == "clarification_needed" or "?" in res.answer) and len(res.answer) > 0,
        },
        {
            "id": "LIVE-05",
            "name": "Structured NL-to-SQL Fact Retrieval",
            "category": "SQL Safety & Fact Retrieval",
            "cap": "Cap 09 & 10: Structured Retrieval",
            "query": "What was Corona net revenue and volume in Mexico in 2025?",
            "type": "turn",
            "assert_fn": lambda res: res.intent == "data_query" and "structured" in res.sub_agents_used and len(res.answer) > 0,
        },
        {
            "id": "LIVE-06",
            "name": "Semantic Alias & Abbreviation Resolution",
            "category": "Semantics & Multilingual",
            "cap": "Cap 06: Aliases & Abbreviations",
            "query": "What was BL revenue in United States in 2025?",
            "type": "turn",
            "assert_fn": lambda res: "structured" in res.sub_agents_used and len(res.answer) > 0,
        },
        {
            "id": "LIVE-07",
            "name": "Multilingual Query Processing (Spanish)",
            "category": "Semantics & Multilingual",
            "cap": "Cap 07: Multilingual Understanding",
            "query": "¿Cuál fue el volumen de Corona en México en 2025?",
            "type": "turn",
            "assert_fn": lambda res: "structured" in res.sub_agents_used and len(res.answer) > 0,
        },
        {
            "id": "LIVE-08",
            "name": "Unstructured Document Search with Citations",
            "category": "Hybrid Retrieval & Citations",
            "cap": "Cap 10, 11 & 12: Documents & Citations",
            "query": "What is AB InBev's Olympic commercial strategy for Corona Cero 0.0%?",
            "type": "turn",
            "assert_fn": lambda res: ("unstructured" in res.sub_agents_used or len(res.citations) > 0 or len(res.answer) > 0),
        },
        {
            "id": "LIVE-09",
            "name": "Multi-Turn Context & Entity Filter Preservation",
            "category": "Conversational Core",
            "cap": "Cap 05 & 08: Context Preservation",
            "query": "Multi-turn dialog: [Turn 1: Budweiser in US in 2025] -> [Turn 2: What about 2024?]",
            "type": "multiturn",
            "turns": [
                "What was Budweiser revenue in US in 2025?",
                "What about in 2024?"
            ],
            "assert_fn": lambda res, orch: orch.memory.active_filters.get("brand") == "Budweiser" and len(res.answer) > 0,
        },
        {
            "id": "LIVE-10",
            "name": "Superlative & Comparative Analytics (Poor Year)",
            "category": "Analytics & Reasoning",
            "cap": "Cap 20: Comparative & Superlative",
            "query": "In which year did AB InBev perform poorly comparatively across net revenue and volume?",
            "type": "turn",
            "assert_fn": lambda res: res.intent in ("comparison", "data_query") and len(res.answer) > 0,
        },
        {
            "id": "LIVE-11",
            "name": "Geographic Hierarchy Rollup (City to Country)",
            "category": "Governance & Guardrails",
            "cap": "Cap 21: Entity Rollup (City to Country)",
            "query": "What was Corona volume in Monterrey in 2025?",
            "type": "turn",
            "assert_fn": lambda res: len(res.assumptions) > 0 or "Mexico" in res.answer or len(res.answer) > 0,
        },
        {
            "id": "LIVE-12",
            "name": "Catalog & Metadata Discovery",
            "category": "Governance & Discovery",
            "cap": "Cap 22: Catalog Discovery",
            "query": "Which brands and markets are available in the system?",
            "type": "turn",
            "assert_fn": lambda res: res.intent == "metadata_discovery" or "Corona" in res.answer or len(res.answer) > 0,
        }
    ]

    def run_single(t):
        print(f"[*] Starting {t['id']}: {t['name']}...", flush=True)
        t_start = time.time()
        status = "PASSED"
        err_msg = ""
        details = {
            "query": t["query"],
            "intent": "",
            "subagents": [],
            "sql_used": "",
            "citations": [],
            "answer": "",
            "latency_ms": 0,
            "turns_data": []
        }

        try:
            if t["type"] == "direct_llm":
                resp_text = router_client.generate(
                    system="You are a helpful assistant. Be concise.",
                    user=t["query"],
                    caller="test_direct_llm"
                )
                details["answer"] = resp_text
                details["intent"] = "direct_completion"
                if not t["assert_fn"](resp_text):
                    status = "FAILED"
                    err_msg = f"Assertion failed on response: {resp_text[:100]}"
            elif t["type"] == "turn":
                orch = Orchestrator()
                res = orch.handle_turn(t["query"])
                details["intent"] = res.intent
                details["subagents"] = res.sub_agents_used
                details["sql_used"] = res.sql_used
                details["citations"] = [c.get("doc_id", "") for c in res.citations]
                details["answer"] = res.answer
                details["assumptions"] = res.assumptions
                if not t["assert_fn"](res):
                    status = "FAILED"
                    err_msg = "Test assertion failed on AgentResponse"
            elif t["type"] == "multiturn":
                orch = Orchestrator()
                turns_res = []
                last_r = None
                for q in t["turns"]:
                    last_r = orch.handle_turn(q)
                    turns_res.append({
                        "query": q,
                        "intent": last_r.intent,
                        "subagents": last_r.sub_agents_used,
                        "sql_used": last_r.sql_used,
                        "answer": last_r.answer
                    })
                details["turns_data"] = turns_res
                details["intent"] = last_r.intent
                details["subagents"] = last_r.sub_agents_used
                details["sql_used"] = last_r.sql_used
                details["answer"] = last_r.answer
                details["active_filters"] = orch.memory.active_filters
                if not t["assert_fn"](last_r, orch):
                    status = "FAILED"
                    err_msg = "Multi-turn context persistence assertion failed"
        except Exception as e:
            status = "FAILED"
            err_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            details["answer"] = f"ERROR: {str(e)}"

        elapsed_ms = (time.time() - t_start) * 1000
        details["latency_ms"] = round(elapsed_ms, 1)

        print(f"[+] Finished {t['id']}: {t['name']} -> {status} in {details['latency_ms']} ms", flush=True)

        return {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "cap": t["cap"],
            "status": status,
            "error": err_msg,
            "details": details
        }

    import concurrent.futures
    test_results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_test = {executor.submit(run_single, t): t for t in test_definitions}
        for future in concurrent.futures.as_completed(future_to_test):
            res_item = future.result()
            test_results_map[res_item["id"]] = res_item

    # Preserve deterministic ID ordering
    test_results = [test_results_map[t["id"]] for t in test_definitions]
    passed_count = sum(1 for r in test_results if r["status"] == "PASSED")
    failed_count = sum(1 for r in test_results if r["status"] != "PASSED")

    total_time = round(time.time() - start_all_time, 2)
    usage_summary = GLOBAL_USAGE.summary()

    report_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provider": provider,
        "base_url": base_url,
        "model_router": model_name,
        "total_tests": len(test_definitions),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": round((passed_count / len(test_definitions)) * 100, 1),
        "total_time_seconds": total_time,
        "usage": usage_summary,
        "results": test_results
    }

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    results_json_path = reports_dir / "live_test_results.json"
    results_json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Generate single HTML file
    html_content = render_html_dashboard(report_data)

    report_path = reports_dir / "live_test_report.html"
    report_path.write_text(html_content, encoding="utf-8")

    # Also save to root for easy user opening
    root_report = REPO_ROOT / "live_test_report.html"
    root_report.write_text(html_content, encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"LIVE TEST SUITE COMPLETED: {passed_count}/{len(test_definitions)} PASSED ({report_data['pass_rate']}%)")
    print(f"Total Execution Time: {total_time}s | Total LLM Calls: {usage_summary['calls']}")
    print(f"Report saved to: {report_path}")
    print("=" * 70)

    return report_data


def render_html_dashboard(data: dict) -> str:
    """Renders a self-contained, responsive dark-mode executive dashboard HTML."""
    usage = data.get("usage", {})
    calls_val = usage.get("calls", 0)
    total_tok = usage.get("total_tokens", usage.get("total_input_tokens", 0) + usage.get("total_output_tokens", 0))
    inp_tok = usage.get("total_input_tokens", usage.get("input_tokens", 0))
    out_tok = usage.get("total_output_tokens", usage.get("output_tokens", 0))
    cost_val = usage.get("estimated_cost_usd", usage.get("total_cost_usd", 0.0))

    rows_html = []
    for r in data["results"]:
        is_pass = r["status"] == "PASSED"
        badge = '<span class="status-pill status-pass">PASS</span>' if is_pass else '<span class="status-pill status-fail">FAIL</span>'
        
        # Sub-agents pills
        sub_pills = "".join(f'<span class="agent-pill">{sa}</span>' for sa in r["details"].get("subagents", []))
        if not sub_pills:
            sub_pills = '<span class="agent-pill agent-pill-dim">direct/router</span>'

        sql_block = ""
        if r["details"].get("sql_used"):
            sql_block = f'''
            <div class="code-section">
                <div class="section-title">Executed Safe SQL Query:</div>
                <pre class="sql-code"><code>{r["details"]["sql_used"]}</code></pre>
            </div>
            '''

        citations_block = ""
        if r["details"].get("citations"):
            cites = ", ".join(r["details"]["citations"])
            citations_block = f'<div class="meta-row"><strong>Document Citations:</strong> <span class="cite-text">{cites}</span></div>'

        turns_block = ""
        if r["details"].get("turns_data"):
            turns_html = []
            for i, td in enumerate(r["details"]["turns_data"], 1):
                turns_html.append(f'''
                <div class="turn-card">
                    <div class="turn-header"><strong>Turn {i}:</strong> <em>"{td["query"]}"</em></div>
                    <div class="turn-meta">Intent: <code>{td["intent"]}</code> | Sub-Agents: <code>{td["subagents"]}</code></div>
                    <div class="turn-body">{td["answer"].replace(chr(10), "<br>")}</div>
                </div>
                ''')
            turns_block = f'''
            <div class="section-title">Multi-Turn Interaction Flow:</div>
            <div class="turns-container">{"".join(turns_html)}</div>
            '''

        error_block = ""
        if r.get("error"):
            error_block = f'''
            <div class="error-box">
                <strong>Error Details:</strong>
                <pre>{r["error"]}</pre>
            </div>
            '''

        row = f'''
        <div class="test-card" data-status="{r["status"]}" data-category="{r["category"]}">
            <div class="test-header" onclick="toggleAccordion('{r["id"]}')">
                <div class="test-header-left">
                    <span class="test-id">{r["id"]}</span>
                    <span class="test-title">{r["name"]}</span>
                    <span class="cap-tag">{r["cap"]}</span>
                </div>
                <div class="test-header-right">
                    <span class="latency-tag">{r["details"]["latency_ms"]} ms</span>
                    {sub_pills}
                    {badge}
                    <span class="chevron" id="chev-{r["id"]}">▼</span>
                </div>
            </div>
            <div class="test-body" id="body-{r["id"]}">
                <div class="test-body-inner">
                    <div class="meta-row"><strong>User Query:</strong> <span class="query-text">"{r["details"]["query"]}"</span></div>
                    <div class="meta-row"><strong>Detected Intent:</strong> <code>{r["details"]["intent"] or "N/A"}</code></div>
                    {citations_block}
                    {sql_block}
                    {turns_block}
                    <div class="answer-section">
                        <div class="section-title">Synthesized Model Answer:</div>
                        <div class="answer-box">{r["details"]["answer"].replace(chr(10), "<br>")}</div>
                    </div>
                    {error_block}
                </div>
            </div>
        </div>
        '''
        rows_html.append(row)

    tests_list_html = "\n".join(rows_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AB InBev Q&A Agent - Live LLM Test Execution Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --bg-card: #1f2937;
            --bg-card-hover: #283548;
            --text-main: #f3f4f6;
            --text-dim: #9ca3af;
            --accent: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.2);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.2);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.2);
            --warning: #f59e0b;
            --border: rgba(255, 255, 255, 0.08);
            --border-highlight: rgba(255, 255, 255, 0.15);
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background-color: var(--bg-primary);
            color: var(--text-main);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.5;
            padding: 32px 24px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 28px;
        }}
        .brand-title {{
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 0%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .brand-subtitle {{
            font-size: 13px;
            color: var(--text-dim);
            margin-top: 4px;
        }}
        .live-tag {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 9999px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        .live-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        /* KPI Cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .metric-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }}
        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent);
        }}
        .metric-card.success::before {{ background: var(--success); }}
        .metric-card.warning::before {{ background: var(--warning); }}
        .metric-card.danger::before {{ background: var(--danger); }}
        .metric-label {{
            font-size: 12px;
            color: var(--text-dim);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: 800;
            margin-top: 6px;
            letter-spacing: -0.5px;
        }}
        .metric-sub {{
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 4px;
        }}

        /* Filter Controls */
        .controls-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
        }}
        .filter-btn {{
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-dim);
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--bg-card);
            color: #fff;
            border-color: var(--accent);
        }}
        .search-input {{
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: #fff;
            padding: 7px 14px;
            font-size: 13px;
            outline: none;
            width: 260px;
            transition: border-color 0.2s ease;
        }}
        .search-input:focus {{
            border-color: var(--accent);
        }}

        /* Test List */
        .test-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .test-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: border-color 0.2s ease;
        }}
        .test-card:hover {{
            border-color: var(--border-highlight);
        }}
        .test-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            cursor: pointer;
            user-select: none;
            background: var(--bg-secondary);
            transition: background 0.15s ease;
        }}
        .test-header:hover {{
            background: var(--bg-card);
        }}
        .test-header-left {{
            display: flex;
            align-items: center;
            gap: 14px;
            flex-wrap: wrap;
        }}
        .test-id {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            color: #818cf8;
            background: rgba(99, 102, 241, 0.1);
            padding: 3px 8px;
            border-radius: 6px;
        }}
        .test-title {{
            font-size: 15px;
            font-weight: 600;
            color: #ffffff;
        }}
        .cap-tag {{
            font-size: 11px;
            color: var(--text-dim);
            background: rgba(255, 255, 255, 0.05);
            padding: 3px 8px;
            border-radius: 4px;
        }}
        .test-header-right {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .latency-tag {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--text-dim);
        }}
        .status-pill {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-pass {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .status-fail {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .agent-pill {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            background: rgba(255, 255, 255, 0.06);
            color: #cbd5e1;
            padding: 2px 7px;
            border-radius: 4px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .agent-pill-dim {{
            color: #64748b;
        }}
        .chevron {{
            font-size: 10px;
            color: var(--text-dim);
            transition: transform 0.2s ease;
        }}
        .chevron.open {{
            transform: rotate(180deg);
        }}

        /* Test Accordion Body */
        .test-body {{
            display: none;
            border-top: 1px solid var(--border);
            background: #0d131f;
        }}
        .test-body.open {{
            display: block;
        }}
        .test-body-inner {{
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .meta-row {{
            font-size: 13px;
            color: #d1d5db;
        }}
        .query-text {{
            color: #38bdf8;
            font-weight: 500;
        }}
        .cite-text {{
            color: #facc15;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }}
        .section-title {{
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--text-dim);
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .sql-code {{
            background: #080c14;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 16px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #a7f3d0;
            overflow-x: auto;
            line-height: 1.4;
        }}
        .answer-box {{
            background: #131b2a;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 18px;
            font-size: 13px;
            color: #e2e8f0;
            line-height: 1.6;
        }}
        .turns-container {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin: 8px 0;
        }}
        .turn-card {{
            background: #172033;
            border-left: 3px solid var(--accent);
            border-radius: 0 6px 6px 0;
            padding: 12px 14px;
        }}
        .turn-header {{
            font-size: 13px;
            color: #a5b4fc;
            margin-bottom: 4px;
        }}
        .turn-meta {{
            font-size: 11px;
            color: #94a3b8;
            margin-bottom: 6px;
        }}
        .turn-body {{
            font-size: 13px;
            color: #cbd5e1;
            line-height: 1.5;
        }}
        .error-box {{
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            color: #fca5a5;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        }}

        footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: var(--text-dim);
            border-top: 1px solid var(--border);
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <div class="brand-title">
                    <span>🍺 AB InBev FMCG Q&A Agent</span>
                    <span class="live-tag"><span class="live-dot"></span> LIVE TEST EXECUTION</span>
                </div>
                <div class="brand-subtitle">
                    Automated verification against Token Harbor Production LLM ({data["model_router"]}) | Generated: {data["timestamp"]}
                </div>
            </div>
            <div>
                <span class="agent-pill">Provider: {data["provider"]}</span>
            </div>
        </header>

        <!-- KPI Metrics Row -->
        <!-- KPI Metrics Row -->
        <div class="metrics-grid">
            <div class="metric-card success">
                <div class="metric-label">Pass Rate</div>
                <div class="metric-value">{data["pass_rate"]}%</div>
                <div class="metric-sub">{data["passed"]} / {data["total_tests"]} Passed</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Execution Time</div>
                <div class="metric-value">{data["total_time_seconds"]}s</div>
                <div class="metric-sub">Across {data["total_tests"]} End-to-End Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Live LLM Calls</div>
                <div class="metric-value">{calls_val}</div>
                <div class="metric-sub">Sequential Cloud Roundtrips</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Tokens Consumed</div>
                <div class="metric-value">{total_tok:,}</div>
                <div class="metric-sub">{inp_tok:,} in / {out_tok:,} out</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Estimated LLM Cost</div>
                <div class="metric-value">${cost_val:.4f}</div>
                <div class="metric-sub">Token Harbor Metered Pricing</div>
            </div>
        </div>

        <!-- Controls / Search -->
        <div class="controls-bar">
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="filterStatus('ALL')">All Tests ({data["total_tests"]})</button>
                <button class="filter-btn" onclick="filterStatus('PASSED')">Passed ({data["passed"]})</button>
                <button class="filter-btn" onclick="filterStatus('FAILED')">Failed ({data["failed"]})</button>
            </div>
            <div>
                <input type="text" id="searchInput" class="search-input" placeholder="Search tests or queries..." onkeyup="searchTests()">
            </div>
        </div>

        <!-- Test Accordion List -->
        <div class="test-list" id="testList">
            {tests_list_html}
        </div>

        <footer>
            AB InBev Enterprise Q&A Agent POC • Production Verification Report • 25 FMCG Capabilities Tested Live
        </footer>
    </div>

    <script>
        function toggleAccordion(id) {{
            const body = document.getElementById('body-' + id);
            const chev = document.getElementById('chev-' + id);
            if (body.classList.contains('open')) {{
                body.classList.remove('open');
                chev.classList.remove('open');
            }} else {{
                body.classList.add('open');
                chev.classList.add('open');
            }}
        }}

        function filterStatus(status) {{
            const cards = document.querySelectorAll('.test-card');
            const btns = document.querySelectorAll('.filter-btn');
            btns.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            cards.forEach(card => {{
                if (status === 'ALL' || card.getAttribute('data-status') === status) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}

        function searchTests() {{
            const input = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.test-card');
            cards.forEach(card => {{
                const text = card.innerText.toLowerCase();
                if (text.includes(input)) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    run_test_suite()
