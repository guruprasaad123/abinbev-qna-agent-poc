"""
Generate the synthetic unstructured document corpus for Solara FMCG Group.

Design (see docs/DESIGN_DECISIONS.md):
  - Documents are organized into ~10 "storylines" (e.g. a product launch, a
    pricing decision, a sustainability initiative). Each storyline produces
    3-4 documents of DIFFERENT types (press release, earnings commentary,
    market research note, sustainability update, competitor intel, strategy
    memo) that share the SAME brand/country/category entities. This is what
    creates deliberate overlap in theme+entities across documents, and across
    the structured/unstructured boundary -- required by the assignment.
  - Several documents embed numbers pulled LIVE from the structured SQLite DB
    (actual YoY revenue growth, market share, ACV) so an agent can cross-
    validate a qualitative claim ("strong growth in Germany") against the
    quantitative fact table -- this is what the answer-validation /
    hybrid-retrieval capabilities actually exercise.
  - Some documents are purely qualitative (no numbers) to exercise semantic
    retrieval on its own. Some reference FICTIONAL COMPETITORS that have no
    row in the structured DB at all -- this is deliberate: it's what lets us
    demonstrate "graceful handling of unsupported/unavailable requests" when
    a user asks for a competitor's exact revenue.
  - Each doc gets YAML-ish frontmatter (doc_id, title, date, source_type,
    tags, brands, countries) written into data/unstructured/manifest.json so
    the retrieval tool can filter by metadata/tags/recency without re-parsing
    every file.
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
DB_PATH = ROOT / "data" / "db" / "solara_fmcg.db"

FICTIONAL_COMPETITORS = ["Northern Lager Co.", "Blue Ridge Snacks", "Meridian Beverages", "Alpine Confectionery"]


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

    # --- Storyline 1: Vivo Splash Zero launch (Non-Alcoholic, Germany + UK) ---
    growth_de, cur_de, _ = yoy_growth(cur, "Vivo Splash", "Germany", 2025)
    docs.append(doc(nid(), "Solara Launches Vivo Splash Zero in Germany and the UK", date(2025, 3, 10),
        "press_release", ["product_launch", "non_alcoholic", "sugar_free"], ["Vivo Splash"], ["Germany", "United Kingdom"],
        f"""
{COMPANY_NAME} today announced the European launch of Vivo Splash Zero, a zero-sugar
sparkling water line, in Germany and the United Kingdom. The launch responds to
accelerating consumer demand for no/low-sugar refreshment across Western Europe.
Vivo Splash Zero will be available in 500ml bottles through Modern Trade and
E-commerce channels from April 2025, with Traditional Trade rollout to follow in H2.
"Consumers are actively trading down on sugar without trading down on taste," said
the Vivo Splash European brand lead. Initial distribution targets 60% ACV within
the first two quarters of launch.
"""))
    docs.append(doc(nid(), "Q1 2025 Earnings Commentary: Non-Alcoholic Momentum in Europe", date(2025, 5, 2),
        "earnings_commentary", ["earnings", "non_alcoholic", "europe"], ["Vivo Splash"], ["Germany", "United Kingdom"],
        f"""
Vivo Splash net revenue in Germany grew {growth_de if growth_de else 'double-digit'}% year-over-year in the
twelve months to 2025, which management attributes primarily to the March 2025
launch of Vivo Splash Zero and continued strength in E-commerce. Distribution
(ACV) in Germany reached {latest_acv(cur,'Vivo Splash','Germany')}% by the most recent reporting month.
Management noted early cannibalization of the core Vivo Splash line by Zero was
lower than modeled, supporting an incremental rather than substitutive growth thesis.
"""))
    docs.append(doc(nid(), "Market Research Note: Sugar-Free Positioning in Western Europe", date(2025, 6, 15),
        "market_research", ["non_alcoholic", "sugar_free", "europe", "consumer_trend"], ["Vivo Splash", "PureSpring"],
        ["Germany", "United Kingdom"],
        """
Independent market research indicates 34% of German and UK consumers surveyed
actively sought sugar-free alternatives in the sparkling water category in 2025,
up from 26% two years prior. Zero-sugar sparkling water is now the fastest-growing
sub-segment of the non-alcoholic category in both markets, outpacing flavored
still water. Private-label entrants remain limited, leaving room for branded
players with early-mover distribution advantages.
"""))
    docs.append(doc(nid(), "Sustainability Update: Recyclable Packaging for Vivo Splash Zero", date(2025, 4, 22),
        "sustainability", ["packaging", "sustainability", "non_alcoholic"], ["Vivo Splash"], ["Germany", "United Kingdom"],
        f"""
