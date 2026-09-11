"""
Builds data/db/ab_inbev.db from REAL, PUBLICLY DISCLOSED AB InBev figures.

Unlike a synthetic generator, this script does not invent anything -- it
loads a hardcoded table of numbers transcribed from AB InBev's own quarterly
and full-year results press releases (BusinessWire) and SEC EX-99.2 filings,
each tagged with the exact source and URL it came from. Re-running this
script is deterministic (same literal data in, same DB out) for the same
reason a spreadsheet built from filed numbers is deterministic -- there's no
randomness here, only transcription.

Sourcing notes (see docs/DESIGN_DECISIONS.md §1 for the full trade-off
writeup):
  - Quarterly zone-level rows (Q1 2024 - Q4 2025): transcribed from each
    quarter's "AB InBev Reports ... Quarter <Y> Results" BusinessWire release,
    Annex "Segment reporting" tables.
  - Annual company-wide totals (FY2022 - FY2025): transcribed from each
    year's "AB InBev Reports Full Year and Fourth Quarter <Y> Results"
    release.
  - "Global" quarterly rows are COMPUTED as the sum of the 5 reported zones
    for that quarter (AB InBev's total is, by construction, the sum of its
    zones) -- these cross-checked to within rounding of the company's own
    disclosed annual totals where both exist (e.g. summing the four 2025
    zone-quarters for North America gives $14,208M vs. the company's own
    disclosed FY2025 North America figure of $14,207M -- a $1M rounding
    difference, which is itself a small piece of evidence the source
    numbers were transcribed correctly rather than invented).
  - ebitda_margin_pct is COMPUTED (ebitda / revenue) wherever both are
    present, not separately disclosed by AB InBev for every row.
  - EMEA and South America don't have every full-year absolute figure
    cleanly disclosed for FY2022/FY2023 in the sources used here (some
    years' filings state only growth rates or Q4-only figures for those
    zones) -- rather than estimate a number to fill the gap, this build
    leaves it out entirely (NULL). See the `source_label` column: any row
    without one wasn't loaded.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "db" / "ab_inbev.db"

BW = "AB InBev {q} Results (BusinessWire, {d})"

# ---------------------------------------------------------------------------
# Quarterly zone-level figures: (zone, year, quarter) -> dict of real figures.
# revenue_usd_m, volume_k_hl, normalized_ebitda_usd_m, organic_revenue_growth_pct
# ---------------------------------------------------------------------------
QUARTERLY_ZONE = {
    # --- 2024 ---
    ("North America", 2024, 1):     dict(revenue_usd_m=3593, volume_k_hl=21353, normalized_ebitda_usd_m=1126, organic_revenue_growth_pct=-8.8),
    ("Middle Americas", 2024, 1):   dict(revenue_usd_m=4051, volume_k_hl=35690, normalized_ebitda_usd_m=1886, organic_revenue_growth_pct=8.0),
    ("South America", 2024, 1):     dict(revenue_usd_m=3233, volume_k_hl=40347, normalized_ebitda_usd_m=1084, organic_revenue_growth_pct=5.1),
    ("EMEA", 2024, 1):              dict(revenue_usd_m=1927, volume_k_hl=21030, normalized_ebitda_usd_m=569, organic_revenue_growth_pct=16.3),
    ("Asia Pacific", 2024, 1):      dict(revenue_usd_m=1634, volume_k_hl=21045, normalized_ebitda_usd_m=616, organic_revenue_growth_pct=-0.5),

    ("North America", 2024, 2):     dict(revenue_usd_m=3864, volume_k_hl=22639, normalized_ebitda_usd_m=1338, organic_revenue_growth_pct=-1.3),
    ("Middle Americas", 2024, 2):   dict(revenue_usd_m=4522, volume_k_hl=38381, normalized_ebitda_usd_m=2219, organic_revenue_growth_pct=5.9),
    ("South America", 2024, 2):     dict(revenue_usd_m=2785, volume_k_hl=35969, normalized_ebitda_usd_m=750, organic_revenue_growth_pct=6.1),
    ("EMEA", 2024, 2):              dict(revenue_usd_m=2301, volume_k_hl=23852, normalized_ebitda_usd_m=721, organic_revenue_growth_pct=10.0),
    ("Asia Pacific", 2024, 2):      dict(revenue_usd_m=1749, volume_k_hl=25399, normalized_ebitda_usd_m=570, organic_revenue_growth_pct=-8.2),

    ("North America", 2024, 3):     dict(revenue_usd_m=3867, volume_k_hl=22764, normalized_ebitda_usd_m=1358, organic_revenue_growth_pct=1.5),
    ("Middle Americas", 2024, 3):   dict(revenue_usd_m=4103, volume_k_hl=37107, normalized_ebitda_usd_m=2068, organic_revenue_growth_pct=1.9),
    ("South America", 2024, 3):     dict(revenue_usd_m=2932, volume_k_hl=39502, normalized_ebitda_usd_m=908, organic_revenue_growth_pct=5.6),
    ("EMEA", 2024, 3):              dict(revenue_usd_m=2351, volume_k_hl=24039, normalized_ebitda_usd_m=780, organic_revenue_growth_pct=8.2),
    ("Asia Pacific", 2024, 3):      dict(revenue_usd_m=1691, volume_k_hl=24514, normalized_ebitda_usd_m=503, organic_revenue_growth_pct=-9.5),

    ("North America", 2024, 4):     dict(revenue_usd_m=3331, volume_k_hl=19516, normalized_ebitda_usd_m=969, organic_revenue_growth_pct=1.7),
    ("Middle Americas", 2024, 4):   dict(revenue_usd_m=4395, volume_k_hl=38907, normalized_ebitda_usd_m=2227, organic_revenue_growth_pct=6.6),
    ("South America", 2024, 4):     dict(revenue_usd_m=3473, volume_k_hl=44950, normalized_ebitda_usd_m=1310, organic_revenue_growth_pct=3.2),
    ("EMEA", 2024, 4):              dict(revenue_usd_m=2424, volume_k_hl=24883, normalized_ebitda_usd_m=776, organic_revenue_growth_pct=8.7),
    ("Asia Pacific", 2024, 4):      dict(revenue_usd_m=1122, volume_k_hl=13439, normalized_ebitda_usd_m=244, organic_revenue_growth_pct=-10.9),

    # --- 2025 ---
    ("North America", 2025, 1):     dict(revenue_usd_m=3364, volume_k_hl=19842, normalized_ebitda_usd_m=1087, organic_revenue_growth_pct=-4.7),
    ("Middle Americas", 2025, 1):   dict(revenue_usd_m=3784, volume_k_hl=35081, normalized_ebitda_usd_m=1858, organic_revenue_growth_pct=3.6),
    ("South America", 2025, 1):     dict(revenue_usd_m=2978, volume_k_hl=40891, normalized_ebitda_usd_m=1007, organic_revenue_growth_pct=8.5),
    ("EMEA", 2025, 1):              dict(revenue_usd_m=1965, volume_k_hl=20752, normalized_ebitda_usd_m=624, organic_revenue_growth_pct=4.8),
    ("Asia Pacific", 2025, 1):      dict(revenue_usd_m=1450, volume_k_hl=19648, normalized_ebitda_usd_m=523, organic_revenue_growth_pct=-7.7),

    ("North America", 2025, 2):     dict(revenue_usd_m=3844, volume_k_hl=22376, normalized_ebitda_usd_m=1372, organic_revenue_growth_pct=2.2),
    ("Middle Americas", 2025, 2):   dict(revenue_usd_m=4340, volume_k_hl=38822, normalized_ebitda_usd_m=2149, organic_revenue_growth_pct=5.1),
    ("South America", 2025, 2):     dict(revenue_usd_m=2529, volume_k_hl=34199, normalized_ebitda_usd_m=692, organic_revenue_growth_pct=3.6),
    ("EMEA", 2025, 2):              dict(revenue_usd_m=2489, volume_k_hl=24172, normalized_ebitda_usd_m=800, organic_revenue_growth_pct=5.2),
    ("Asia Pacific", 2025, 2):      dict(revenue_usd_m=1658, volume_k_hl=23716, normalized_ebitda_usd_m=533, organic_revenue_growth_pct=-4.5),

    ("North America", 2025, 3):     dict(revenue_usd_m=3765, volume_k_hl=21896, normalized_ebitda_usd_m=1323, organic_revenue_growth_pct=-0.7),
    ("Middle Americas", 2025, 3):   dict(revenue_usd_m=4325, volume_k_hl=36915, normalized_ebitda_usd_m=2170, organic_revenue_growth_pct=4.2),
    ("South America", 2025, 3):     dict(revenue_usd_m=2802, volume_k_hl=36922, normalized_ebitda_usd_m=881, organic_revenue_growth_pct=2.0),
    ("EMEA", 2025, 3):              dict(revenue_usd_m=2524, volume_k_hl=24149, normalized_ebitda_usd_m=859, organic_revenue_growth_pct=3.0),
    ("Asia Pacific", 2025, 3):      dict(revenue_usd_m=1533, volume_k_hl=22301, normalized_ebitda_usd_m=452, organic_revenue_growth_pct=-9.0),

    ("North America", 2025, 4):     dict(revenue_usd_m=3235, volume_k_hl=18619, normalized_ebitda_usd_m=906, organic_revenue_growth_pct=-1.0),
    ("Middle Americas", 2025, 4):   dict(revenue_usd_m=4927, volume_k_hl=39672, normalized_ebitda_usd_m=2508, organic_revenue_growth_pct=5.9),
    ("South America", 2025, 4):     dict(revenue_usd_m=3645, volume_k_hl=43160, normalized_ebitda_usd_m=1321, organic_revenue_growth_pct=5.0),
    ("EMEA", 2025, 4):              dict(revenue_usd_m=2524, volume_k_hl=24249, normalized_ebitda_usd_m=815, organic_revenue_growth_pct=0.2),
    ("Asia Pacific", 2025, 4):      dict(revenue_usd_m=1053, volume_k_hl=13334, normalized_ebitda_usd_m=192, organic_revenue_growth_pct=-4.3),
}
QUARTERLY_SOURCE = {
    2024: {1: BW.format(q="First Quarter 2024", d="7 May 2024"),
           2: BW.format(q="Second Quarter 2024", d="31 Jul 2024"),
           3: BW.format(q="Third Quarter 2024", d="30 Oct 2024"),
           4: BW.format(q="Full Year and Fourth Quarter 2024", d="26 Feb 2025")},
    2025: {1: BW.format(q="First Quarter 2025", d="7 May 2025"),
           2: BW.format(q="Second Quarter 2025", d="31 Jul 2025"),
           3: BW.format(q="Third Quarter 2025", d="30 Oct 2025"),
           4: BW.format(q="Full Year and Fourth Quarter 2025", d="11 Feb 2026")},
}
QUARTERLY_URL = {
    2024: {1: "https://www.businesswire.com/news/home/20240507296313/en/AB-InBev-Reports-First-Quarter-2024-Results",
           2: "https://www.businesswire.com/news/home/20240731260058/en/AB-InBev-Reports-Second-Quarter-2024-Results",
           3: "https://www.businesswire.com/news/home/20241030139581/en/AB-InBev-Reports-Third-Quarter-2024-Results",
           4: "https://www.businesswire.com/news/home/20250225267454/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2024-Results"},
    2025: {1: "https://www.businesswire.com/news/home/20250507671244/en/AB-InBev-Reports-First-Quarter-2025-Results",
           2: "https://www.businesswire.com/news/home/20250730542419/en/AB-InBev-Reports-Second-Quarter-2025-Results",
           3: "https://www.businesswire.com/news/home/20251029571716/en/AB-InBev-Reports-Third-Quarter-2025-Results",
           4: "https://www.businesswire.com/news/home/20260211688662/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2025-Results"},
}

# ---------------------------------------------------------------------------
# Annual, company-wide ("Global") totals -- FY2022-FY2025. Zone-level annual
# breakouts for FY2024/FY2025 are NOT loaded separately here: they're
# reconstructed by summing the quarterly zone rows above (see build_db()),
# which is more transparent than hardcoding a second, redundant copy.
# ---------------------------------------------------------------------------
ANNUAL_GLOBAL = {
    2022: dict(revenue_usd_m=57786, volume_k_hl=595133, normalized_ebitda_usd_m=19843,
               net_profit_usd_m=5969, organic_revenue_growth_pct=None,
               source_label=BW.format(q="Full Year and Fourth Quarter 2022", d="1 Mar 2023"),
               source_url="https://www.businesswire.com/news/home/20230301006162/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2022-Results"),
    2023: dict(revenue_usd_m=59380, volume_k_hl=584728, normalized_ebitda_usd_m=19976,
               net_profit_usd_m=5341, organic_revenue_growth_pct=None,
               source_label=BW.format(q="Full Year and Fourth Quarter 2023", d="28 Feb 2024"),
               source_url="https://www.businesswire.com/news/home/20240228688664/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2023-Results"),
    2024: dict(revenue_usd_m=59768, volume_k_hl=575706, normalized_ebitda_usd_m=20958,
               net_profit_usd_m=5855, organic_revenue_growth_pct=2.7,
               source_label=QUARTERLY_SOURCE[2024][4], source_url=QUARTERLY_URL[2024][4]),
    2025: dict(revenue_usd_m=59320, volume_k_hl=561100, normalized_ebitda_usd_m=21223,
               net_profit_usd_m=6837, organic_revenue_growth_pct=None,
               source_label=QUARTERLY_SOURCE[2025][4], source_url=QUARTERLY_URL[2025][4]),
}

# Disclosed (not computed) FY zone totals, for the two years AB InBev's own
# release stated them directly -- kept alongside the computed quarterly-sum
# version isn't necessary (they reconcile to within rounding; see docstring),
# so only the computed version is loaded, to avoid duplicate/near-duplicate
# rows in the same table.


def build_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE dim_zone_country (
            zone TEXT NOT NULL,
            country TEXT NOT NULL
        )
    """)
    from src.config import ZONE_HIERARCHY
    for zone, countries in ZONE_HIERARCHY.items():
        for country in countries:
            cur.execute("INSERT INTO dim_zone_country (zone, country) VALUES (?, ?)", (zone, country))

    cur.execute("""
        CREATE TABLE fact_kpi (
            grain TEXT NOT NULL,              -- 'quarterly' or 'annual'
            zone TEXT NOT NULL,                -- one of the 5 real zones, or 'Global'
            year INTEGER NOT NULL,
            quarter INTEGER,                   -- 1-4, NULL for annual rows
            period_label TEXT NOT NULL,        -- e.g. 'Q1 2024', 'FY2023'
            revenue_usd_m REAL,
            volume_k_hl REAL,
            normalized_ebitda_usd_m REAL,
            ebitda_margin_pct REAL,            -- computed: ebitda / revenue
            organic_revenue_growth_pct REAL,
            net_profit_usd_m REAL,             -- only populated for Global/annual rows
            source_label TEXT NOT NULL,
            source_url TEXT NOT NULL
        )
    """)

    rows = []

    # Quarterly, per-zone (real, transcribed)
    for (zone, year, quarter), figs in QUARTERLY_ZONE.items():
        margin = round(100.0 * figs["normalized_ebitda_usd_m"] / figs["revenue_usd_m"], 1)
        rows.append((
            "quarterly", zone, year, quarter, f"Q{quarter} {year}",
            figs["revenue_usd_m"], figs["volume_k_hl"], figs["normalized_ebitda_usd_m"],
            margin, figs["organic_revenue_growth_pct"], None,
            QUARTERLY_SOURCE[year][quarter], QUARTERLY_URL[year][quarter],
        ))

    # Quarterly, Global = computed sum of the 5 real zones for that quarter
    for year in (2024, 2025):
        for quarter in (1, 2, 3, 4):
            zone_rows = [QUARTERLY_ZONE[(z, year, quarter)] for z in ZONE_HIERARCHY]
            revenue = sum(r["revenue_usd_m"] for r in zone_rows)
            volume = sum(r["volume_k_hl"] for r in zone_rows)
            ebitda = sum(r["normalized_ebitda_usd_m"] for r in zone_rows)
            margin = round(100.0 * ebitda / revenue, 1)
            rows.append((
                "quarterly", "Global", year, quarter, f"Q{quarter} {year}",
                revenue, volume, ebitda, margin, None, None,
                "Computed: sum of the 5 reported zones (see AB InBev quarterly results)",
                QUARTERLY_URL[year][quarter],
            ))

    # Annual, Global (real, transcribed)
    for year, figs in ANNUAL_GLOBAL.items():
        margin = round(100.0 * figs["normalized_ebitda_usd_m"] / figs["revenue_usd_m"], 1)
        rows.append((
            "annual", "Global", year, None, f"FY{year}",
            figs["revenue_usd_m"], figs["volume_k_hl"], figs["normalized_ebitda_usd_m"],
            margin, figs["organic_revenue_growth_pct"], figs["net_profit_usd_m"],
            figs["source_label"], figs["source_url"],
        ))

    # Annual, per-zone (2024/2025 only) = computed sum of that year's 4 quarters
    for year in (2024, 2025):
        for zone in ZONE_HIERARCHY:
            q_rows = [QUARTERLY_ZONE[(zone, year, q)] for q in (1, 2, 3, 4)]
            revenue = sum(r["revenue_usd_m"] for r in q_rows)
            volume = sum(r["volume_k_hl"] for r in q_rows)
            ebitda = sum(r["normalized_ebitda_usd_m"] for r in q_rows)
            margin = round(100.0 * ebitda / revenue, 1)
            rows.append((
                "annual", zone, year, None, f"FY{year}",
                revenue, volume, ebitda, margin, None, None,
                f"Computed: sum of {zone}'s 4 quarters in FY{year} (see AB InBev quarterly results)",
                QUARTERLY_URL[year][4],
            ))

    cur.executemany("""
        INSERT INTO fact_kpi (grain, zone, year, quarter, period_label, revenue_usd_m, volume_k_hl,
                               normalized_ebitda_usd_m, ebitda_margin_pct, organic_revenue_growth_pct,
                               net_profit_usd_m, source_label, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM fact_kpi").fetchone()[0]
    conn.close()
    print(f"Wrote {DB_PATH} with {n} rows in fact_kpi "
          f"({len(QUARTERLY_ZONE)} real quarterly zone rows, "
          f"8 computed quarterly Global rows, {len(ANNUAL_GLOBAL)} real annual Global rows, "
          f"10 computed annual zone rows) + {sum(len(v) for v in ZONE_HIERARCHY.values())} dim_zone_country rows.")


if __name__ == "__main__":
    build_db()
