"""
Script to generate all modular notebooks in notebooks/high_level/ and notebooks/capabilities/
with authentic pre-computed outputs from the live pipeline.
"""
import io
import json
import contextlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_HIGH_LEVEL = ROOT / "notebooks" / "high_level"
NB_CAPABILITIES = ROOT / "notebooks" / "capabilities"

NB_HIGH_LEVEL.mkdir(parents=True, exist_ok=True)
NB_CAPABILITIES.mkdir(parents=True, exist_ok=True)


def make_notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md_cell(text: str) -> dict:
    lines = [ln + "\n" for ln in text.strip().split("\n")]
    if lines:
        lines[-1] = lines[-1].rstrip("\n")
    return {"cell_type": "markdown", "metadata": {}, "source": lines}


def exec_code_cell(code: str, exec_env: dict, count: int) -> dict:
    lines = [ln + "\n" for ln in code.strip().split("\n")]
    if lines:
        lines[-1] = lines[-1].rstrip("\n")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            exec(code, exec_env)
        except Exception as e:
            print(f"Execution error: {type(e).__name__}: {e}")

    out_text = buf.getvalue()
    outputs = []
    if out_text:
        out_lines = [ln + "\n" for ln in out_text.splitlines()]
        if out_lines:
            out_lines[-1] = out_lines[-1].rstrip("\n")
        outputs.append({
            "name": "stdout",
            "output_type": "stream",
            "text": out_lines,
        })

    return {
        "cell_type": "code",
        "execution_count": count,
        "metadata": {},
        "outputs": outputs,
        "source": lines,
    }


SETUP_CODE = """import sys, pathlib
ROOT = pathlib.Path.cwd().parents[1] if "high_level" in str(pathlib.Path.cwd()) or "capabilities" in str(pathlib.Path.cwd()) else pathlib.Path.cwd()
sys.path.insert(0, str(ROOT))

from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.tools.sql_tool import run_query, validate_sql
from src.tools.retrieval_tool import get_index
from src.tools.code_tool import run_code
from src.formatting import format_value, rows_to_markdown_table

print("AB InBev Enterprise Q&A Agent Pipeline Loaded.")"""


