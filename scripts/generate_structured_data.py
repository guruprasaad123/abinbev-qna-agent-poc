"""
Generate the synthetic structured dataset for Meridian Brewing Group.

Produces a SQLite database at data/db/meridian_brewing.db with:
  - dim_brand, dim_geo, dim_channel : dimension tables
  - fact_monthly_kpi                : brand x country x channel x month grain fact table

Design choices (see docs/DESIGN_DECISIONS.md for the full rationale):
  - Deterministic seed -> reproducible dataset (important for grading/demo stability).
  - Realistic-looking but clearly synthetic time series: base level per brand/country
    (bigger brands/markets get bigger numbers), a mild YoY growth trend (faster for
    the "Beyond Beer" non-alcoholic/hard-seltzer segment, mirroring the real-world
    growth trend in that segment), monthly seasonality (a summer uplift, common
    across beer/near-beer/seltzer occasions), and bounded random noise.
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

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db" / "meridian_brewing.db"

# Relative base "size" multipliers so numbers feel like a real portfolio rather
# than uniform noise -- flagship brands and larger markets are bigger.
BRAND_BASE = {
    "Northstar Lager": 1.6, "Kestrel Pilsner": 0.9,
    "Ironclad Stout": 0.6, "Copperline Amber Ale": 0.5,
    "Frostpeak Light": 1.3, "Harborlight Gold": 0.8,
    "Clearwater Zero": 0.7, "Havenbrook Seltzer": 0.6,
}
# Annualized YoY growth rate per brand -- Beyond Beer (non-alc / hard seltzer)
# grows fastest, mirroring the real-world trend in that segment; Mainstream
# Lager grows slowest, reflecting a more mature/flat segment.
BRAND_GROWTH = {
    "Northstar Lager": 1.05, "Kestrel Pilsner": 1.06,
    "Ironclad Stout": 1.09, "Copperline Amber Ale": 1.08,
    "Frostpeak Light": 1.02, "Harborlight Gold": 1.03,
    "Clearwater Zero": 1.14, "Havenbrook Seltzer": 1.16,
}
# Base price (USD per hL) by sub-category -- craft/specialty commands the
# highest price, mainstream lager the lowest.
BASE_PRICE_BY_SUBCAT = {
    "International Premium": 70, "Craft & Specialty": 85,
    "Mainstream Lager": 45, "Non-Alcoholic": 55, "Hard Seltzer": 60,
}
COUNTRY_BASE = {
    "United States": 2.2, "Canada": 0.6, "United Kingdom": 1.1, "Germany": 1.3,
    "India": 1.5, "Australia": 0.6, "Brazil": 1.0, "Mexico": 0.7,
}
CHANNEL_SHARE = {  # relative share of volume by channel (sums ~1.0)
    "Modern Trade": 0.42, "Traditional Trade": 0.28, "E-commerce": 0.15, "On-Premise": 0.15,
}
# On-Premise (bars/pubs/restaurants) over-indexes for occasion-led premium and
# craft drinking, under-indexes for retail-led Beyond Beer purchases.
SUBCAT_ONPREM_ADJ = {
    "International Premium": 1.4, "Craft & Specialty": 1.7,
    "Mainstream Lager": 1.0, "Non-Alcoholic": 0.5, "Hard Seltzer": 0.6,
}


def month_range(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            m = 1
            y += 1


def seasonality(month: int) -> float:
    """Summer (N. hemisphere) uplift centered on July -- applies across beer,
    non-alcoholic beer, and hard seltzer occasions alike."""
    return 1.0 + 0.20 * (1 - abs(month - 7) / 6)


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
        base_price = BASE_PRICE_BY_SUBCAT[sub_cat]
        brand_mult = BRAND_BASE[brand]
        growth_rate = BRAND_GROWTH[brand]

        for country in ALL_COUNTRIES:
            country_mult = COUNTRY_BASE[country]
            # Small fixed per-brand-country random factor (some brands under-index in some markets)
            local_mix = 0.6 + 1.0 * random.random()
            base_monthly_volume = 8000 * brand_mult * country_mult * local_mix / 12 * n_months / n_months  # ~monthly hL

            for month_idx in months:
                year, month = month_idx
                years_elapsed = (year - months[0][0]) + (month - months[0][1]) / 12
                trend = growth_rate ** years_elapsed
                season = seasonality(month)
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
                    gross_margin = round(max(25.0, min(65.0, 50 + random.uniform(-4, 4))), 1)

                    rows.append((
                        brand, country, channel, year, month,
                        revenue, volume, "hL", market_share,
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
