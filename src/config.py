"""
Central business-domain configuration for the Anheuser-Busch InBev (AB InBev) universe.

This is the SINGLE SOURCE OF TRUTH for entities (company/category/brand/SKU,
geography, channel), KPIs, and aliases. Both the structured-data generator and
the unstructured-document generator import from here, which is what guarantees
the two corpora share the same entities and themes (a requirement of the
assignment) rather than being generated independently and only coincidentally
overlapping.

DOMAIN REALISM: Anheuser-Busch InBev (AB InBev) is the world's leading brewer.
Its portfolio spans global megabrands (Budweiser, Stella Artois, Corona,
Michelob ULTRA), local champions (Bud Light in the US, Brahma in Brazil),
specialty Belgian wheat (Hoegaarden), and its rapidly growing "Beyond Beer"
flagship (Corona Cero 0.0% Non-Alcoholic, official Worldwide Olympic Partner).
Geographic reporting zones cover North America, Middle Americas, South America,
Europe, and APAC. Commercial channels include Modern Trade, Traditional Trade,
the critical On-Premise channel, and the proprietary BEES B2B digital platform.
All facts are modeled deterministically for complete reproducibility.
"""

from __future__ import annotations
from datetime import date

COMPANY_NAME = "Anheuser-Busch InBev"
COMPANY_SHORT_NAME = "AB InBev"

# ---------------------------------------------------------------------------
# Category hierarchy: Category -> Sub-category
# Mirrors how AB InBev segments its portfolio:
# - Premium & Above: Global Premium, Premium Active, Craft & Specialty
# - Core & Value: Mainstream Core, Mainstream Light
# - Beyond Beer: Non-Alcoholic (0.0% growth segment)
# ---------------------------------------------------------------------------
CATEGORY_HIERARCHY = {
    "Premium & Above": ["Global Premium", "Premium Active", "Craft & Specialty"],
    "Core & Value": ["Mainstream Core", "Mainstream Light"],
    "Beyond Beer": ["Non-Alcoholic"],
}

# ---------------------------------------------------------------------------
# Brand hierarchy: Brand -> Category / Sub-category, plus representative SKUs
# ---------------------------------------------------------------------------
BRANDS = {
    "Corona": {
        "category": "Premium & Above",
        "sub_category": "Global Premium",
        "skus": ["Corona Extra 330ml Bottle 6-Pack", "Corona Extra 355ml Can", "Corona Extra 710ml Caguama"],
    },
    "Stella Artois": {
        "category": "Premium & Above",
        "sub_category": "Global Premium",
        "skus": ["Stella Artois 330ml Chalice Bottle 6-Pack", "Stella Artois 500ml Can", "Stella Artois 30L Draught Keg"],
    },
    "Michelob ULTRA": {
        "category": "Premium & Above",
        "sub_category": "Premium Active",
        "skus": ["Michelob ULTRA 355ml Can 12-Pack", "Michelob ULTRA 330ml Slim Can", "Michelob ULTRA 500ml Bottle"],
    },
    "Hoegaarden": {
        "category": "Premium & Above",
        "sub_category": "Craft & Specialty",
        "skus": ["Hoegaarden White 330ml Bottle", "Hoegaarden Rosée 330ml Bottle", "Hoegaarden 20L Draught Keg"],
    },
    "Budweiser": {
        "category": "Core & Value",
        "sub_category": "Mainstream Core",
        "skus": ["Budweiser 355ml Can 6-Pack", "Budweiser 500ml Bottle", "Budweiser 50L Draught Keg"],
    },
    "Bud Light": {
        "category": "Core & Value",
        "sub_category": "Mainstream Light",
        "skus": ["Bud Light 355ml Can 12-Pack", "Bud Light 500ml Bottle", "Bud Light 50L Draught Keg"],
    },
    "Brahma": {
        "category": "Core & Value",
        "sub_category": "Mainstream Core",
        "skus": ["Brahma Chopp 350ml Can", "Brahma Duplo Malte 350ml Can 8-Pack", "Brahma 600ml Returnable Glass Bottle"],
    },
    "Corona Cero": {
        "category": "Beyond Beer",
        "sub_category": "Non-Alcoholic",
        "skus": ["Corona Cero 0.0% 330ml Bottle 6-Pack", "Corona Cero 0.0% 330ml Slim Can"],
    },
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
    "North America": {
        "United States": ["New York", "St. Louis", "Los Angeles"],
        "Canada": ["Toronto", "Montreal"],
    },
    "Middle Americas": {
        "Mexico": ["Mexico City", "Monterrey"],
    },
    "South America": {
        "Brazil": ["Sao Paulo", "Rio de Janeiro"],
    },
    "Europe": {
        "United Kingdom": ["London"],
        "Belgium": ["Brussels", "Leuven"],  # Leuven is AB InBev's global headquarters & historic Stella brewery
    },
    "APAC": {
        "China": ["Shanghai"],
        "India": ["Mumbai", "Bengaluru"],
    },
}
ALL_COUNTRIES = [c for region in GEO_HIERARCHY.values() for c in region]
COUNTRY_TO_REGION = {c: r for r, cs in GEO_HIERARCHY.items() for c in cs}
CITY_TO_COUNTRY = {city: c for r, cs in GEO_HIERARCHY.items() for c, cities in cs.items() for city in cities}