class NotebookBuilder:
    def __init__(self, title: str, subtitle: str):
        self.cells = [md_cell(f"# {title}\n\n{subtitle}")]
        self.env = {}
        self.count = 1
        self.add_code(SETUP_CODE)

    def add_md(self, text: str):
        self.cells.append(md_cell(text))

    def add_code(self, code: str):
        self.cells.append(exec_code_cell(code, self.env, self.count))
        self.count += 1

    def save(self, path: Path):
        path.write_text(json.dumps(make_notebook(self.cells), indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# HIGH-LEVEL NOTEBOOKS GENERATION
# ---------------------------------------------------------------------------

def generate_high_level_notebooks():
    # 01. Conversational Core
    nb = NotebookBuilder("01. Conversational Core",
                         "Covers **Attributes 1, 2, 3, 4, 8, 17**:\n- Single & multi-turn dialogs\n- Greetings, capability intro, and out-of-scope handling\n- Intent validation before data retrieval\n- Clarification for ambiguous requests\n- Context preservation across turns\n- Long-running session memory optimization")
    nb.add_md("### 1. Greetings, Capability Introduction & Out-of-Scope Requests")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
for q in ["Hello!", "What can you do?", "What is the weather in London today?"]:
    r = orch.handle_turn(q)
    print(f"User: {q}\\nIntent: {r.intent}\\nAnswer: {r.answer[:120]}...\\n")""")
    nb.add_md("### 2. Intent Validation & Ambiguity Clarification")
    nb.add_code("""for q in ["Can you tell me about the performance?", "What was Budweiser revenue in US in 2025?"]:
    r = orch.handle_turn(q)
    print(f"User: {q}\\nIntent: {r.intent}\\nNeeds Clarification: {r.intent == 'clarification_needed'}\\nSub-Agents Used: {r.sub_agents_used}\\nAnswer: {r.answer[:140]}...\\n")""")
    nb.add_md("### 3. Multi-Turn Context Preservation & Filter Persistence")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
turns = [
    "What was Budweiser revenue in the United States in 2025?",
    "What about in 2024?",
    "And what was the volume in that year?"
]
for t in turns:
    r = orch.handle_turn(t)
    print(f">> {t}")
    print(f"Active Filters: {orch.memory.active_filters}")
    print(f"SQL Used: {r.sql_used}\\n")""")
    nb.add_md("### 4. Memory Optimization (Rolling Summarization for Long Sessions)")
    nb.add_code("""print(f"Initial raw turns: {len(orch.memory.raw_turns)}")
for i in range(12):
    orch.handle_turn(f"Follow-up step {i} regarding performance")
print(f"Final raw turns bounded: {len(orch.memory.raw_turns)}")
print(f"Rolling summary generated:\\n{orch.memory.rolling_summary}")""")
    nb.save(NB_HIGH_LEVEL / "01_conversational_core.ipynb")

    # 02. Semantic Understanding & Multilingual
    nb = NotebookBuilder("02. Semantic Understanding & Multilingual",
                         "Covers **Attributes 6 & 7**:\n- Entity aliases (Bud, BL, Stella, Ultra, Brahma)\n- Geographic abbreviations (US, UK, America, Britain)\n- Typo tolerance (coron, hoegarden)\n- Multilingual queries (Spanish, French, Hindi)\n- Mixed-language queries (Spanglish, Hinglish)")
    nb.add_md("### 1. Brand Aliases, Abbreviations & Typo Correction")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
queries = [
    "What was Bud revenue in US in 2025?",
    "Show BL volume in US in 2025",
    "Show Ultra market share in America in 2025",
    "What was Coron sales in Mexico in 2025?",
    "Hoegarden volume in China in 2025"
]
for q in queries:
    r = orch.handle_turn(q)
    print(f"Query: {q}\\nResolved SQL: {r.sql_used}\\n")""")
    nb.add_md("### 2. Multilingual & Mixed-Language Support")
    nb.add_code("""multilingual_queries = [
    "¿Cuáles fueron los ingresos de Corona en México en 2025?",
    "Quelle était la part de marché de Stella Artois en Belgique en 2024?",
    "2025 mein Budweiser ka revenue United States mein kitna tha?",
    "Show me los ingresos de Bud Light in US para 2025"
]
for q in multilingual_queries:
    r = orch.handle_turn(q)
    lang = r.raw_nlu.get("language", "en")
    print(f"Query: {q}\\nDetected Language: {lang}\\nAnswer: {r.answer[:140]}...\\n")""")
    nb.save(NB_HIGH_LEVEL / "02_semantic_multilingual.ipynb")

    # 03. SQL Safety & Security Controls
    nb = NotebookBuilder("03. SQL Safety & Security Controls",
                         "Covers **Attribute 9**:\n- Read-only SQLite connection\n- Single-statement SELECT-only validation\n- Table whitelisting\n- Blocked SQL keywords (DROP, DELETE, UPDATE, INSERT, ALTER, ATTACH, PRAGMA)\n- Row cap enforcement (LIMIT 500)")
    nb.add_md("### 1. Valid Read-Only SELECT Execution")
    nb.add_code("""res = run_query("SELECT brand, SUM(net_revenue_usd) AS total_rev FROM fact_monthly_kpi GROUP BY brand LIMIT 5")
print(f"Rows returned: {res.row_count}")
print(f"Columns: {res.columns}")
for row in res.rows:
    print(f"  {row[0]}: ${row[1]:,.0f}")""")
    nb.add_md("### 2. Adversarial Attacks Safely Blocked")
    nb.add_code("""from src.tools.sql_tool import SQLSafetyError

attacks = [
    "SELECT * FROM fact_monthly_kpi; DROP TABLE dim_brand;",
    "DELETE FROM fact_monthly_kpi WHERE 1=1",
    "UPDATE fact_monthly_kpi SET net_revenue_usd = 0",
    "SELECT * FROM sqlite_master",
    "PRAGMA table_info(dim_brand)"
]
for attack in attacks:
    try:
        validate_sql(attack)
        print(f"FAIL: Attack allowed: {attack}")
    except SQLSafetyError as e:
        print(f"BLOCKED: {attack}\\n  Reason: {e}\\n")""")
    nb.add_md("### 3. Automatic Row Cap Enforcement")
    nb.add_code("""queries = [
    "SELECT brand FROM fact_monthly_kpi",
    "SELECT brand FROM fact_monthly_kpi LIMIT 999999",
    "SELECT brand FROM fact_monthly_kpi LIMIT 10"
]
for q in queries:
    safe = validate_sql(q)
    print(f"Original: {q}\\nSanitized: {safe}\\n")""")
    nb.save(NB_HIGH_LEVEL / "03_sql_safety.ipynb")

    # 04. Data Retrieval & Hybrid Multi-Agent Orchestration
    nb = NotebookBuilder("04. Data Retrieval & Hybrid Multi-Agent Orchestration",
                         "Covers **Attributes 10, 11, 12, 23**:\n- Structured SQL fact retrieval\n- Unstructured BM25 + metadata document retrieval\n- Inline document citations ([DOC-xxx])\n- Hybrid multi-source orchestration\n- Metadata, tag, and recency document filtering")
    nb.add_md("### 1. Document Retrieval with BM25 & Metadata Filtering")
    nb.add_code("""idx = get_index()
docs = idx.search("Corona Cero Olympic Games Paris sponsorship", k=3)
print(f"Retrieved {len(docs)} documents:")
for d in docs:
    print(f"- [{d.doc_id}] {d.title} (Date: {d.date}, Score: {d.score})")
    print(f"  Tags: {d.tags} | Brands: {d.brands}")
    print(f"  Excerpt: {d.excerpt}\\n")""")
    nb.add_md("### 2. Pure Metadata Filtering (No Search Keywords)")
    nb.add_code("""docs_sustainability = idx.search("", k=4, tags=["sustainability"])
print(f"Sustainability updates retrieved: {len(docs_sustainability)}")
for d in docs_sustainability:
    print(f"- [{d.doc_id}] {d.title} ({d.date})")""")
    nb.add_md("### 3. Hybrid Orchestration (Structured SQL + Unstructured Documents)")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
q = "Why did Corona Cero grow in the United Kingdom, any press releases?"
r = orch.handle_turn(q)
print(f"User: {q}")
print(f"Sub-Agents Used: {r.sub_agents_used}")
print(f"Citations: {r.citations}")
print(f"\\nAnswer:\\n{r.answer}")""")
    nb.save(NB_HIGH_LEVEL / "04_retrieval_hybrid.ipynb")

    # 05. Analytics, Temporal Reasoning & Derived Calculations
    nb = NotebookBuilder("05. Analytics, Temporal Reasoning & Derived Calculations",
                         "Covers **Attributes 14, 15, 19, 20 & Coding Sub-Agent**:\n- Standardized formatting (markdown tables, USD/hL/%)\n- Temporal reasoning (historical, current YTD 2026, YoY)\n- Enterprise-wide superlative comparative analysis (poor/best years)\n- Multi-entity, multi-KPI, and channel comparisons\n- Sandboxed derived calculations via Coding Sub-Agent (CAGR, projections)")
    nb.add_md("### 1. Comparative Superlative Query & Multi-Year Performance")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
