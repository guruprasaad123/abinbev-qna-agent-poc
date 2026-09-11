"""
Central business-domain configuration for the Meridian Brewing Group synthetic universe.

This is the SINGLE SOURCE OF TRUTH for entities (company/category/brand/SKU,
geography, channel), KPIs, and aliases. Both the structured-data generator and
the unstructured-document generator import from here, which is what guarantees
the two corpora share the same entities and themes (a requirement of the
assignment) rather than being generated independently and only coincidentally
overlapping.

NOTE ON REALISM: "Meridian Brewing Group" and all brand names below are
entirely fictional. We deliberately did NOT model this on a real company's
actual financials/brands, even though the domain (a global brewer, mirroring
the kind of portfolio and business-zone structure a company like AB InBev
has) is intentionally realistic — fabricating numbers and attributing them
to a real, identifiable company would be misleading even in an obviously
synthetic exercise. The category/segment mix (International Premium, Craft
& Specialty, Mainstream Lager, and a "Beyond Beer" segment of Non-Alcoholic/
Hard Seltzer) mirrors how a real global brewer actually segments its
portfolio, so the hierarchy, multi-KPI comparison, and temporal-reasoning
challenges are representative of the real domain.
"""

from __future__ import annotations
from datetime import date

COMPANY_NAME = "Meridian Brewing Group"

# ---------------------------------------------------------------------------
# Category hierarchy: Category -> Sub-category
# Mirrors how a global brewer actually segments its portfolio: price-tier
# segments (Premium & Above, Core & Value) plus the "Beyond Beer" growth
# segment (non-alcoholic / hard seltzer) that real brewers report separately.
# ---------------------------------------------------------------------------
CATEGORY_HIERARCHY = {
    "Premium & Above": ["International Premium", "Craft & Specialty"],
    "Core & Value": ["Mainstream Lager"],
    "Beyond Beer": ["Non-Alcoholic", "Hard Seltzer"],
}

# ---------------------------------------------------------------------------
# Brand hierarchy: Brand -> Category / Sub-category, plus SKUs
# ---------------------------------------------------------------------------
BRANDS = {
    "Northstar Lager":       {"category": "Premium & Above", "sub_category": "International Premium",
                               "skus": ["Northstar Lager 330ml Can 6-Pack", "Northstar Lager 500ml Bottle", "Northstar Lager 30L Keg"]},
    "Kestrel Pilsner":       {"category": "Premium & Above", "sub_category": "International Premium",
                               "skus": ["Kestrel Pilsner 330ml Can 4-Pack", "Kestrel Pilsner 500ml Bottle"]},
    "Ironclad Stout":        {"category": "Premium & Above", "sub_category": "Craft & Specialty",
                               "skus": ["Ironclad Stout 330ml Can 4-Pack", "Ironclad Stout 500ml Bottle"]},
    "Copperline Amber Ale":  {"category": "Premium & Above", "sub_category": "Craft & Specialty",
                               "skus": ["Copperline Amber Ale 355ml Can 6-Pack", "Copperline Amber Ale 500ml Bottle"]},
    "Frostpeak Light":       {"category": "Core & Value", "sub_category": "Mainstream Lager",
                               "skus": ["Frostpeak Light 355ml Can 12-Pack", "Frostpeak Light 500ml Bottle", "Frostpeak Light 30L Keg"]},
    "Harborlight Gold":      {"category": "Core & Value", "sub_category": "Mainstream Lager",
                               "skus": ["Harborlight Gold 330ml Can 6-Pack", "Harborlight Gold 1L Bottle"]},
    "Clearwater Zero":       {"category": "Beyond Beer", "sub_category": "Non-Alcoholic",
                               "skus": ["Clearwater Zero 330ml Can 6-Pack", "Clearwater Zero 500ml Bottle"]},
    "Havenbrook Seltzer":    {"category": "Beyond Beer", "sub_category": "Hard Seltzer",
                               "skus": ["Havenbrook Seltzer 355ml Can 12-Pack Variety", "Havenbrook Seltzer 355ml Can 6-Pack"]},
}
ALL_BRANDS = list(BRANDS.keys())

# ---------------------------------------------------------------------------
# Geography hierarchy: Region -> Country -> [Cities]
# Structured facts are generated at COUNTRY grain. Cities exist only in
# unstructured documents / metadata, which lets us demonstrate
# hierarchy-aware fallback (user asks about a city; structured data can only
# answer at country grain, so the agent rolls up and says so explicitly).
# ---------------------------------------------------------------------------
GEO_HIERARCHY = {
    "North America": {"United States": ["New York", "Los Angeles"], "Canada": ["Toronto"]},
    "Europe": {"United Kingdom": ["London"], "Germany": ["Berlin"]},
    "APAC": {"India": ["Mumbai", "Delhi"], "Australia": ["Sydney"]},
    "South America": {"Brazil": ["Sao Paulo"], "Mexico": ["Mexico City"]},
}
ALL_COUNTRIES = [c for region in GEO_HIERARCHY.values() for c in region]
COUNTRY_TO_REGION = {c: r for r, cs in GEO_HIERARCHY.items() for c in cs}
CITY_TO_COUNTRY = {city: c for r, cs in GEO_HIERARCHY.items() for c, cities in cs.items() for city in cities}

# ---------------------------------------------------------------------------
# Channels -- On-Premise (bars/pubs/restaurants) matters far more for a
# brewer than for a generic FMCG portfolio, so it's kept as a first-class
# channel rather than an afterthought.
# ---------------------------------------------------------------------------
ALL_CHANNELS = ["Modern Trade", "Traditional Trade", "E-commerce", "On-Premise"]