As part of {COMPANY_NAME}'s 2030 packaging commitments, all Vivo Splash Zero bottles
launched in Germany and the UK use 100% recycled PET (rPET). This is ahead of the
group-wide target of 70% rPET across the Non-Alcoholic portfolio by 2027.
"""))

    # --- Storyline 2: Glacier Peak On-Premise recovery in USA ---
    growth_us, cur_us, _ = yoy_growth(cur, "Glacier Peak", "United States", 2025)
    docs.append(doc(nid(), "Q3 2025 Earnings Commentary: Glacier Peak On-Premise Recovery", date(2025, 11, 4),
        "earnings_commentary", ["earnings", "beer", "on_premise", "north_america"], ["Glacier Peak"], ["United States"],
        f"""
Glacier Peak On-Premise volumes in the United States continued to recover through
Q3 2025 as bar and restaurant traffic normalized. Full-year net revenue in the
United States grew {growth_us if growth_us else 'high-single-digit'}% year-over-year. Management called out
On-Premise as the primary growth channel, partially offset by softer Traditional
Trade performance in the Midwest.
"""))
    docs.append(doc(nid(), "Market Research Note: Craft and Premium Beer Trends, USA", date(2025, 9, 1),
        "market_research", ["beer", "premiumization", "north_america", "consumer_trend"], ["Glacier Peak", "Ironclad Stout"],
        ["United States"],
        """