q = "in year did the AB inBev performed poor comparatively"
r = orch.handle_turn(q)
print(f"Query: {q}\\nIntent: {r.intent}\\nSQL:\\n{r.sql_used}\\n\\nAnswer:\\n{r.answer}")""")
    nb.add_md("### 2. Multi-Brand & Multi-KPI Comparison")
    nb.add_code("""q = "Compare Budweiser and Corona in the United States in 2025"
r = orch.handle_turn(q)
print(f"Query: {q}\\nSQL: {r.sql_used}\\n\\nAnswer:\\n{r.answer}")""")
    nb.add_md("### 3. Sandboxed Coding Sub-Agent Execution (CAGR & Projections)")
    nb.add_code("""queries = [
    "Calculate CAGR if revenue grew from 140.97 to 172.00 over 2 years",
    "If Corona grew by 8% per year for 3 years calculate the projection from 172"
]
for q in queries:
    r = orch.handle_turn(q)
    print(f">> {q}")
    print(f"Sub-Agents: {r.sub_agents_used}")
    print(f"Code Executed:\\n{r.intermediate_steps.get('code_used')}\\n")""")
    nb.save(NB_HIGH_LEVEL / "05_analytics_temporal.ipynb")

    # 06. Governance, Guardrails & Hierarchy Fallback
    nb = NotebookBuilder("06. Governance, Guardrails & Hierarchy Fallback",
                         "Covers **Attributes 13, 16, 18, 21, 22, 24, 25**:\n- Hierarchy-aware fallback (city -> country roll-up)\n- Unsupported entity and competitor boundary detection\n- Metadata discovery & schema queries\n- Context-aware follow-up suggestions\n- Transparent reporting of assumptions & system limitations\n- Numeric overlap verification and retry mechanisms")
    nb.add_md("### 1. Hierarchy-Aware Fallback (City to Country)")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
cities = ["St. Louis", "Monterrey", "Leuven", "Brussels", "Shanghai", "Mumbai", "Sao Paulo"]
for city in cities:
    r = orch.handle_turn(f"How did brands perform in {city} in 2025?")
    print(f"City: {city} -> Country SQL: {r.sql_used}")
    print(f"Assumption Note: {r.assumptions[0] if r.assumptions else 'None'}\\n")""")
    nb.add_md("### 2. Unsupported Entity & Competitor Disclosures")
    nb.add_code("""competitors = ["Heineken", "Carlsberg", "Molson Coors"]
for comp in competitors:
    r = orch.handle_turn(f"How is {comp} doing in Europe?")
    print(f"Query for {comp}:\\nAssumptions surfaced: {r.assumptions}\\n")""")
    nb.add_md("### 3. Metadata Discovery & Context-Aware Suggestions")
    nb.add_code("""r_meta = orch.handle_turn("What data is available in the catalog?")
print("Metadata Catalog Answer:\\n" + r_meta.answer[:300] + "...\\n")

r_sug = orch.handle_turn("What was Budweiser revenue in US in 2025?")
print("Follow-up Suggestions generated:")
for s in r_sug.follow_up_suggestions:
    print(f"- {s}")""")
    nb.save(NB_HIGH_LEVEL / "06_governance_guardrails.ipynb")


