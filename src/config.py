"""
Central business-domain configuration for the Solara FMCG Group synthetic universe.

This is the SINGLE SOURCE OF TRUTH for entities (company/category/brand/SKU,
geography, channel), KPIs, and aliases. Both the structured-data generator and
the unstructured-document generator import from here, which is what guarantees
the two corpora share the same entities and themes (a requirement of the
assignment) rather than being generated independently and only coincidentally
overlapping.

NOTE ON REALISM: "Solara FMCG Group" and all brand names below are entirely
fictional. We deliberately did NOT model this on a real company's actual
financials/brands, even though the assignment domain is FMCG — fabricated
numbers attributed to a real company would be misleading. The category mix
(beer / non-alcoholic beverages / snacks / confectionery) mirrors a realistic
multi-category FMCG portfolio so the retrieval and reasoning challenges
(hierarchy, multi-KPI comparisons, temporal reasoning) are representative.
"""

from __future__ import annotations
from datetime import date

COMPANY_NAME = "Solara FMCG Group"

# ---------------------------------------------------------------------------
# Category hierarchy: Category -> Sub-category
# ---------------------------------------------------------------------------
CATEGORY_HIERARCHY = {
    "Beverages": ["Beer", "Non-Alcoholic"],
    "Food": ["Salty Snacks", "Confectionery"],
}

# ---------------------------------------------------------------------------
# Brand hierarchy: Brand -> Category / Sub-category, plus SKUs
# ---------------------------------------------------------------------------
BRANDS = {
    "Glacier Peak":   {"category": "Beverages", "sub_category": "Beer",
                        "skus": ["Glacier Peak 330ml Can 6-Pack", "Glacier Peak 500ml Bottle", "Glacier Peak 1L Multipack"]},
    "Ironclad Stout": {"category": "Beverages", "sub_category": "Beer",
                        "skus": ["Ironclad Stout 330ml Can 4-Pack", "Ironclad Stout 500ml Bottle"]},
    "Vivo Splash":    {"category": "Beverages", "sub_category": "Non-Alcoholic",
                        "skus": ["Vivo Splash 500ml Bottle", "Vivo Splash 1.5L Bottle", "Vivo Splash Zero 500ml Bottle"]},
    "PureSpring":     {"category": "Beverages", "sub_category": "Non-Alcoholic",
                        "skus": ["PureSpring 500ml Bottle", "PureSpring 1L Bottle"]},
    "CrunchWave":     {"category": "Food", "sub_category": "Salty Snacks",
                        "skus": ["CrunchWave 150g Bag", "CrunchWave Family Pack 300g"]},
    "Golden Harvest": {"category": "Food", "sub_category": "Salty Snacks",
                        "skus": ["Golden Harvest 120g Bag", "Golden Harvest Sharing Pack 250g"]},
    "SweetPeak":      {"category": "Food", "sub_category": "Confectionery",
                        "skus": ["SweetPeak Bar 45g", "SweetPeak Sharing Bag 180g"]},
    "CocoNest":       {"category": "Food", "sub_category": "Confectionery",
                        "skus": ["CocoNest Bar 40g", "CocoNest Gift Box 200g"]},
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
    "LATAM": {"Brazil": ["Sao Paulo"], "Mexico": ["Mexico City"]},
}
ALL_COUNTRIES = [c for region in GEO_HIERARCHY.values() for c in region]
COUNTRY_TO_REGION = {c: r for r, cs in GEO_HIERARCHY.items() for c in cs}
CITY_TO_COUNTRY = {city: c for r, cs in GEO_HIERARCHY.items() for c, cities in cs.items() for city in cities}

# ---------------------------------------------------------------------------
# Channels
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
# ---------------------------------------------------------------------------
KPI_CATALOG = {
    "net_revenue_usd": {
        "label": "Net Revenue", "unit": "USD", "format": "currency",
        "description": "Net sales revenue after trade discounts.",
        "category_scope": "all",
    },
    "volume": {
        "label": "Volume", "unit": "varies by category", "format": "volume",
        "description": "Sales volume. Reported in hectoliters (hL) for Beverages, thousand units (K units) for Food.",
        "category_scope": "all",
    },
    "market_share_pct": {
        "label": "Market Share", "unit": "%", "format": "percent",
        "description": "Estimated value share within the relevant category/country.",
        "category_scope": "all",
    },
    "avg_selling_price_usd": {
        "label": "Average Selling Price (ASP)", "unit": "USD", "format": "currency",
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
        "description": "Above-the-line marketing investment.",
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
# sees the query (cheap, fast, auditable) — the LLM is the second-pass
# fallback for anything not in this table (see src/nlu.py).
# ---------------------------------------------------------------------------
ENTITY_ALIASES = {
    # Brands: abbreviations & common typos
    "gp": "Glacier Peak", "glacier": "Glacier Peak", "glacer peak": "Glacier Peak", "glacie peak": "Glacier Peak",
    "ironclad": "Ironclad Stout", "stout": "Ironclad Stout",
    "vivo": "Vivo Splash", "vivosplash": "Vivo Splash",
    "purespring": "PureSpring", "pure spring": "PureSpring",
    "crunchwave": "CrunchWave", "crunch wave": "CrunchWave", "cw": "CrunchWave",
    "golden harvest": "Golden Harvest", "gh": "Golden Harvest",
    "sweetpeak": "SweetPeak", "sweet peak": "SweetPeak",
    "coconest": "CocoNest", "coco nest": "CocoNest",
    # Geography
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom",
    "de": "Germany", "deutschland": "Germany",
    "nyc": "New York", "la": "Los Angeles",
    "na": "North America", "apac": "APAC", "latam": "LATAM",
    # Channels
    "mt": "Modern Trade", "modern trade": "Modern Trade",
    "tt": "Traditional Trade", "traditional trade": "Traditional Trade",
    "ecom": "E-commerce", "e-comm": "E-commerce", "online": "E-commerce",
    "on prem": "On-Premise", "on-prem": "On-Premise", "bars": "On-Premise",
    # KPIs (incl. common non-English terms for multilingual support)
    "revenue": "net_revenue_usd", "sales": "net_revenue_usd", "rev": "net_revenue_usd",
    "ingresos": "net_revenue_usd", "chiffre d'affaires": "net_revenue_usd",
    "vol": "volume", "volumen": "volume",
    "share": "market_share_pct", "mkt share": "market_share_pct", "market share": "market_share_pct",
    "asp": "avg_selling_price_usd", "price": "avg_selling_price_usd", "precio": "avg_selling_price_usd",
    "acv": "distribution_acv_pct", "distribution": "distribution_acv_pct",
    "marketing": "marketing_spend_usd", "a&p": "marketing_spend_usd",
    "promo": "promo_spend_usd", "promotion": "promo_spend_usd",
    "margin": "gross_margin_pct", "gm": "gross_margin_pct",
}

# Business-domain scope statement, shown in greeting / used for out-of-scope detection
DOMAIN_DESCRIPTION = (
    f"{COMPANY_NAME} performance across its Beverages (Beer, Non-Alcoholic) and "
    f"Food (Salty Snacks, Confectionery) portfolios — revenue, volume, market share, "
    f"pricing, distribution, marketing/promotion spend and margin, by brand, market "
    f"and channel, plus related company news, market research and competitive context."
)