Premiumization continues in the U.S. beer category: consumers are drinking less
volume overall but trading up within occasions, favoring craft-style and premium
lager positioning. On-Premise remains the highest-margin channel for premium beer
and is recovering faster than Traditional Trade in most metro markets.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Northern Lager Co. On-Premise Push", date(2025, 10, 12),
        "competitor_intel", ["beer", "on_premise", "competitor", "north_america"], ["Glacier Peak"], ["United States"],
        """
Northern Lager Co. has announced an expanded On-Premise sponsorship program
targeting major U.S. metro markets for 2026, including tap placement incentives
at independent bars. This is viewed as a direct competitive response to premium
lager share gains in the On-Premise channel. Solara does not hold detailed
third-party sales data on Northern Lager Co. and monitors this via public
announcements and distributor feedback only.
"""))

    # --- Storyline 3: CrunchWave Q4 holiday campaign India ---
    growth_in, _, _ = yoy_growth(cur, "CrunchWave", "India", 2025)
    docs.append(doc(nid(), "Solara Launches 'Share the Crunch' Campaign in India", date(2025, 10, 20),
        "press_release", ["product_launch", "campaign", "salty_snacks", "apac"], ["CrunchWave"], ["India"],
        """
Solara's CrunchWave brand launched its 'Share the Crunch' festive campaign across
India ahead of the Q4 holiday season, spanning Modern Trade, Traditional Trade and
E-commerce. The campaign features limited-edition sharing packs and a national
outdoor and digital media push, Solara's largest CrunchWave marketing investment
in India to date.
"""))
    docs.append(doc(nid(), "Q4 2025 Earnings Commentary: CrunchWave India Holiday Performance", date(2026, 2, 3),
        "earnings_commentary", ["earnings", "salty_snacks", "apac", "seasonality"], ["CrunchWave"], ["India"],
        f"""
CrunchWave India delivered {growth_in if growth_in else 'strong'}% net revenue growth year-over-year in 2025,
with the Q4 holiday period the single largest contributor following the 'Share
the Crunch' campaign. Traditional Trade remained the largest channel by volume,
while E-commerce grew fastest off a smaller base.
"""))
    docs.append(doc(nid(), "Market Research Note: Festive Snacking Trends in APAC", date(2025, 12, 1),
        "market_research", ["salty_snacks", "apac", "seasonality", "consumer_trend"], ["CrunchWave", "Golden Harvest"],
        ["India", "Australia"],
        """
Snacking occasions in India and Australia both show pronounced Q4 seasonality
tied to festive and holiday gifting, with sharing-format packs outperforming
single-serve formats by a wide margin during this period. Manufacturers investing
in limited-edition festive packaging saw the strongest incremental lift.
"""))

    # --- Storyline 4: Ironclad Stout UK expansion ---
    docs.append(doc(nid(), "Ironclad Stout Expands Distribution in the United Kingdom", date(2024, 6, 18),
        "press_release", ["distribution", "beer", "europe"], ["Ironclad Stout"], ["United Kingdom"],
        f"""
Ironclad Stout announced an expanded distribution agreement in the United Kingdom,
targeting an increase in all-commodity-volume (ACV) distribution across independent
and Modern Trade retailers through 2025. Current UK ACV stands at {latest_acv(cur,'Ironclad Stout','United Kingdom')}%.
"""))
    docs.append(doc(nid(), "Internal Strategy Memo: Ironclad Stout UK Channel Mix", date(2024, 8, 5),
        "strategy_memo", ["strategy", "beer", "europe", "channel"], ["Ironclad Stout"], ["United Kingdom"],
        """
Recommendation: prioritize independent off-trade and Modern Trade distribution
gains over On-Premise expansion in the UK for Ironclad Stout through 2025, given
the brand's still-developing awareness relative to Glacier Peak. On-Premise
investment should follow, not lead, off-trade household penetration.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Craft Stout Entrants in the UK", date(2025, 1, 15),
        "competitor_intel", ["beer", "competitor", "europe"], ["Ironclad Stout"], ["United Kingdom"],
        """
Several independent craft breweries have entered the UK stout category at premium
price points over the past year. While individually small, their combined shelf
presence in independent retail has increased. No reliable third-party volume data
is available for these entrants; Solara tracks this qualitatively via distributor
and retailer conversations.
"""))

    # --- Storyline 5: SweetPeak sustainability - cocoa sourcing ---
    docs.append(doc(nid(), "SweetPeak Commits to 100% Certified Sustainable Cocoa by 2027", date(2024, 3, 1),
        "sustainability", ["sustainability", "confectionery", "sourcing"], ["SweetPeak"], [],
        f"""
{COMPANY_NAME}'s SweetPeak brand announced a commitment to source 100% certified
sustainable cocoa by 2027, up from approximately 55% today. The commitment covers
all SweetPeak SKUs globally and will be independently audited annually.
"""))
    docs.append(doc(nid(), "Market Research Note: Ethical Sourcing and Confectionery Purchase Intent", date(2024, 9, 10),
        "market_research", ["confectionery", "sustainability", "consumer_trend"], ["SweetPeak", "CocoNest"], [],
        """
Surveyed consumers across Solara's core confectionery markets rank "ethically
sourced ingredients" among the top three purchase drivers for premium chocolate,
though price and taste remain more influential overall. Certification labeling
on-pack has a measurable but modest effect on trial rate.
"""))
    docs.append(doc(nid(), "Press Release: SweetPeak Sourcing Progress Update", date(2025, 7, 8),
        "press_release", ["sustainability", "confectionery", "sourcing"], ["SweetPeak"], [],
        """
SweetPeak reports it has reached 68% certified sustainable cocoa sourcing,
ahead of its internal interim milestone, and reaffirms its 2027 target of 100%.
"""))

    # --- Storyline 6: PureSpring e-commerce push Brazil/Mexico ---
    growth_br, _, _ = yoy_growth(cur, "PureSpring", "Brazil", 2025)
    docs.append(doc(nid(), "Internal Strategy Memo: PureSpring LATAM E-commerce Acceleration", date(2025, 2, 20),
        "strategy_memo", ["strategy", "non_alcoholic", "latam", "ecommerce"], ["PureSpring"], ["Brazil", "Mexico"],
        """
Recommendation: shift incremental FY2025 marketing investment for PureSpring in
Brazil and Mexico toward E-commerce-specific media and retail media placements,
given E-commerce's outsized growth rate off a small base in both markets relative
to Modern and Traditional Trade.
"""))
    docs.append(doc(nid(), "Q4 2025 Earnings Commentary: PureSpring LATAM", date(2026, 2, 3),
        "earnings_commentary", ["earnings", "non_alcoholic", "latam", "ecommerce"], ["PureSpring"], ["Brazil", "Mexico"],
        f"""
PureSpring net revenue in Brazil grew {growth_br if growth_br else 'strongly'}% year-over-year in 2025, with
E-commerce the fastest-growing channel following the strategic shift toward
digital-first marketing investment agreed in February 2025.
"""))
    docs.append(doc(nid(), "Market Research Note: E-commerce Grocery Growth in LATAM", date(2025, 5, 19),
        "market_research", ["latam", "ecommerce", "consumer_trend"], ["PureSpring"], ["Brazil", "Mexico"],
        """
Online grocery penetration in Brazil and Mexico remains below 10% of total FMCG
retail value but is growing faster than any other channel, driven by quick-
commerce delivery apps and marketplace grocery sections. Non-alcoholic beverages
over-index in online grocery baskets relative to their offline channel share.
"""))

    # --- Storyline 7: Golden Harvest price increase rationale ---
    docs.append(doc(nid(), "Internal Strategy Memo: Golden Harvest Pricing Action", date(2024, 11, 12),
        "strategy_memo", ["strategy", "pricing", "salty_snacks"], ["Golden Harvest"], [],
        """
Recommendation: implement a low-single-digit list price increase on Golden
Harvest core SKUs in early 2025 to offset sustained input cost inflation
(sunflower oil, packaging film), while holding promotional depth roughly flat
to protect volume and shelf presence.
"""))
    docs.append(doc(nid(), "Q1 2025 Earnings Commentary: Golden Harvest Margin Recovery", date(2025, 5, 2),
        "earnings_commentary", ["earnings", "pricing", "salty_snacks", "margin"], ["Golden Harvest"], [],
        f"""
Golden Harvest gross margin improved year-over-year in Q1 2025 following the
pricing action taken in response to input cost inflation. Volume elasticity was
within modeled expectations; management does not currently plan further list
price increases in the near term.
"""))
    docs.append(doc(nid(), "Competitor Intelligence: Blue Ridge Snacks Pricing Response", date(2025, 6, 2),
        "competitor_intel", ["salty_snacks", "competitor", "pricing"], ["Golden Harvest"], [],
        """
Blue Ridge Snacks appears to have followed with comparable list price increases
across its core range shortly after Golden Harvest's pricing action, based on
retailer shelf-price checks. No official announcement was made by Blue Ridge Snacks.
"""))

    # --- Storyline 8: CocoNest Australia market entry ---
    docs.append(doc(nid(), "Solara Enters the Australian Market with CocoNest", date(2023, 9, 5),
        "press_release", ["market_entry", "confectionery", "apac"], ["CocoNest"], ["Australia"],
        """
Solara announced the entry of its CocoNest confectionery brand into Australia,
its first Oceania market launch, distributed initially through Modern Trade
retailers in Sydney with national rollout planned over 18 months.
"""))
    docs.append(doc(nid(), "Market Research Note: Premium Confectionery in Australia", date(2024, 2, 14),
        "market_research", ["confectionery", "apac", "consumer_trend"], ["CocoNest"], ["Australia"],
        """
The Australian premium confectionery segment has grown steadily, supported by
gifting occasions and a consumer base receptive to new international entrants
with clear provenance stories. Shelf space in Modern Trade for premium chocolate
has expanded modestly over the past two years.
"""))
    docs.append(doc(nid(), "Q4 2024 Earnings Commentary: CocoNest Australia One-Year Update", date(2025, 2, 4),
        "earnings_commentary", ["earnings", "confectionery", "apac"], ["CocoNest"], ["Australia"],
        f"""
CocoNest's first full year in Australia closed with distribution (ACV) of
{latest_acv(cur,'CocoNest','Australia')}% in Modern Trade and market share of {latest_share(cur,'CocoNest','Australia')}%,
tracking ahead of the original three-year market-entry plan.
"""))

    # --- Storyline 9: Company-wide annual highlights ---
    docs.append(doc(nid(), f"{COMPANY_NAME} FY2025 Annual Highlights", date(2026, 2, 20),
        "earnings_commentary", ["earnings", "company_wide", "annual"], [], [],
        """
FY2025 was a year of continued portfolio premiumization and channel mix shift
toward E-commerce across both the Beverages and Food divisions. Beverages growth
was led by Non-Alcoholic (Vivo Splash Zero launch) and a recovering On-Premise
channel for Beer. Food division growth was led by CrunchWave's Q4 campaign in
India and margin recovery in Golden Harvest following pricing actions.
Sustainability commitments across packaging (Vivo Splash) and sourcing
(SweetPeak) progressed ahead of interim milestones.
"""))
    docs.append(doc(nid(), "Solara Group Investor FAQ: Data and Reporting Scope", date(2026, 1, 10),
        "metadata_note", ["reporting", "company_wide", "scope"], [], [],
        f"""
{COMPANY_NAME} reports net revenue, volume, market share, average selling price,
distribution (ACV), marketing spend, promotion spend and gross margin, at
brand x country x channel x month grain, for its eight core brands across
eight countries. Data is available from January 2023 through the most recently
closed month. Competitor performance figures are not part of Solara's internal
reporting scope; any competitor references in company materials are qualitative
and sourced from public information only.
"""))

    # --- Storyline 10: generic competitive landscape overview ---
    docs.append(doc(nid(), "Competitive Landscape Overview: FMCG Beverages and Snacks", date(2025, 8, 1),
        "competitor_intel", ["competitor", "market_overview"], [], [],
        f"""
Solara's principal named competitors referenced in internal materials include
{', '.join(FICTIONAL_COMPETITORS)}. Solara does not maintain structured sales
data for any competitor; all competitor commentary in this document set is
qualitative and directional, drawn from public announcements, retailer shelf
checks, and market research panels.
"""))

    manifest = {"company": COMPANY_NAME, "generated": date.today().isoformat(), "documents": []}
    DOC_DIR.mkdir(parents=True, exist_ok=True)
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
