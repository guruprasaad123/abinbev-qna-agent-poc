"""
Central business-domain configuration for the real AB InBev dataset.

This is the SINGLE SOURCE OF TRUTH for entities (company/zone/country/brand),
KPIs, and aliases. Both the structured-data curation script and the
unstructured-document curation script import from here, which is what
guarantees the two corpora share the same entities (a requirement of the
assignment) rather than being built independently.

NOTE ON REAL DATA (see docs/DESIGN_DECISIONS.md §1 for the full rationale):
Every number reachable through the structured sub-agent in this build is a
REAL, PUBLICLY DISCLOSED figure from Anheuser-Busch InBev SA/NV's own
quarterly and full-year results press releases (BusinessWire / SEC EX-99.2
filings), not a synthetic or estimated one. That constrains the schema to
what AB InBev actually discloses:
  - Financials are broken out by REPORTING ZONE (North America, Middle
    Americas, South America, EMEA, Asia Pacific) and by QUARTER/YEAR --
    AB InBev does not publicly disclose revenue/volume by individual
    country, brand, or trade channel in a structured, queryable form.
  - Country-level and brand-level detail exists only as QUALITATIVE
    commentary in the source documents (e.g. "Brazil volumes declined 4.1%
    in 2025"), which is why those live in the unstructured corpus and route
    through document retrieval rather than SQL -- a real, not contrived,
    illustration of "graceful handling of an unsupported request" and
    "hierarchy-aware fallback" (country -> zone).
  - There is no real, public trade-channel (on-premise vs. off-premise)
    breakdown with numbers, so "channel" is not a structured dimension here
    at all; it appears only as a document tag where a source discusses it
    qualitatively.
  - Historical depth varies by grain, exactly as real disclosure works:
    quarterly zone-level detail is only available from FY2024 onward
    (that's as far back as this build sourced it); FY2022-FY2023 exist only
    as annual company-wide totals. This unevenness is left visible rather
    than smoothed over.
Every row in the structured database carries the exact source document and
URL it was transcribed from (see data/db/ab_inbev.db `source_label` /
`source_url` columns and scripts/generate_structured_data.py).
"""

from __future__ import annotations
from datetime import date

COMPANY_NAME = "Anheuser-Busch InBev (AB InBev)"

# ---------------------------------------------------------------------------
# Reporting zones -- AB InBev's actual disclosed segments -- and the real
# countries publicly named (in FY2025 SEC filing EX-99.2 and earnings
# releases) as belonging to each. This is not an exhaustive country list per
# zone (AB InBev doesn't publish one); it's every country the company itself
# names in its own disclosures.
# ---------------------------------------------------------------------------
ZONE_HIERARCHY = {
    "North America": ["United States", "Canada"],
    "Middle Americas": ["Mexico", "Colombia", "Peru", "Ecuador"],
    "South America": ["Brazil", "Argentina"],
    "EMEA": ["United Kingdom", "Netherlands", "France", "Italy", "South Africa", "Nigeria"],
    "Asia Pacific": ["China", "South Korea"],
}
ALL_ZONES = list(ZONE_HIERARCHY.keys())
ALL_COUNTRIES = [c for cs in ZONE_HIERARCHY.values() for c in cs]
COUNTRY_TO_ZONE = {c: z for z, cs in ZONE_HIERARCHY.items() for c in cs}

# ---------------------------------------------------------------------------
# Brands -- real AB InBev-owned brands, used for entity recognition and
# document tagging only. There is NO structured (SQL-queryable) brand-level
# financial data anywhere in this build -- AB InBev doesn't publicly disclose
# it -- so these exist purely so the agent can recognize a brand mention and
# correctly route it to qualitative document retrieval / web search instead
# of fabricating a SQL row for it.
# (Note on Corona/Modelo: AB InBev owns Grupo Modelo -- and the Corona/Modelo
# brand family -- everywhere except the United States, where Constellation
# Brands holds a permanent license to those brands. Kept simple here since
# this build never needs brand-level US-license nuance.)
# ---------------------------------------------------------------------------
BRANDS = {
    "Budweiser":     {"origin_market": "United States"},
    "Corona":        {"origin_market": "Mexico"},
    "Stella Artois": {"origin_market": "Belgium"},
    "Michelob Ultra": {"origin_market": "United States"},
    "Beck's":        {"origin_market": "Germany"},
    "Brahma":        {"origin_market": "Brazil"},
    "Skol":          {"origin_market": "Brazil"},
    "Castle Lager":  {"origin_market": "South Africa"},
}
ALL_BRANDS = list(BRANDS.keys())

# ---------------------------------------------------------------------------
# Real, named competitors that are deliberately OUTSIDE this build's tracked
# entities -- AB InBev doesn't report on them, so any question about them
# should be flagged as unsupported (no internal data) rather than answered
# from fabricated figures. Real companies, used only to demonstrate correct
# scope-boundary / graceful-unsupported-request handling -- never used to
# invent numbers about them.
# ---------------------------------------------------------------------------
KNOWN_COMPETITORS = ["Heineken", "Molson Coors", "Carlsberg", "Constellation Brands",
                      "Diageo", "Asahi", "Kirin", "China Resources Snow Breweries"]

