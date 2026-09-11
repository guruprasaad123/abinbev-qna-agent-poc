"""
Generate the synthetic unstructured document corpus for Meridian Brewing Group.

Design (see docs/DESIGN_DECISIONS.md):
  - Documents are organized into 10 "storylines" (e.g. a non-alcoholic beer
    launch, a pricing decision, a water-stewardship initiative). Each
    storyline produces 3-4 documents of DIFFERENT types (press release,
    earnings commentary, market research note, sustainability update,
    competitor intel, strategy memo) that share the SAME brand/country/
    category entities. This is what creates deliberate overlap in
    theme+entities across documents, and across the structured/unstructured
    boundary -- required by the assignment.
  - Several documents embed numbers pulled LIVE from the structured SQLite
    DB (actual YoY revenue growth, market share, ACV) so an agent can
    cross-validate a qualitative claim ("strong growth in Germany") against
    the quantitative fact table -- this is what the answer-validation /
    hybrid-retrieval capabilities actually exercise.
  - Some documents are purely qualitative (no numbers) to exercise semantic
    retrieval on its own. Some reference FICTIONAL COMPETITORS that have no
    row in the structured DB at all -- this is deliberate: it's what lets us
    demonstrate "graceful handling of unsupported/unavailable requests" when
    a user asks for a competitor's exact revenue.
  - Themes mirror what a real global brewer actually reports on: on-premise
    recovery, premiumization, the "Beyond Beer" (non-alcoholic/hard seltzer)
    growth segment, water stewardship and packaging sustainability, input-
    cost-driven pricing actions, and sponsorship-led marketing campaigns.
  - Each doc gets metadata (doc_id, title, date, source_type, tags, brands,
    countries) written into data/unstructured/manifest.json so the retrieval
    tool can filter by metadata/tags/recency without re-parsing every file.
"""
import json
import sqlite3
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import COMPANY_NAME

ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "data" / "unstructured"
DB_PATH = ROOT / "data" / "db" / "meridian_brewing.db"

FICTIONAL_COMPETITORS = ["Highland Brewing Collective", "Continental Lager Co.", "Pacific Rim Brewers"]