# ---------------------------------------------------------------------------
# Channels -- On-Premise is critical for a global brewer; BEES & E-commerce
# reflects AB InBev's leading proprietary B2B digital ordering marketplace
# (BEES) and D2C fulfillment (TaDa Delivery).
# ---------------------------------------------------------------------------
ALL_CHANNELS = ["Modern Trade", "Traditional Trade", "On-Premise", "BEES & E-commerce"]

# ---------------------------------------------------------------------------
# Time range for structured facts: monthly, Jan 2023 -> Aug 2026 (current YTD)
# ---------------------------------------------------------------------------
DATA_START = date(2023, 1, 1)
DATA_END = date(2026, 8, 1)  # last fully-closed month before "today" 2026-09-11
CURRENT_YEAR = 2026

# ---------------------------------------------------------------------------
# KPI catalog: canonical key -> metadata.
# Volume is reported in hectoliters (hL) throughout -- the brewing industry's
# standard volume unit (1 hL = 100 liters = ~26.4 US gallons).
# ---------------------------------------------------------------------------
KPI_CATALOG = {
    "net_revenue_usd": {
        "label": "Net Revenue", "unit": "USD", "format": "currency",
        "description": "Net sales revenue after excise taxes and trade discounts (Normalized Revenue).",
        "category_scope": "all",
    },
    "volume": {
        "label": "Volume", "unit": "hL", "format": "volume",
        "description": "Sales volume in hectoliters (hL), the global standard brewing unit.",
        "category_scope": "all",
    },
    "market_share_pct": {
        "label": "Market Share", "unit": "%", "format": "percent",
        "description": "Estimated volume/value share within the relevant segment and country.",
        "category_scope": "all",
    },
    "avg_selling_price_usd": {
        "label": "Net Revenue per hL (ASP)", "unit": "USD per hL", "format": "currency",
        "description": "Net revenue divided by volume (Net Revenue per hectoliter).",
        "category_scope": "all",
    },
    "distribution_acv_pct": {
        "label": "Distribution (ACV / BEES Reach)", "unit": "%", "format": "percent",
        "description": "Percent of retail/on-premise outlets carrying the brand or active on BEES platform.",
        "category_scope": "all",
    },
    "marketing_spend_usd": {
        "label": "Marketing Spend", "unit": "USD", "format": "currency",
        "description": "Sales and marketing investment (including global sports sponsorships like Olympics and FIFA).",
        "category_scope": "all",
    },
    "promo_spend_usd": {
        "label": "Promotion Spend", "unit": "USD", "format": "currency",
        "description": "Trade and consumer promotion investment.",
        "category_scope": "all",
    },
    "gross_margin_pct": {
        "label": "Gross Margin", "unit": "%", "format": "percent",
        "description": "Gross profit as a percentage of net revenue.",
        "category_scope": "all",
    },
}
ALL_KPIS = list(KPI_CATALOG.keys())

# ---------------------------------------------------------------------------
# Known external competitors (for fallback & web search routing)
# ---------------------------------------------------------------------------
KNOWN_COMPETITORS = [
    "Heineken", "Heineken NV", "Carlsberg", "Carlsberg Group",
    "Molson Coors", "Molson Coors Beverage Company",
    "Constellation Brands", "Asahi", "Asahi Group Holdings",
]