# ---------------------------------------------------------------------------
# Time range for structured facts: monthly, Jan 2023 -> Aug 2026 (current YTD)
# ---------------------------------------------------------------------------
DATA_START = date(2023, 1, 1)
DATA_END = date(2026, 8, 1)  # last fully-closed month before "today" 2026-09-11
CURRENT_YEAR = 2026

# ---------------------------------------------------------------------------
# KPI catalog: canonical key -> metadata. Units matter for unit-aware
# presentation; category_scope restricts which KPIs make sense for which
# sub-categories (used for metadata discovery / graceful "not applicable").
# Volume is reported in hectoliters (hL) throughout -- the beer industry's
# standard volume unit -- for every brand, including Beyond Beer.
# ---------------------------------------------------------------------------
KPI_CATALOG = {
    "net_revenue_usd": {
        "label": "Net Revenue", "unit": "USD", "format": "currency",
        "description": "Net sales revenue after trade discounts.",
        "category_scope": "all",
    },
    "volume": {
        "label": "Volume", "unit": "hL", "format": "volume",
        "description": "Sales volume in hectoliters (hL), the standard brewing-industry volume unit.",
        "category_scope": "all",
    },
    "market_share_pct": {
        "label": "Market Share", "unit": "%", "format": "percent",
        "description": "Estimated value share within the relevant segment/country.",
        "category_scope": "all",
    },
    "avg_selling_price_usd": {
        "label": "Average Selling Price (ASP)", "unit": "USD per hL", "format": "currency",
        "description": "Net revenue divided by volume.",
        "category_scope": "all",
    },
    "distribution_acv_pct": {
        "label": "Distribution (ACV)", "unit": "%", "format": "percent",
        "description": "Percent of all-commodity-volume retail outlets stocking the brand.",
        "category_scope": "all",
    },
    "marketing_spend_usd": {
        "label": "Marketing Spend", "unit": "USD", "format": "currency",
        "description": "Above-the-line marketing investment (incl. sponsorships).",
        "category_scope": "all",
    },
    "promo_spend_usd": {
        "label": "Promotion Spend", "unit": "USD", "format": "currency",
        "description": "Trade/consumer promotion investment.",
        "category_scope": "all",
    },
    "gross_margin_pct": {
        "label": "Gross Margin", "unit": "%", "format": "percent",
        "description": "Gross profit as a percent of net revenue.",
        "category_scope": "all",
    },
}
ALL_KPIS = list(KPI_CATALOG.keys())

# ---------------------------------------------------------------------------
# Entity aliases / abbreviations / common typos -> canonical entity.
# This is a deterministic first-pass normalizer that runs BEFORE the LLM
# sees the query (cheap, fast, auditable) -- the LLM is the second-pass
# fallback for anything not in this table (see src/nlu logic in orchestrator.py).
# ---------------------------------------------------------------------------
ENTITY_ALIASES = {
    # Brands: abbreviations & common typos
    "northstar": "Northstar Lager", "nsl": "Northstar Lager", "norhstar": "Northstar Lager",
    "kestrel": "Kestrel Pilsner", "kestral pilsner": "Kestrel Pilsner",
    "ironclad": "Ironclad Stout", "stout": "Ironclad Stout",
    "copperline": "Copperline Amber Ale", "copper line": "Copperline Amber Ale", "amber ale": "Copperline Amber Ale",
    "frostpeak": "Frostpeak Light", "frost peak": "Frostpeak Light", "frostpeek": "Frostpeak Light",
    "harborlight": "Harborlight Gold", "harbor light": "Harborlight Gold", "harbourlight": "Harborlight Gold",
    "clearwater": "Clearwater Zero", "clear water zero": "Clearwater Zero",
    "havenbrook": "Havenbrook Seltzer", "haven brook": "Havenbrook Seltzer",
    # Geography
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom",
    "de": "Germany", "deutschland": "Germany",
    "nyc": "New York", "la": "Los Angeles",
    "na": "North America", "apac": "APAC", "latam": "South America",
    # Channels
    "mt": "Modern Trade", "modern trade": "Modern Trade",
    "tt": "Traditional Trade", "traditional trade": "Traditional Trade",
    "ecom": "E-commerce", "e-comm": "E-commerce", "online": "E-commerce",
    "on prem": "On-Premise", "on-prem": "On-Premise", "bars": "On-Premise", "draught": "On-Premise",
    # KPIs (incl. common non-English terms for multilingual support)
    "revenue": "net_revenue_usd", "sales": "net_revenue_usd", "rev": "net_revenue_usd",
    "ingresos": "net_revenue_usd", "chiffre d'affaires": "net_revenue_usd",
    "vol": "volume", "volumen": "volume", "hectoliters": "volume", "hectolitres": "volume",
    "share": "market_share_pct", "mkt share": "market_share_pct", "market share": "market_share_pct",
    "asp": "avg_selling_price_usd", "price": "avg_selling_price_usd", "precio": "avg_selling_price_usd",
    "acv": "distribution_acv_pct", "distribution": "distribution_acv_pct",
    "marketing": "marketing_spend_usd", "a&p": "marketing_spend_usd", "sponsorship": "marketing_spend_usd",
    "promo": "promo_spend_usd", "promotion": "promo_spend_usd",
    "margin": "gross_margin_pct", "gm": "gross_margin_pct",
}

# Business-domain scope statement, shown in greeting / used for out-of-scope detection
DOMAIN_DESCRIPTION = (
    f"{COMPANY_NAME} performance across its Premium & Above (International Premium, "
    f"Craft & Specialty), Core & Value (Mainstream Lager), and Beyond Beer (Non-Alcoholic, "
    f"Hard Seltzer) portfolios -- revenue, volume, market share, pricing, distribution, "
    f"marketing/promotion spend and margin, by brand, market and channel, plus related "
    f"company news, market research and competitive context."
)
