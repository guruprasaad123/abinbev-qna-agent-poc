"""
Structured Data Sub-Agent: natural language -> validated SQL -> rows.

Flow: build a schema-grounded prompt (schema + KPI catalog + active
conversation filters) -> ask the LLM (worker role, cheap/fast model) for a
single SELECT -> validate+execute via src/tools/sql_tool -> on a safety/
execution error, retry ONCE with the error fed back to the LLM ("Support
answer validation, retry mechanisms") -> return a structured result the
orchestrator can cite and format.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from src.tools.sql_tool import run_query, SQLSafetyError, schema_description
from src.config import KPI_CATALOG, ALL_ZONES, ALL_COUNTRIES, ALL_BRANDS

MAX_RETRIES = 1


@dataclass
class StructuredResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    sql_used: str = ""
    truncated: bool = False
    error: str = ""
    notes: list[str] = field(default_factory=list)


SYSTEM_PROMPT = f"""You are a SQL generation assistant for a read-only database of AB InBev's
REAL, publicly disclosed financial results. Given a user question (possibly with resolved
context filters), output ONE single SQLite SELECT statement and nothing else -- no markdown
fences, no commentary.

{schema_description()}

KPI column reference:
{chr(10).join(f"  {k}: {v['label']} ({v['unit']})" for k, v in KPI_CATALOG.items())}

Known zones: {', '.join(ALL_ZONES)}, or 'Global' for company-wide
Known countries (map to a zone via dim_zone_country; there is no country-grain data): {', '.join(ALL_COUNTRIES)}
Known brands (NO structured data exists for these -- select nothing, do not guess a zone): {', '.join(ALL_BRANDS)}

Rules:
- Only reference the tables/columns above.
- If the question names a country, JOIN dim_zone_country to resolve it to its zone and query at
  zone grain -- never invent a country-level row.
- If the question names a brand, return no SQL rows for it (route to documents instead).
- If the question implies a time comparison (YoY, QoQ, "vs last year"), compute
  it with conditional aggregation (e.g. SUM(CASE WHEN year=2025 THEN ... END)).
- Always GROUP BY the non-aggregated dimensions requested.
- Output raw SQL only.
"""


def _build_user_prompt(question: str, context_block: str) -> str:
    parts = []
    if context_block:
        parts.append(context_block)
    parts.append(f"User question: {question}")
    return "\n\n".join(parts)


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def answer(llm_client, question: str, context_block: str = "") -> StructuredResult:
    user_prompt = _build_user_prompt(question, context_block)
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        prompt = user_prompt if attempt == 0 else (
            f"{user_prompt}\n\nYour previous SQL failed validation/execution with this error:\n"
            f"{last_error}\nFix it and output a corrected single SELECT statement only."
        )
        raw_sql = llm_client.generate(
            system=SYSTEM_PROMPT, user=prompt, max_tokens=400, caller="structured_agent",
        )
        sql = _strip_fences(raw_sql)
        try:
            result = run_query(sql)
            notes = []
            if result.truncated:
                notes.append(f"Result truncated to the first {len(result.rows)} rows; consider narrowing the question.")
            return StructuredResult(ok=True, columns=result.columns, rows=result.rows,
                                     sql_used=result.sql_used, truncated=result.truncated, notes=notes)
        except SQLSafetyError as e:
            last_error = str(e)
            continue

    return StructuredResult(ok=False, error=f"Could not produce a safe/valid query after retry: {last_error}", sql_used=sql)