# ---------------------------------------------------------------------------
# Entity aliases / abbreviations / common typos -> canonical entity.
# Deterministic first-pass normalizer before LLM processing.
# ---------------------------------------------------------------------------
ENTITY_ALIASES = {
    # Brands
    "corona": "Corona", "corona extra": "Corona", "coronita": "Corona", "coron": "Corona", "corna": "Corona",
    "stella": "Stella Artois", "stella artois": "Stella Artois", "artois": "Stella Artois",
    "ultra": "Michelob ULTRA", "michelob": "Michelob ULTRA", "michelob ultra": "Michelob ULTRA", "mich ultra": "Michelob ULTRA",
    "hoegaarden": "Hoegaarden", "hoegarden": "Hoegaarden", "hoegard": "Hoegaarden",
    "bud": "Budweiser", "budweiser": "Budweiser", "the king of beers": "Budweiser", "budweiser lager": "Budweiser",
    "bud light": "Bud Light", "budlight": "Bud Light", "bl": "Bud Light",
    "brahma": "Brahma", "brahma chopp": "Brahma", "brahma duplo malte": "Brahma",
    "corona cero": "Corona Cero", "cero": "Corona Cero", "corona 0.0": "Corona Cero",
    "corona zero": "Corona Cero", "non-alcoholic corona": "Corona Cero",

    # Geography: Countries & Regions
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States", "america": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom", "great britain": "United Kingdom",
    "belgium": "Belgium", "belgique": "Belgium", "belgie": "Belgium",
    "brazil": "Brazil", "brasil": "Brazil",
    "mexico": "Mexico", "méxico": "Mexico", "mx": "Mexico", "mexco": "Mexico", "mejico": "Mexico",
    "canada": "Canada",
    "china": "China", "cn": "China", "prc": "China",
    "india": "India", "bharat": "India",
    "na": "North America", "latam": "South America", "middle americas": "Middle Americas",
    "apac": "APAC", "emea": "Europe", "europe": "Europe",

    # Cities (for rollup hierarchy fallback)
    "nyc": "New York", "new york city": "New York", "new york": "New York",
    "st louis": "St. Louis", "st. louis": "St. Louis", "saint louis": "St. Louis",
    "l.a.": "Los Angeles", "los angeles": "Los Angeles",
    "toronto": "Toronto", "montreal": "Montreal",
    "cdmx": "Mexico City", "mexico city": "Mexico City", "monterrey": "Monterrey",
    "sao paulo": "Sao Paulo", "são paulo": "Sao Paulo", "rio": "Rio de Janeiro", "rio de janeiro": "Rio de Janeiro",
    "london": "London", "brussels": "Brussels", "leuven": "Leuven",
    "shanghai": "Shanghai", "mumbai": "Mumbai", "bengaluru": "Bengaluru", "bangalore": "Bengaluru",

    # Channels
    "mt": "Modern Trade", "modern trade": "Modern Trade", "supermarkets": "Modern Trade",
    "tt": "Traditional Trade", "traditional trade": "Traditional Trade", "bodegas": "Traditional Trade", "tienditas": "Traditional Trade",
    "on prem": "On-Premise", "on-prem": "On-Premise", "on premise": "On-Premise", "bars": "On-Premise", "pubs": "On-Premise", "draught": "On-Premise",
    "bees": "BEES & E-commerce", "b2b": "BEES & E-commerce", "ecom": "BEES & E-commerce", "e-commerce": "BEES & E-commerce", "tada": "BEES & E-commerce", "online": "BEES & E-commerce",

    # KPIs (Multilingual & colloquial terms)
    "revenue": "net_revenue_usd", "sales": "net_revenue_usd", "rev": "net_revenue_usd", "revenu": "net_revenue_usd", "revinue": "net_revenue_usd",
    "ingresos": "net_revenue_usd", "chiffre d'affaires": "net_revenue_usd", "receita": "net_revenue_usd",
    "bikri": "net_revenue_usd", "turnover": "net_revenue_usd",
    "vol": "volume", "volumen": "volume", "hectoliters": "volume", "hectolitres": "volume", "hl": "volume",
    "share": "market_share_pct", "mkt share": "market_share_pct", "market share": "market_share_pct", "part de marché": "market_share_pct", "participacion": "market_share_pct",
    "asp": "avg_selling_price_usd", "price": "avg_selling_price_usd", "precio": "avg_selling_price_usd", "nr/hl": "avg_selling_price_usd", "net revenue per hl": "avg_selling_price_usd",
    "acv": "distribution_acv_pct", "distribution": "distribution_acv_pct", "reach": "distribution_acv_pct", "penetration": "distribution_acv_pct",
    "marketing": "marketing_spend_usd", "a&p": "marketing_spend_usd", "sponsorship": "marketing_spend_usd", "olympics": "marketing_spend_usd", "fifa": "marketing_spend_usd",
    "promo": "promo_spend_usd", "promotion": "promo_spend_usd", "trade promo": "promo_spend_usd",
    "margin": "gross_margin_pct", "gm": "gross_margin_pct", "gross margin": "gross_margin_pct", "margen": "gross_margin_pct",
}

# Business-domain scope statement, shown in greeting / used for out-of-scope detection
DOMAIN_DESCRIPTION = (
    f"{COMPANY_NAME} ({COMPANY_SHORT_NAME}) global performance across its Premium & Above "
    f"(Corona, Stella Artois, Michelob ULTRA, Hoegaarden), Core & Value (Budweiser, Bud Light, "
    f"Brahma), and Beyond Beer (Corona Cero 0.0%) portfolios -- net revenue, volume (hL), "
    f"market share, pricing (NR/hL), distribution/BEES reach, marketing/sponsorships, "
    f"promotion spend, and gross margin by brand, country, channel, and period, plus related "
    f"company earnings releases, digital B2B marketplace (BEES) initiatives, sustainability (ESG), "
    f"and competitive intelligence."
)
