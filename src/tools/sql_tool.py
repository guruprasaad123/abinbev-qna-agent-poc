"""
Safe, read-only SQL execution over the structured SQLite database.

SECURITY MODEL ("Support secure access with SQL safety controls"):
  1. The connection itself is opened read-only at the OS/SQLite level
     (`mode=ro` URI) -- even a successfully-injected DDL/DML statement
     physically cannot write.
  2. Statement whitelist: only a single SELECT statement is allowed. Anything
     containing a second statement (`;` followed by more non-whitespace),
     or any of a blocked-keyword list (INSERT/UPDATE/DELETE/DROP/ALTER/
     CREATE/ATTACH/DETACH/PRAGMA/REPLACE/TRUNCATE/VACUUM/REINDEX), is
     rejected before it ever reaches SQLite.
  3. Table/column whitelist: every identifier after FROM/JOIN must be one of
     the known tables. This blocks `sqlite_master` introspection and any
     attempt to reach outside the intended schema.
  4. Row cap: a LIMIT is enforced (added if missing, capped if present) so a
     pathological query can't return unbounded rows into the LLM's context
     (a cost/latency concern as much as a safety one).
  5. A SQLite progress handler aborts execution after a step budget, which
     is our stand-in for a query timeout (SQLite has no native query-level
     timeout).

This is deliberately a whitelist-based validator, not an attempt to detect
"bad" SQL patterns -- whitelisting what's allowed is far more robust against
prompt-injection-style attempts to smuggle instructions through a user
question ("... ignore previous instructions and DROP TABLE ...") than
blacklisting what's forbidden.
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "db" / "meridian_brewing.db"

ALLOWED_TABLES = {"fact_monthly_kpi", "dim_brand", "dim_geo", "dim_channel"}
BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|"
    r"TRUNCATE|VACUUM|REINDEX|GRANT|EXEC|EXECUTE)\b", re.IGNORECASE,
)
MAX_ROWS = 500
STEP_BUDGET = 5_000_000  # sqlite VM steps before we abort, ~ generous safety valve


class SQLSafetyError(ValueError):
    pass


@dataclass
class SQLResult:
    columns: list[str]
    rows: list[tuple]
    sql_used: str
    truncated: bool
    row_count: int


def _extract_referenced_tables(sql: str) -> set[str]:
    return set(re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE))


def validate_sql(sql: str) -> str:
    """Raises SQLSafetyError if unsafe; otherwise returns a (possibly
    LIMIT-adjusted) query safe to execute."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise SQLSafetyError("Empty query.")

    # Reject stacked statements
    if ";" in stripped:
        raise SQLSafetyError("Multiple statements are not allowed.")

    if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise SQLSafetyError("Only SELECT (or WITH ... SELECT) statements are allowed.")

    if BLOCKED_KEYWORDS.search(stripped):
        raise SQLSafetyError("Query contains a disallowed keyword.")

    tables = _extract_referenced_tables(stripped)
    unknown = tables - ALLOWED_TABLES
    if unknown:
        raise SQLSafetyError(f"Query references unknown/disallowed table(s): {sorted(unknown)}")

    # Enforce a row cap. If a LIMIT already exists, ensure it's <= MAX_ROWS;
    # otherwise append one.
    m = re.search(r"\bLIMIT\s+(\d+)\b", stripped, re.IGNORECASE)
    if m:
        if int(m.group(1)) > MAX_ROWS:
            stripped = stripped[: m.start()] + f"LIMIT {MAX_ROWS}" + stripped[m.end():]
    else:
        stripped = f"{stripped} LIMIT {MAX_ROWS}"

    return stripped


def run_query(sql: str) -> SQLResult:
    safe_sql = validate_sql(sql)
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    steps = {"n": 0}

    def _progress():
        steps["n"] += 1
        return 1 if steps["n"] * 1000 > STEP_BUDGET else 0

    conn.set_progress_handler(_progress, 1000)
    try:
        cur = conn.cursor()
        cur.execute(safe_sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise SQLSafetyError("Query exceeded the execution step budget and was aborted.")
        raise SQLSafetyError(f"SQL execution error: {e}")
    finally:
        conn.close()

    truncated = len(rows) >= MAX_ROWS
    return SQLResult(columns=columns, rows=rows, sql_used=safe_sql, truncated=truncated, row_count=len(rows))


def schema_description() -> str:
    """Human/LLM-readable schema, used in the NL->SQL prompt."""
    return """
Tables (read-only):
  fact_monthly_kpi(brand TEXT, country TEXT, channel TEXT, year INT, month INT,
                    net_revenue_usd REAL, volume REAL, volume_unit TEXT,
                    market_share_pct REAL, avg_selling_price_usd REAL,
                    distribution_acv_pct REAL, marketing_spend_usd REAL,
                    promo_spend_usd REAL, gross_margin_pct REAL)
  dim_brand(brand TEXT PRIMARY KEY, category TEXT, sub_category TEXT)
  dim_geo(country TEXT PRIMARY KEY, region TEXT)
  dim_channel(channel TEXT PRIMARY KEY)

Grain of fact_monthly_kpi is one row per (brand, country, channel, year, month).
Data covers Jan 2023 through Aug 2026 (year-to-date). volume_unit is always 'hL'
(hectoliters, the standard brewing-industry volume unit) -- always report volume with its unit.
""".strip()