# ---------------------------------------------------------------------------
# CAPABILITIES NOTEBOOKS GENERATION (Granular 25 Attributes)
# ---------------------------------------------------------------------------

def generate_capabilities_notebooks():
    # 01. Capabilities 1-5: Conversational
    nb = NotebookBuilder("Capabilities 01 to 05: Conversational Core",
                         "- **Cap 01**: Single-turn & multi-turn conversational interactions\n- **Cap 02**: Greeting, capability introduction, and out-of-scope request handling\n- **Cap 03**: Intent validation before data retrieval\n- **Cap 04**: Clarification for ambiguous or incomplete user requests\n- **Cap 05**: Contextual follow-up questions maintaining conversation history")
    nb.add_md("### Demonstrating Capabilities 1 to 5")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
test_queries = [
    ("Cap 02: Greeting", "Hello assistant"),
    ("Cap 02: Capability Intro", "What can you do?"),
    ("Cap 02: Out-of-Scope", "Who won the World Cup?"),
    ("Cap 04: Ambiguity Clarification", "Can you tell me about the performance?"),
    ("Cap 01: Single-Turn Data Query", "What was Corona in Mexico in 2025?"),
    ("Cap 05: Contextual Follow-Up", "What about in 2024?"),
]
for cap_tag, q in test_queries:
    r = orch.handle_turn(q)
    print(f"[{cap_tag}]\\nUser: {q}\\nIntent: {r.intent}\\nAnswer: {r.answer[:120]}...\\n")""")
    nb.save(NB_CAPABILITIES / "01_conversational_capabilities.ipynb")

    # 02. Capabilities 6-8: Semantics & Multilingual
    nb = NotebookBuilder("Capabilities 06 to 08: Semantics, Multilingual & Context",
                         "- **Cap 06**: Semantic understanding: aliases, abbreviations, typo correction\n- **Cap 07**: Multilingual and mixed-language queries\n- **Cap 08**: Conversation context preservation across interactions")
    nb.add_md("### Demonstrating Capabilities 6 to 8")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
queries = [
    ("Cap 06: Brand Alias (Bud -> Budweiser)", "What was Bud revenue in US in 2025?"),
    ("Cap 06: Typo Correction (Coron -> Corona)", "Show Coron volume in Mexico in 2025"),
    ("Cap 07: Spanish Query", "¿Cuáles fueron los ingresos de Corona en México en 2025?"),
    ("Cap 07: French Query", "Quelle était la part de marché de Stella Artois en Belgique en 2024?"),
    ("Cap 07: Mixed-Language (Spanglish)", "Show me los ingresos de Bud Light in US para 2025"),
    ("Cap 08: Context Preservation Follow-up", "What was the volume for that same brand and market?"),
]
for cap_tag, q in queries:
    r = orch.handle_turn(q)
    print(f"[{cap_tag}]\\nQuery: {q}\\nSQL: {r.sql_used}\\nAnswer: {r.answer[:120]}...\\n")""")
    nb.save(NB_CAPABILITIES / "02_semantic_multilingual_capabilities.ipynb")

    # 03. Capabilities 9-12: Security & Retrieval
    nb = NotebookBuilder("Capabilities 09 to 12: Security & Multi-Source Retrieval",
                         "- **Cap 09**: Secure access with SQL safety controls\n- **Cap 10**: Structured and unstructured data retrieval from multiple sources\n- **Cap 11**: Document retrieval with source citations\n- **Cap 12**: Hybrid data retrieval")
    nb.add_md("### Demonstrating Capabilities 9 to 12")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