# ---------------------------------------------------------------------------
# Time range for structured facts.
#   - Quarterly, zone-level detail: Q1 2024 - Q4 2025 (8 quarters, the range
#     this build actually sourced cleanly from primary press releases).
#   - Annual, company-wide totals: FY2022 - FY2025 (zone breakouts aren't
#     available pre-2024 from the sources used here).
# "Today" for this build is treated as shortly after AB InBev's FY2025
# results (published Feb 2026) -- FY2025 / Q4 2025 is the latest closed
# period reflected.
# ---------------------------------------------------------------------------
DATA_START = date(2022, 1, 1)
DATA_END = date(2025, 12, 31)

# ---------------------------------------------------------------------------
# KPI catalog -- every KPI here is one AB InBev actually discloses in its
# results releases, except ebitda_margin_pct, which is COMPUTED (EBITDA /
# revenue) from two disclosed figures rather than separately stated for
# every row -- this is called out explicitly wherever it's used.
# ---------------------------------------------------------------------------
KPI_CATALOG = {
    "revenue_usd_m": {
        "label": "Revenue", "unit": "USD million", "format": "currency",
        "description": "Consolidated revenue, as reported.",
        "category_scope": "all",
    },
    "volume_k_hl": {
        "label": "Volume", "unit": "thousand hL", "format": "volume",
        "description": "Own beer + non-beer volume in thousand hectoliters, as reported.",
        "category_scope": "all",
    },
    "normalized_ebitda_usd_m": {
        "label": "Normalized EBITDA", "unit": "USD million", "format": "currency",
        "description": "EBITDA normalized for non-recurring items, as reported.",
        "category_scope": "all",
    },
    "ebitda_margin_pct": {
        "label": "EBITDA Margin", "unit": "% (computed)", "format": "percent",
        "description": "Normalized EBITDA / Revenue -- computed from the two disclosed figures, not separately reported by AB InBev for every period.",
        "category_scope": "all",
    },
    "organic_revenue_growth_pct": {
        "label": "Organic Revenue Growth", "unit": "%", "format": "percent",
        "description": "AB InBev's own non-GAAP organic growth metric (excludes FX translation and scope/M&A effects), as reported.",
        "category_scope": "all",
    },
    "net_profit_usd_m": {
        "label": "Net Profit", "unit": "USD million", "format": "currency",
        "description": "Profit attributable to equity holders of AB InBev, as reported. Disclosed at the total-company level only (not by zone) in this build's sources.",
        "category_scope": "all",
    },
}
ALL_KPIS = list(KPI_CATALOG.keys())

# ---------------------------------------------------------------------------
# Entity aliases / abbreviations / common typos -> canonical entity.
# Deterministic first-pass normalizer that runs BEFORE the LLM sees the
# query (cheap, fast, auditable) -- the LLM is the second-pass fallback for
# anything not in this table.
# ---------------------------------------------------------------------------
ENTITY_ALIASES = {
    # Zones
    "na": "North America", "n. america": "North America",
    "ma": "Middle Americas", "middle america": "Middle Americas",
    "sa": "South America", "s. america": "South America", "latam south": "South America",
    "emea": "EMEA", "europe middle east africa": "EMEA",
    "apac": "Asia Pacific", "asia": "Asia Pacific",
    # Countries
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom",
    "mx": "Mexico", "méxico": "Mexico",
    "sk": "South Korea", "korea": "South Korea",
    "sa (country)": "South Africa",  # disambiguation hint only, not auto-applied
    # Brands
    "bud": "Budweiser", "budweiser beer": "Budweiser",
    "michelob": "Michelob Ultra", "ultra": "Michelob Ultra",
    "stella": "Stella Artois",
    "becks": "Beck's",
    # KPIs (incl. common non-English terms for multilingual support)
    "revenue": "revenue_usd_m", "sales": "revenue_usd_m", "rev": "revenue_usd_m", "top line": "revenue_usd_m",
    "ingresos": "revenue_usd_m", "chiffre d'affaires": "revenue_usd_m",
    "vol": "volume_k_hl", "volumen": "volume_k_hl", "hectoliters": "volume_k_hl", "hectolitres": "volume_k_hl", "hls": "volume_k_hl",
    "ebitda": "normalized_ebitda_usd_m", "normalised ebitda": "normalized_ebitda_usd_m",
    "margin": "ebitda_margin_pct", "ebitda margin": "ebitda_margin_pct",
    "growth": "organic_revenue_growth_pct", "organic growth": "organic_revenue_growth_pct", "organic": "organic_revenue_growth_pct",
    "profit": "net_profit_usd_m", "net income": "net_profit_usd_m", "bottom line": "net_profit_usd_m",
}

# Business-domain scope statement, shown in greeting / used for out-of-scope detection
DOMAIN_DESCRIPTION = (
    f"{COMPANY_NAME}'s real, publicly disclosed financial performance -- revenue, volume, "
    f"normalized EBITDA, EBITDA margin, organic revenue growth and net profit -- by reporting "
    f"zone (North America, Middle Americas, South America, EMEA, Asia Pacific) and by quarter "
    f"or year, plus qualitative country- and brand-level commentary, company news, and "
    f"competitive context drawn from AB InBev's own results releases and filings."
)
