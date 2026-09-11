"""
Generate the synthetic structured dataset for Solara FMCG Group.

Produces a SQLite database at data/db/solara_fmcg.db with:
  - dim_brand, dim_geo, dim_channel : dimension tables
  - fact_monthly_kpi                : brand x country x channel x month grain fact table

Design choices (see docs/DESIGN_DECISIONS.md for the full rationale):
  - Deterministic seed -> reproducible dataset (important for grading/demo stability).
  - Realistic-looking but clearly synthetic time series: base level per brand/country
    (bigger brands/markets get bigger numbers), a mild YoY growth trend, monthly
    seasonality (Q4 uplift for snacks/confectionery, summer uplift for beer/soft
    drinks), and bounded random noise.
  - KPIs are internally consistent: avg_selling_price = revenue / volume (approx),
    so an agent cross-checking derived metrics against stored ones will find them
    coherent -- this matters for the "answer validation" capability.
"""
import sqlite3
import random
from pathlib import Path
from datetime import date

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import (
    BRANDS, ALL_BRANDS, GEO_HIERARCHY, ALL_COUNTRIES, COUNTRY_TO_REGION,
    ALL_CHANNELS, DATA_START, DATA_END,
)

random.seed(42)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db" / "solara_fmcg.db"

# Relative base "size" multipliers so numbers feel like a real portfolio rather
# than uniform noise -- flagship brands and larger markets are bigger.
BRAND_BASE = {
    "Glacier Peak": 1.6, "Ironclad Stout": 0.6,
    "Vivo Splash": 1.2, "PureSpring": 0.7,
    "CrunchWave": 1.3, "Golden Harvest": 0.8,
    "SweetPeak": 1.0, "CocoNest": 0.5,
}
COUNTRY_BASE = {
    "United States": 2.2, "Canada": 0.6, "United Kingdom": 1.1, "Germany": 1.3,
    "India": 1.5, "Australia": 0.6, "Brazil": 1.0, "Mexico": 0.7,
}
CHANNEL_SHARE = {  # relative share of volume by channel (sums ~1.0)
    "Modern Trade": 0.42, "Traditional Trade": 0.28, "E-commerce": 0.15, "On-Premise": 0.15,
}
# Beer sub-category leans more on On-Premise; non-alc/food lean less. Small
# per-subcategory adjustment applied at generation time.
SUBCAT_ONPREM_ADJ = {"Beer": 1.6, "Non-Alcoholic": 0.5, "Salty Snacks": 0.3, "Confectionery": 0.4}