print("Cap 09: SQL Injection Blocked:")
from src.tools.sql_tool import validate_sql, SQLSafetyError
try:
    validate_sql("SELECT * FROM fact_monthly_kpi; DROP TABLE dim_brand;")
except SQLSafetyError as e:
    print(f"  Safely blocked: {e}\\n")

print("Cap 10 & 11: Unstructured Document Retrieval with Citations:")
r_docs = orch.handle_turn("What are the latest press releases on sustainability and water stewardship?")
print(f"  Sub-agents: {r_docs.sub_agents_used}")
print(f"  Citations: {r_docs.citations}\\n")

print("Cap 12: Hybrid Retrieval (SQL + Docs + Citations):")
r_hyb = orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
print(f"  Sub-agents: {r_hyb.sub_agents_used}")
print(f"  SQL: {r_hyb.sql_used}")
print(f"  Citations: {r_hyb.citations}")""")
    nb.save(NB_CAPABILITIES / "03_security_retrieval_capabilities.ipynb")

    # 04. Capabilities 13-17: Validation & Temporal
    nb = NotebookBuilder("Capabilities 13 to 17: Validation, Formatting & Temporal Reasoning",
                         "- **Cap 13**: Answer validation, retry mechanisms, response quality evaluation\n- **Cap 14**: Standardized formatting (markdown tables, unit-aware presentation)\n- **Cap 15**: Temporal reasoning (current, historical, comparative periods)\n- **Cap 16**: Context-aware follow-up suggestions within supported domains\n- **Cap 17**: Conversation memory optimization for long-running sessions")
    nb.add_md("### Demonstrating Capabilities 13 to 17")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
print("Cap 13: Numeric Validation Overlap Check:")
print("  Overlap pass:", not orch._needs_retry("Net revenue was $140,971,636 in 2023.", {"140971636", "2023"}))
print("  Overlap fail (hallucination detected):", orch._needs_retry("Net revenue was $999,999,999.", {"140971636", "2023"}))

print("\\nCap 14 & 15: Standardized Formatting & Temporal Reasoning:")
r = orch.handle_turn("What was Bud Light in United States in 2025?")
print(r.answer)

print("\\nCap 16: Context-Aware Follow-Up Suggestions:")
for s in r.follow_up_suggestions:
    print(f"- {s}")""")
    nb.save(NB_CAPABILITIES / "04_validation_temporal_capabilities.ipynb")

    # 05. Capabilities 18-22: Metadata & Analytics
    nb = NotebookBuilder("Capabilities 18 to 22: Metadata, Hierarchies & Comparisons",
                         "- **Cap 18**: Metadata queries\n- **Cap 19**: Multiple KPIs, entities, dimensions, and hierarchical business structures\n- **Cap 20**: Analytical comparisons across KPIs, entities, periods, and business domains\n- **Cap 21**: Hierarchy-aware fallback for unsupported entities or granularities\n- **Cap 22**: Metadata discovery for available KPIs, dimensions, periods, and datasets")
    nb.add_md("### Demonstrating Capabilities 18 to 22")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