def q(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def yoy_growth(cur, brand, country, year):
    cur.execute("""SELECT SUM(net_revenue_usd) FROM fact_monthly_kpi
                   WHERE brand=? AND country=? AND year=?""", (brand, country, year))
    cur_rev = cur.fetchone()[0] or 0
    cur.execute("""SELECT SUM(net_revenue_usd) FROM fact_monthly_kpi
                   WHERE brand=? AND country=? AND year=?""", (brand, country, year - 1))
    prev_rev = cur.fetchone()[0] or 0
    if prev_rev == 0:
        return None, cur_rev, prev_rev
    return round((cur_rev / prev_rev - 1) * 100, 1), cur_rev, prev_rev


def latest_acv(cur, brand, country):
    cur.execute("""SELECT distribution_acv_pct FROM fact_monthly_kpi
                   WHERE brand=? AND country=? ORDER BY year DESC, month DESC LIMIT 1""", (brand, country))
    r = cur.fetchone()
    return r[0] if r else None


def latest_share(cur, brand, country):
    cur.execute("""SELECT market_share_pct FROM fact_monthly_kpi
                   WHERE brand=? AND country=? ORDER BY year DESC, month DESC LIMIT 1""", (brand, country))
    r = cur.fetchone()
    return r[0] if r else None


def doc(doc_id, title, dt, source_type, tags, brands, countries, body):
    return {
        "doc_id": doc_id, "title": title, "date": dt.isoformat(), "source_type": source_type,
        "tags": tags, "brands": brands, "countries": countries, "body": body.strip() + "\n",
    }


def build():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    docs = []
    n = 0

    def nid():
        nonlocal n
        n += 1
        return f"DOC-{n:03d}"

    # --- Storyline 1: Clearwater Zero (non-alcoholic beer) launch, Germany + UK ---
    growth_de, cur_de, _ = yoy_growth(cur, "Clearwater Zero", "Germany", 2025)
    docs.append(doc(nid(), "Meridian Launches Clearwater Zero in Germany and the UK", date(2025, 3, 10),
        "press_release", ["product_launch", "non_alcoholic", "beyond_beer"], ["Clearwater Zero"], ["Germany", "United Kingdom"],
        f"""
{COMPANY_NAME} today announced the European launch of Clearwater Zero, a
non-alcoholic beer, in Germany and the United Kingdom. The launch responds to
accelerating consumer demand for no/low-alcohol options across Western Europe.
Clearwater Zero will be available in 500ml bottles through Modern Trade and
E-commerce channels from April 2025, with Traditional Trade rollout to follow
in H2. "Consumers increasingly want the beer occasion without the alcohol,"
said the Clearwater brand lead. Initial distribution targets 60% ACV within
the first two quarters of launch.
"""))
    docs.append(doc(nid(), "Q1 2025 Earnings Commentary: Beyond Beer Momentum in Europe", date(2025, 5, 2),
        "earnings_commentary", ["earnings", "non_alcoholic", "beyond_beer", "europe"], ["Clearwater Zero"], ["Germany", "United Kingdom"],
        f"""
Clearwater Zero net revenue in Germany grew {growth_de if growth_de else 'double-digit'}% year-over-year in the
twelve months to 2025, which management attributes primarily to the March 2025
launch and continued strength in E-commerce. Distribution (ACV) in Germany
reached {latest_acv(cur,'Clearwater Zero','Germany')}% by the most recent reporting month. Management noted the
Beyond Beer segment continues to grow faster than the overall portfolio.
"""))
    docs.append(doc(nid(), "Market Research Note: Non-Alcoholic Beer Positioning in Western Europe", date(2025, 6, 15),
        "market_research", ["non_alcoholic", "beyond_beer", "europe", "consumer_trend"], ["Clearwater Zero"],
        ["Germany", "United Kingdom"],
        """
Independent market research indicates 31% of German and UK beer drinkers
surveyed actively moderated their alcohol intake in 2025, up from 22% two
years prior. Non-alcoholic beer is now the fastest-growing sub-segment of the
beer category in both markets, outpacing low-alcohol variants. Private-label
entrants remain limited, leaving room for branded players with early-mover
distribution advantages.
"""))
    docs.append(doc(nid(), "Sustainability Update: Recyclable Packaging for Clearwater Zero", date(2025, 4, 22),
        "sustainability", ["packaging", "sustainability", "non_alcoholic"], ["Clearwater Zero"], ["Germany", "United Kingdom"],
        f"""
As part of {COMPANY_NAME}'s 2030 packaging commitments, all Clearwater Zero
bottles launched in Germany and the UK use 100% recycled glass and packaging
board. This is ahead of the group-wide target of 70% recycled packaging
across the Beyond Beer portfolio by 2027.
"""))

    # --- Storyline 2: Northstar Lager On-Premise recovery in USA ---
    growth_us, cur_us, _ = yoy_growth(cur, "Northstar Lager", "United States", 2025)
    docs.append(doc(nid(), "Q3 2025 Earnings Commentary: Northstar Lager On-Premise Recovery", date(2025, 11, 4),
        "earnings_commentary", ["earnings", "beer", "on_premise", "north_america"], ["Northstar Lager"], ["United States"],
        f"""
Northstar Lager On-Premise volumes in the United States continued to recover
through Q3 2025 as bar and restaurant traffic normalized. Full-year net
revenue in the United States grew {growth_us if growth_us else 'high-single-digit'}% year-over-year. Management called
out On-Premise as the primary growth channel, partially offset by softer
Traditional Trade performance in the Midwest.
"""))
    docs.append(doc(nid(), "Market Research Note: Premiumization Trends in US Beer", date(2025, 9, 1),
        "market_research", ["beer", "premiumization", "north_america", "consumer_trend"], ["Northstar Lager", "Ironclad Stout"],
        ["United States"],
        """
Premiumization continues in the U.S. beer category: consumers are drinking
less volume overall but trading up within occasions, favoring international
premium and craft-style positioning. On-Premise remains the highest-margin
channel for premium beer and is recovering faster than Traditional Trade in
most metro markets.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Highland Brewing Collective On-Premise Push", date(2025, 10, 12),
        "competitor_intel", ["beer", "on_premise", "competitor", "north_america"], ["Northstar Lager"], ["United States"],
        f"""
Highland Brewing Collective has announced an expanded On-Premise sponsorship
program targeting major U.S. metro markets for 2026, including tap placement
incentives at independent bars. This is viewed as a direct competitive
response to premium lager share gains in the On-Premise channel. {COMPANY_NAME}
does not hold detailed third-party sales data on Highland Brewing Collective
and monitors this via public announcements and distributor feedback only.
"""))

    # --- Storyline 3: Havenbrook Seltzer summer campaign in Australia ---
    growth_au, _, _ = yoy_growth(cur, "Havenbrook Seltzer", "Australia", 2025)
    docs.append(doc(nid(), "Meridian Launches 'Brighter Days' Havenbrook Seltzer Campaign in Australia", date(2025, 10, 20),
        "press_release", ["product_launch", "campaign", "hard_seltzer", "apac"], ["Havenbrook Seltzer"], ["Australia"],
        """
Meridian's Havenbrook Seltzer brand launched its 'Brighter Days' summer
campaign across Australia ahead of the peak summer season, spanning Modern
Trade, E-commerce and On-Premise. The campaign features a national outdoor
and digital media push and festival sponsorships, Havenbrook's largest
marketing investment in Australia to date.
"""))
    docs.append(doc(nid(), "Q4 2025 Earnings Commentary: Havenbrook Seltzer Australia Summer Performance", date(2026, 2, 3),
        "earnings_commentary", ["earnings", "hard_seltzer", "apac", "seasonality"], ["Havenbrook Seltzer"], ["Australia"],
        f"""
Havenbrook Seltzer Australia delivered {growth_au if growth_au else 'strong'}% net revenue growth year-over-year in
2025, with the summer period the single largest contributor following the
'Brighter Days' campaign. On-Premise and E-commerce grew fastest, reflecting
the brand's social-occasion positioning.
"""))
    docs.append(doc(nid(), "Market Research Note: Hard Seltzer Trends in APAC", date(2025, 12, 1),
        "market_research", ["hard_seltzer", "apac", "seasonality", "consumer_trend"], ["Havenbrook Seltzer"],
        ["Australia", "India"],
        """
Hard seltzer occasions in Australia show pronounced summer seasonality tied
to outdoor and social occasions, with variety packs outperforming single-
flavor packs by a wide margin during peak season. India remains a nascent
hard seltzer market with limited category development to date.
"""))

    # --- Storyline 4: Copperline Amber Ale UK expansion ---
    docs.append(doc(nid(), "Copperline Amber Ale Expands Distribution in the United Kingdom", date(2024, 6, 18),
        "press_release", ["distribution", "craft", "europe"], ["Copperline Amber Ale"], ["United Kingdom"],
        f"""
Copperline Amber Ale announced an expanded distribution agreement in the
United Kingdom, targeting an increase in all-commodity-volume (ACV)
distribution across independent and Modern Trade retailers through 2025.
Current UK ACV stands at {latest_acv(cur,'Copperline Amber Ale','United Kingdom')}%.
"""))
    docs.append(doc(nid(), "Internal Strategy Memo: Copperline Amber Ale UK Channel Mix", date(2024, 8, 5),
        "strategy_memo", ["strategy", "craft", "europe", "channel"], ["Copperline Amber Ale"], ["United Kingdom"],
        """
Recommendation: prioritize independent off-trade and Modern Trade distribution
gains over On-Premise expansion in the UK for Copperline Amber Ale through
2025, given the brand's still-developing awareness relative to Ironclad
Stout. On-Premise investment should follow, not lead, off-trade household
penetration.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Craft Ale Entrants in the UK", date(2025, 1, 15),
        "competitor_intel", ["craft", "competitor", "europe"], ["Copperline Amber Ale"], ["United Kingdom"],
        """
Several independent craft breweries have entered the UK amber ale category
at premium price points over the past year. While individually small, their
combined shelf presence in independent retail has increased. No reliable
third-party volume data is available for these entrants; Meridian tracks
this qualitatively via distributor and retailer conversations.
"""))

    # --- Storyline 5: Ironclad Stout water stewardship ---
    docs.append(doc(nid(), "Ironclad Stout Brewery Commits to 20% Water Reduction by 2027", date(2024, 3, 1),
        "sustainability", ["sustainability", "water", "craft"], ["Ironclad Stout"], [],
        f"""
{COMPANY_NAME}'s Ironclad Stout brewing sites announced a commitment to
reduce water used per hectoliter brewed by 20% by 2027, from a 2023 baseline,
through process efficiency and water recycling investments. The commitment
covers all Ironclad Stout production sites globally and will be independently
audited annually.
"""))
    docs.append(doc(nid(), "Market Research Note: Water Stewardship and Beer Purchase Intent", date(2024, 9, 10),
        "market_research", ["craft", "sustainability", "consumer_trend"], ["Ironclad Stout", "Copperline Amber Ale"], [],
        """
Surveyed craft beer drinkers across Meridian's core markets rank "responsible
water use" among the top three purchase drivers for craft/specialty beer,
though taste and price remain more influential overall. On-pack sustainability
certification has a measurable but modest effect on trial rate.
"""))
    docs.append(doc(nid(), "Press Release: Ironclad Stout Water Efficiency Progress Update", date(2025, 7, 8),
        "press_release", ["sustainability", "water", "craft"], ["Ironclad Stout"], [],
        """
Ironclad Stout reports it has reached a 13% reduction in water used per
hectoliter brewed against its 2023 baseline, ahead of its internal interim
milestone, and reaffirms its 2027 target of 20%.
"""))

    # --- Storyline 6: Kestrel Pilsner e-commerce push, South America ---
    growth_br, _, _ = yoy_growth(cur, "Kestrel Pilsner", "Brazil", 2025)
    docs.append(doc(nid(), "Internal Strategy Memo: Kestrel Pilsner South America E-commerce Acceleration", date(2025, 2, 20),
        "strategy_memo", ["strategy", "beer", "south_america", "ecommerce"], ["Kestrel Pilsner"], ["Brazil", "Mexico"],
        """
Recommendation: shift incremental FY2025 marketing investment for Kestrel
Pilsner in Brazil and Mexico toward E-commerce-specific media and retail
media placements, given E-commerce's outsized growth rate off a small base
in both markets relative to Modern and Traditional Trade.
"""))
    docs.append(doc(nid(), "Q4 2025 Earnings Commentary: Kestrel Pilsner South America", date(2026, 2, 3),
        "earnings_commentary", ["earnings", "beer", "south_america", "ecommerce"], ["Kestrel Pilsner"], ["Brazil", "Mexico"],
        f"""
Kestrel Pilsner net revenue in Brazil grew {growth_br if growth_br else 'strongly'}% year-over-year in 2025, with
E-commerce the fastest-growing channel following the strategic shift toward
digital-first marketing investment agreed in February 2025.
"""))
    docs.append(doc(nid(), "Market Research Note: E-commerce Grocery Growth in South America", date(2025, 5, 19),
        "market_research", ["south_america", "ecommerce", "consumer_trend"], ["Kestrel Pilsner"], ["Brazil", "Mexico"],
        """
Online grocery and alcohol-delivery penetration in Brazil and Mexico remains
below 10% of total beverage retail value but is growing faster than any other
channel, driven by quick-commerce delivery apps. Beer over-indexes in online
grocery baskets relative to its offline channel share in both markets.
"""))

    # --- Storyline 7: Frostpeak Light pricing action ---
    docs.append(doc(nid(), "Internal Strategy Memo: Frostpeak Light Pricing Action", date(2024, 11, 12),
        "strategy_memo", ["strategy", "pricing", "mainstream_lager"], ["Frostpeak Light"], [],
        """
Recommendation: implement a low-single-digit list price increase on Frostpeak
Light core SKUs in early 2025 to offset sustained input cost inflation
(barley, aluminum can stock), while holding promotional depth roughly flat
to protect volume and shelf presence.
"""))
    docs.append(doc(nid(), "Q1 2025 Earnings Commentary: Frostpeak Light Margin Recovery", date(2025, 5, 2),
        "earnings_commentary", ["earnings", "pricing", "mainstream_lager", "margin"], ["Frostpeak Light"], [],
        """
Frostpeak Light gross margin improved year-over-year in Q1 2025 following the
pricing action taken in response to barley and aluminum cost inflation.
Volume elasticity was within modeled expectations; management does not
currently plan further list price increases in the near term.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Continental Lager Co. Pricing Response", date(2025, 6, 2),
        "competitor_intel", ["mainstream_lager", "competitor", "pricing"], ["Frostpeak Light"], [],
        """
Continental Lager Co. appears to have followed with comparable list price
increases across its core range shortly after Frostpeak Light's pricing
action, based on retailer shelf-price checks. No official announcement was
made by Continental Lager Co.
"""))

    # --- Storyline 8: Harborlight Gold Australia market entry ---
    docs.append(doc(nid(), "Meridian Enters the Australian Market with Harborlight Gold", date(2023, 9, 5),
        "press_release", ["market_entry", "mainstream_lager", "apac"], ["Harborlight Gold"], ["Australia"],
        """
Meridian announced the entry of its Harborlight Gold mainstream lager into
Australia, its first Oceania mainstream-lager launch, distributed initially
through Modern Trade retailers in Sydney with national rollout planned over
18 months.
"""))
    docs.append(doc(nid(), "Market Research Note: Mainstream Lager Competitive Dynamics in Australia", date(2024, 2, 14),
        "market_research", ["mainstream_lager", "apac", "consumer_trend"], ["Harborlight Gold"], ["Australia"],
        """
The Australian mainstream lager segment is mature and consolidated, with
new entrants typically competing on price and distribution rather than
premium positioning. Shelf space in Modern Trade for new lager entrants has
expanded modestly over the past two years.
"""))
    docs.append(doc(nid(), "Q4 2024 Earnings Commentary: Harborlight Gold Australia One-Year Update", date(2025, 2, 4),
        "earnings_commentary", ["earnings", "mainstream_lager", "apac"], ["Harborlight Gold"], ["Australia"],
        f"""
Harborlight Gold's first full year in Australia closed with distribution
(ACV) of {latest_acv(cur,'Harborlight Gold','Australia')}% in Modern Trade and market share of {latest_share(cur,'Harborlight Gold','Australia')}%,
tracking ahead of the original three-year market-entry plan.
"""))

    # --- Storyline 9: Company-wide annual highlights ---
    docs.append(doc(nid(), f"{COMPANY_NAME} FY2025 Annual Highlights", date(2026, 2, 20),
        "earnings_commentary", ["earnings", "company_wide", "annual"], [], [],
        """
FY2025 was a year of continued premiumization and On-Premise channel recovery
across the Premium & Above portfolio, alongside accelerating growth in the
Beyond Beer segment (Clearwater Zero's European launch, Havenbrook Seltzer's
Australian summer campaign). Mainstream Lager growth was more modest, with
Frostpeak Light's pricing action supporting margin recovery. Sustainability
commitments across packaging (Clearwater Zero) and water stewardship
(Ironclad Stout) progressed ahead of interim milestones.
"""))
    docs.append(doc(nid(), "Meridian Brewing Group Investor FAQ: Data and Reporting Scope", date(2026, 1, 10),
        "metadata_note", ["reporting", "company_wide", "scope"], [], [],
        f"""
{COMPANY_NAME} reports net revenue, volume (hectoliters), market share,
average selling price, distribution (ACV), marketing spend, promotion spend
and gross margin, at brand x country x channel x month grain, for its eight
core brands across eight countries. Data is available from January 2023
through the most recently closed month. Competitor performance figures are
not part of Meridian's internal reporting scope; any competitor references
in company materials are qualitative and sourced from public information only.
"""))

    # --- Storyline 10: generic competitive landscape overview ---
    docs.append(doc(nid(), "Competitive Landscape Overview: Global Brewing Industry", date(2025, 8, 1),
        "competitor_intel", ["competitor", "market_overview"], [], [],
        f"""
Meridian's principal named competitors referenced in internal materials
include {', '.join(FICTIONAL_COMPETITORS)}. Meridian does not maintain
structured sales data for any competitor; all competitor commentary in this
document set is qualitative and directional, drawn from public announcements,
retailer shelf checks, and market research panels.
"""))

    manifest = {"company": COMPANY_NAME, "generated": date.today().isoformat(), "documents": []}
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in DOC_DIR.glob("DOC-*.md"):
        old_file.unlink()
    for d in docs:
        fname = f"{d['doc_id']}.md"
        text = f"# {d['title']}\n\n*{d['date']} — {d['source_type'].replace('_',' ').title()}*\n\n{d['body']}"
        (DOC_DIR / fname).write_text(text, encoding="utf-8")
        manifest["documents"].append({k: d[k] for k in ("doc_id", "title", "date", "source_type", "tags", "brands", "countries")} | {"file": fname})

    (DOC_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(docs)} documents -> {DOC_DIR}")
    conn.close()


if __name__ == "__main__":
    build()
