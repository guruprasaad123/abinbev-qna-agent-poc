"""
Generate the synthetic structured dataset for Anheuser-Busch InBev (AB InBev).

Produces a SQLite database at data/db/abinbev.db with:
  - dim_brand, dim_geo, dim_channel : dimension tables
  - fact_monthly_kpi                : brand x country x channel x month grain fact table

Design choices:
  - Deterministic seed (42) -> 100% reproducible dataset (critical for grading/evaluation).
  - Realistic time series reflecting AB InBev's real-world business dynamics:
      * Rapid growth for Corona Cero (Beyond Beer 0.0%) and Michelob ULTRA.
      * Major volume bases in the United States, Mexico, and Brazil.
      * Seasonality centered around summer drinking occasions and sporting events.
      * Commercial channels featuring Traditional Trade, Modern Trade, On-Premise,
        and the proprietary BEES B2B digital platform.
  - KPIs are mathematically coherent: avg_selling_price = revenue / volume.
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

# Explicit fixed seed for full reproducibility
random.seed(42)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db" / "abinbev.db"

# Relative base volume multiplier per brand reflecting global megabrand scale
BRAND_BASE = {
    "Corona": 1.8,
    "Stella Artois": 1.4,
    "Michelob ULTRA": 1.5,
    "Hoegaarden": 0.8,
    "Budweiser": 1.7,
    "Bud Light": 1.6,
    "Brahma": 1.5,
    "Corona Cero": 0.9,
}

# Annualized YoY growth rate per brand
# Corona Cero (non-alcoholic 0.0%) and Michelob ULTRA grow fastest, reflecting real consumer trends
BRAND_GROWTH = {
    "Corona": 1.07,
    "Stella Artois": 1.05,
    "Michelob ULTRA": 1.11,
    "Hoegaarden": 1.08,
    "Budweiser": 1.03,
    "Bud Light": 1.02,
    "Brahma": 1.04,
    "Corona Cero": 1.20,
}

# Base price (USD per hL) by sub-category
BASE_PRICE_BY_SUBCAT = {
    "Global Premium": 80,
    "Premium Active": 75,
    "Craft & Specialty": 90,
    "Mainstream Core": 50,
    "Mainstream Light": 48,
    "Non-Alcoholic": 65,
}

# Country volume multiplier reflecting key AB InBev global markets
COUNTRY_BASE = {
    "United States": 2.4,
    "Canada": 0.7,
    "Mexico": 2.1,
    "Brazil": 2.2,
    "United Kingdom": 1.2,
    "Belgium": 0.8,
    "China": 1.8,
    "India": 1.3,
}

# Relative volume share by commercial channel
CHANNEL_SHARE = {
    "Modern Trade": 0.35,
    "Traditional Trade": 0.35,
    "On-Premise": 0.18,
    "BEES & E-commerce": 0.12,
}

# On-Premise channel weighting by sub-category
SUBCAT_ONPREM_ADJ = {
    "Global Premium": 1.4,
    "Premium Active": 1.3,
    "Craft & Specialty": 1.8,
    "Mainstream Core": 1.0,
    "Mainstream Light": 1.1,
    "Non-Alcoholic": 0.7,
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
    """Summer uplift (centered around July) for outdoor and festive occasions."""
    return 1.0 + 0.20 * (1 - abs(month - 7) / 6)


def build():
    # Enforce deterministic seed at execution time
    random.seed(42)

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
            # Deterministic per-brand-country affinity
            local_mix = 0.6 + 0.8 * random.random()
            # Brahma heavily indexes in Brazil; Bud Light in US; Stella/Hoegaarden in Belgium/UK
            if brand == "Brahma" and country == "Brazil":
                local_mix *= 1.8
            elif brand == "Bud Light" and country == "United States":
                local_mix *= 1.6
            elif brand in ("Stella Artois", "Hoegaarden") and country in ("Belgium", "United Kingdom", "China"):
                local_mix *= 1.5
            elif brand == "Corona" and country in ("Mexico", "United States", "China"):
                local_mix *= 1.5

            base_monthly_volume = 9000 * brand_mult * country_mult * local_mix / 12

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
                    elif channel == "Traditional Trade" and country in ("Brazil", "Mexico", "India"):
                        ch_share *= 1.3
                    elif channel == "BEES & E-commerce" and country in ("Brazil", "Mexico", "China"):
                        ch_share *= 1.4

                    noise = random.uniform(0.92, 1.08)
                    volume = round(total_volume_month * ch_share * noise, 1)
                    if volume <= 0:
                        continue

                    price = base_price * random.uniform(0.96, 1.04) * (1.03 ** years_elapsed)
                    if channel == "BEES & E-commerce":
                        price *= 0.98  # B2B efficiency discount
                    elif channel == "On-Premise":
                        price *= 1.75  # On-premise draft/pack premium

                    revenue = round(volume * price, 2)
                    market_share = round(max(0.5, min(48.0, 7 + 10 * brand_mult / country_mult + random.uniform(-1.0, 1.0) + 0.3 * years_elapsed)), 2)
                    distribution = round(max(25.0, min(99.0, 60 + 20 * brand_mult + random.uniform(-6, 6))), 1)
                    marketing_spend = round(revenue * random.uniform(0.04, 0.08), 2)
                    promo_spend = round(revenue * random.uniform(0.02, 0.05), 2)
                    gross_margin = round(max(30.0, min(68.0, 52 + random.uniform(-3.5, 3.5))), 1)

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