print("Cap 18 & 22: Metadata Discovery:")
r_meta = orch.handle_turn("What KPIs, brands, and channels are available?")
print(r_meta.answer[:250] + "...\\n")

print("Cap 20: Comparative Superlative Analysis:")
r_comp = orch.handle_turn("in year did the AB inBev performed poor comparatively")
print(f"SQL: {r_comp.sql_used}\\nAnswer snippet: {r_comp.answer[:200]}...\\n")

print("Cap 21: Hierarchy-Aware Fallback (City to Country):")
r_city = orch.handle_turn("How is Budweiser in St. Louis in 2025?")
print(f"City query resolved to: {r_city.sql_used}")
print(f"Assumption: {r_city.assumptions[0]}")""")
    nb.save(NB_CAPABILITIES / "05_metadata_analytics_capabilities.ipynb")

    # 06. Capabilities 23-25: Filtering & Governance
    nb = NotebookBuilder("Capabilities 23 to 25: Filtering, Governance & Graceful Degradation",
                         "- **Cap 23**: Document filtering using metadata, tags, and recency\n- **Cap 24**: Transparent reporting of assumptions, data availability, and system limitations\n- **Cap 25**: Graceful handling of unsupported or unavailable requests")
    nb.add_md("### Demonstrating Capabilities 23 to 25")
    nb.add_code("""orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
idx = get_index()
print("Cap 23: Pure Metadata Document Filtering (Brand + Recency):")
docs = idx.search("", k=3, brands=["Corona Cero"], recency_weight=1.2)
for d in docs:
    print(f"- [{d.doc_id}] {d.title} (Date: {d.date}, Tags: {d.tags})")

print("\\nCap 24 & 25: Unsupported Entity & Competitor Boundary Disclosures:")
r_comp = orch.handle_turn("How is Heineken performing in Europe?")
print("Assumptions Surfaced:")
for a in r_comp.assumptions:
    print(f"- {a}")

print("\\nCap 25: Graceful Handling of Unsupported Request:")
r_out = orch.handle_turn("Can you help me design an airplane engine?")
print(f"Response: {r_out.answer[:120]}...")""")
    nb.save(NB_CAPABILITIES / "06_filtering_governance_capabilities.ipynb")


if __name__ == "__main__":
    print("Generating high-level notebooks...")
    generate_high_level_notebooks()
    print("Generating capabilities notebooks...")
    generate_capabilities_notebooks()
    print("All 12 modular notebooks generated successfully with pre-computed outputs!")