def month_range(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


def seasonality(sub_category: str, month: int) -> float:
    """Return a multiplier >0 capturing category-specific seasonality."""
    if sub_category in ("Beer", "Non-Alcoholic"):
        # Summer (N. hemisphere) uplift centered July, mild
        return 1.0 + 0.18 * (1 - abs(month - 7) / 6)
    else:  # Confectionery / Salty Snacks -> Q4 holiday uplift
        return 1.0 + (0.30 if month in (11, 12) else 0.05 if month in (1,) else 0.0)


def build():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""CREATE TABLE dim_brand (
        brand TEXT PRIMARY KEY, category TEXT NOT NULL, sub_category TEXT NOT NULL
    )""")
    for b, meta in BRANDS.items():
        cur.execute("INSERT INTO dim_brand VALUES (?,?,?)", (b, meta["category"], meta["sub_category"]))

    cur.execute("""CREATE TABLE dim_geo (
        country TEXT PRIMARY KEY, region TEXT NOT NULL
    )""")
    for country, region in COUNTRY_TO_REGION.items():
        cur.execute("INSERT INTO dim_geo VALUES (?,?)", (country, region))

    cur.execute("""CREATE TABLE dim_channel (channel TEXT PRIMARY KEY)""")
    for ch in ALL_CHANNELS:
        cur.execute("INSERT INTO dim_channel VALUES (?)", (ch,))

    cur.execute("""CREATE TABLE fact_monthly_kpi (
        brand TEXT NOT NULL,
        country TEXT NOT NULL,
        channel TEXT NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        net_revenue_usd REAL NOT NULL,
        volume REAL NOT NULL,
        volume_unit TEXT NOT NULL,
        market_share_pct REAL NOT NULL,
        avg_selling_price_usd REAL NOT NULL,
        distribution_acv_pct REAL NOT NULL,
        marketing_spend_usd REAL NOT NULL,
        promo_spend_usd REAL NOT NULL,
        gross_margin_pct REAL NOT NULL,
        FOREIGN KEY (brand) REFERENCES dim_brand(brand),
        FOREIGN KEY (country) REFERENCES dim_geo(country),
        FOREIGN KEY (channel) REFERENCES dim_channel(channel)
    )""")

    months = list(month_range(DATA_START, DATA_END))
    n_months = len(months)
    rows = []

    for brand, meta in BRANDS.items():
        sub_cat = meta["sub_category"]
        is_beverage = meta["category"] == "Beverages"
        volume_unit = "hL" if is_beverage else "K units"
        base_price = {"Beer": 65, "Non-Alcoholic": 22, "Salty Snacks": 18, "Confectionery": 14}[sub_cat]
        brand_mult = BRAND_BASE[brand]

        for country in ALL_COUNTRIES:
            country_mult = COUNTRY_BASE[country]
            # Small fixed per-brand-country random factor (some brands under-index in some markets)
            local_mix = 0.6 + 1.0 * random.random()
            base_monthly_volume = 8000 * brand_mult * country_mult * local_mix / 12 * n_months / n_months  # ~monthly hL/Kunits

            for ci, month_idx in enumerate(months):
                year, month = month_idx
                # YoY growth trend: ~4-9% annualized, brand-specific
                years_elapsed = (year - months[0][0]) + (month - months[0][1]) / 12
                growth_rate = {"Glacier Peak": 1.06, "Ironclad Stout": 1.09, "Vivo Splash": 1.08,
                                "PureSpring": 1.10, "CrunchWave": 1.05, "Golden Harvest": 1.07,
                                "SweetPeak": 1.04, "CocoNest": 1.11}[brand]
                trend = growth_rate ** years_elapsed
                season = seasonality(sub_cat, month)
                total_volume_month = base_monthly_volume * trend * season

                for channel in ALL_CHANNELS:
                    ch_share = CHANNEL_SHARE[channel]
                    if channel == "On-Premise":
                        ch_share *= SUBCAT_ONPREM_ADJ[sub_cat]
                    noise = random.uniform(0.90, 1.10)
                    volume = round(total_volume_month * ch_share * noise, 1)
                    if volume <= 0:
                        continue

                    price = base_price * random.uniform(0.95, 1.05) * (1.03 ** years_elapsed)
                    if channel == "E-commerce":
                        price *= 1.03  # slight premium online
                    if channel == "On-Premise":
                        price *= 1.8  # markup at bars/restaurants

                    revenue = round(volume * price, 2)
                    market_share = round(max(0.5, min(45.0, 6 + 10 * brand_mult / country_mult + random.uniform(-1.5, 1.5) + 0.4 * years_elapsed)), 2)
                    distribution = round(max(20.0, min(98.0, 55 + 20 * brand_mult + random.uniform(-8, 8))), 1)
                    marketing_spend = round(revenue * random.uniform(0.03, 0.07), 2)
                    promo_spend = round(revenue * random.uniform(0.02, 0.05), 2)
                    gross_margin = round(max(25.0, min(65.0, 48 + (5 if is_beverage else -3) + random.uniform(-4, 4))), 1)

                    rows.append((
                        brand, country, channel, year, month,
                        revenue, volume, volume_unit, market_share,
                        round(price, 2), distribution, marketing_spend, promo_spend, gross_margin,
                    ))

    cur.executemany(
        """INSERT INTO fact_monthly_kpi
           (brand, country, channel, year, month, net_revenue_usd, volume, volume_unit,
            market_share_pct, avg_selling_price_usd, distribution_acv_pct,
            marketing_spend_usd, promo_spend_usd, gross_margin_pct)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM fact_monthly_kpi")
    n = cur.fetchone()[0]
    print(f"Generated {n:,} fact rows across {len(ALL_BRANDS)} brands x {len(ALL_COUNTRIES)} countries "
          f"x {len(ALL_CHANNELS)} channels x {n_months} months -> {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    build()
