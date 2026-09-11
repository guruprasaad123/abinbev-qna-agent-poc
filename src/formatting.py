"""
Standardized, unit-aware presentation helpers.
"Support standardized formatting, including markdown tables and
unit-aware presentation" -- centralized here so every sub-agent/orchestrator
path formats numbers identically rather than each writing ad hoc string code.
"""
from __future__ import annotations
from src.config import KPI_CATALOG


def format_value(column: str, value) -> str:
    if value is None:
        return "—"
    meta = KPI_CATALOG.get(column)
    if meta is None:
        return str(value)
    fmt = meta["format"]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if fmt == "currency":
        return f"${v:,.0f}" if abs(v) >= 100 else f"${v:,.2f}"
    if fmt == "percent":
        return f"{v:.1f}%"
    if fmt == "volume":
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def rows_to_markdown_table(columns: list[str], rows: list[tuple], volume_unit_by_row: list[str] | None = None) -> str:
    """Render SQL result rows as a GitHub-flavored markdown table, applying
    unit-aware formatting per KPI column (and appending the volume unit,
    e.g. 'hL' vs 'K units', when a `volume` column is present)."""
    if not rows:
        return "_No matching rows found._"

    header = "| " + " | ".join(_pretty_col(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for i, row in enumerate(rows):
        cells = []
        for col, val in zip(columns, row):
            cell = format_value(col, val)
            if col == "volume" and volume_unit_by_row:
                cell = f"{cell} {volume_unit_by_row[i]}"
            cells.append(cell)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _pretty_col(col: str) -> str:
    meta = KPI_CATALOG.get(col)
    if meta:
        return f"{meta['label']} ({meta['unit']})" if meta["unit"] != "varies by category" else meta["label"]
    return col.replace("_", " ").title()
