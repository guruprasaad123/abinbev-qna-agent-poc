"""
Build the unstructured document corpus for the real AB InBev dataset.

Design (see docs/DESIGN_DECISIONS.md §1/§2):
  - Every document here is a short analyst-brief I (the build) wrote myself,
    summarizing REAL, publicly disclosed AB InBev figures and REAL quoted
    commentary -- never a fabricated document presented as if AB InBev
    itself issued it. Each document ends with an explicit citation (source
    title + URL) to the actual press release / filing it's drawn from, so
    every claim is traceable to a primary source.
  - Numbers quoted in these briefs are pulled LIVE from data/db/ab_inbev.db
    (the same real numbers loaded by generate_structured_data.py), which is
    what guarantees a SQL answer and a document citation agree exactly --
    this is the same "single source of truth" principle the original design
    used, just grounded in real transcribed figures instead of a random
    generator.
  - Country- and brand-level color (which has NO structured/SQL
    representation -- see src/config.py) lives ONLY here, in the documents,
    which is what makes hybrid retrieval and hierarchy-aware fallback real
    rather than contrived: a question about "Brazil" or "Corona" genuinely
    can't be answered from SQL and genuinely can be answered from these
    documents.
  - Real, named competitors are mentioned exactly once, in a purely
    qualitative competitive-landscape note -- no invented figures about them,
    ever.
"""
import json
import sqlite3
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import COMPANY_NAME, KNOWN_COMPETITORS

ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "data" / "unstructured"
DB_PATH = ROOT / "data" / "db" / "ab_inbev.db"

_counter = [0]


def nid():
    _counter[0] += 1
    return f"DOC-{_counter[0]:03d}"


def doc(doc_id, title, dt, source_type, tags, brands, countries, body, source_label, source_url):
    footer = f"\n\n---\n*Source: {source_label} — {source_url}*"
    return {
        "doc_id": doc_id, "title": title, "date": dt.isoformat(), "source_type": source_type,
        "tags": tags, "brands": brands, "countries": countries, "body": body.strip() + footer,
    }


def zone_row(cur, zone, year, quarter):
    cur.execute("""SELECT revenue_usd_m, volume_k_hl, normalized_ebitda_usd_m, ebitda_margin_pct,
                          organic_revenue_growth_pct, source_label, source_url
                   FROM fact_kpi WHERE grain='quarterly' AND zone=? AND year=? AND quarter=?""",
                (zone, year, quarter))
    return cur.fetchone()


def global_annual(cur, year):
    cur.execute("""SELECT revenue_usd_m, volume_k_hl, normalized_ebitda_usd_m, ebitda_margin_pct,
                          organic_revenue_growth_pct, net_profit_usd_m, source_label, source_url
                   FROM fact_kpi WHERE grain='annual' AND zone='Global' AND year=?""", (year,))
    return cur.fetchone()


ZONES = ["North America", "Middle Americas", "South America", "EMEA", "Asia Pacific"]


def quarterly_brief(cur, year, quarter, dt, extra=""):
    lines = []
    for z in ZONES:
        rev, vol, ebitda, margin, growth, src, url = zone_row(cur, z, year, quarter)
        lines.append(f"- **{z}**: revenue ${rev:,.0f}M (organic growth {growth:+.1f}%), "
                      f"volume {vol:,.0f}K hL, normalized EBITDA ${ebitda:,.0f}M (margin {margin:.1f}%).")
    _, _, _, _, _, src, url = zone_row(cur, ZONES[0], year, quarter)
    body = (f"Zone-by-zone results for Q{quarter} {year}:\n\n" + "\n".join(lines) +
            (f"\n\n{extra}" if extra else ""))
    return body, src, url


def build():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    docs = []

    # --- Q1-Q3 2024 quarterly briefs ---
    body, src, url = quarterly_brief(cur, 2024, 1, date(2024, 5, 7),
        "North America organic revenue declined as U.S. industry volumes remained soft, while EMEA "
        "posted the fastest organic growth of any zone, helped by premiumization in Europe and recovery "
        "in Nigeria and South Africa.")
    docs.append(doc(nid(), "Q1 2024 Results: Zone-by-Zone Summary", date(2024, 5, 7), "earnings_commentary",
        ["earnings", "quarterly", "Q1 2024"] + ZONES, [], [], body, src, url))

    body, src, url = quarterly_brief(cur, 2024, 2, date(2024, 7, 31),
        "Asia Pacific organic revenue fell for a second straight quarter, driven mainly by continued "
        "softness in China, while Middle Americas and EMEA both grew normalized EBITDA faster than revenue.")
    docs.append(doc(nid(), "Q2 2024 Results: Zone-by-Zone Summary", date(2024, 7, 31), "earnings_commentary",
        ["earnings", "quarterly", "Q2 2024"] + ZONES, [], [], body, src, url))

    body, src, url = quarterly_brief(cur, 2024, 3, date(2024, 10, 30),
        "North America returned to modest organic growth, while Asia Pacific's decline deepened further "
        "on continued China weakness -- a pattern that persisted through the rest of 2024.")
    docs.append(doc(nid(), "Q3 2024 Results: Zone-by-Zone Summary", date(2024, 10, 30), "earnings_commentary",
        ["earnings", "quarterly", "Q3 2024"] + ZONES, [], [], body, src, url))

    # --- FY2024 / Q4 2024 full year ---
    rev, vol, ebitda, margin, growth, netp, src, url = global_annual(cur, 2024)
    body, _, _ = quarterly_brief(cur, 2024, 4, date(2025, 2, 26),
        f"Full-year 2024: consolidated revenue ${rev:,.0f}M (organic growth {growth:+.1f}%), volume "
        f"{vol:,.0f}K hL, normalized EBITDA ${ebitda:,.0f}M (margin {margin:.1f}%), net profit "
        f"${netp:,.0f}M. Megabrands (the company's global/multi-country brand portfolio, including "
        f"Budweiser, Corona, Stella Artois and Michelob Ultra) grew revenue 4.6% for the year; Corona "
        f"delivered low-teens revenue growth outside Mexico. Asia Pacific was the weakest zone for the "
        f"full year, with revenue down 10.9% organically on continued China softness.")
    docs.append(doc(nid(), "FY2024 Full-Year Results and Q4 2024 Summary", date(2025, 2, 26),
        "earnings_commentary", ["earnings", "annual", "FY2024", "Q4 2024", "megabrands"] + ZONES,
        ["Budweiser", "Corona", "Stella Artois", "Michelob Ultra"], ["China", "Mexico"], body, src, url))

    # --- Q1-Q3 2025 quarterly briefs ---
    body, src, url = quarterly_brief(cur, 2025, 1, date(2025, 5, 7),
        "Middle Americas and South America led organic growth, with Brazil-driven strength in South "
        "America; North America and Asia Pacific both posted organic revenue declines.")
    docs.append(doc(nid(), "Q1 2025 Results: Zone-by-Zone Summary", date(2025, 5, 7), "earnings_commentary",
        ["earnings", "quarterly", "Q1 2025"] + ZONES, [], ["Brazil"], body, src, url))

    body, src, url = quarterly_brief(cur, 2025, 2, date(2025, 7, 31),
        "All zones except Asia Pacific grew organic revenue in Q2 2025; North America returned to "
        "positive organic growth for the first time in several quarters.")
    docs.append(doc(nid(), "Q2 2025 Results: Zone-by-Zone Summary", date(2025, 7, 31), "earnings_commentary",
        ["earnings", "quarterly", "Q2 2025"] + ZONES, [], [], body, src, url))

    body, src, url = quarterly_brief(cur, 2025, 3, date(2025, 10, 30),
        "Asia Pacific organic revenue declined again in Q3 2025, its steepest quarterly drop of the "
        "year, while Middle Americas remained the most consistent grower across 2025.")
    docs.append(doc(nid(), "Q3 2025 Results: Zone-by-Zone Summary", date(2025, 10, 30), "earnings_commentary",
        ["earnings", "quarterly", "Q3 2025"] + ZONES, [], [], body, src, url))

    # --- FY2025 / Q4 2025 full year ---
    rev, vol, ebitda, margin, growth, netp, src, url = global_annual(cur, 2025)
    body, _, _ = quarterly_brief(cur, 2025, 4, date(2026, 2, 11),
        f"Full-year 2025: consolidated revenue ${rev:,.0f}M, volume {vol:,.0f}K hL, normalized EBITDA "
        f"${ebitda:,.0f}M (margin {margin:.1f}%), net profit ${netp:,.0f}M. Megabrands grew revenue "
        f"4.1% for the year; Corona grew revenue 8.3% outside Mexico with double-digit volume growth; "
        f"Michelob Ultra became the #1 volume share gainer in the U.S. beer industry and, per the "
        f"company, the leading brand by volume in that market. Asia Pacific again posted the steepest "
        f"organic revenue decline of any zone for the year (-6.5%).")
    docs.append(doc(nid(), "FY2025 Full-Year Results and Q4 2025 Summary", date(2026, 2, 11),
        "earnings_commentary", ["earnings", "annual", "FY2025", "Q4 2025", "megabrands"] + ZONES,
        ["Corona", "Michelob Ultra"], ["Mexico", "United States"], body, src, url))

    # --- FY2022 / FY2023 (company totals only -- no zone breakout sourced) ---
    rev, vol, ebitda, margin, growth, netp, src, url = global_annual(cur, 2022)
    docs.append(doc(nid(), "FY2022 Full-Year Results: Company Totals", date(2023, 3, 1), "earnings_commentary",
        ["earnings", "annual", "FY2022"], [], [],
        f"Full-year 2022 consolidated results: revenue ${rev:,.0f}M, volume {vol:,.0f}K hL, normalized "
        f"EBITDA ${ebitda:,.0f}M (margin {margin:.1f}%), net profit ${netp:,.0f}M. Zone-level absolute "
        f"figures for this year are not part of this build's structured data (see "
        f"docs/DESIGN_DECISIONS.md) -- only the company-wide total is loaded.", src, url))

    rev, vol, ebitda, margin, growth, netp, src, url = global_annual(cur, 2023)
    docs.append(doc(nid(), "FY2023 Full-Year Results: Company Totals", date(2024, 2, 28), "earnings_commentary",
        ["earnings", "annual", "FY2023"], [], [],
        f"Full-year 2023 consolidated results: revenue ${rev:,.0f}M, volume {vol:,.0f}K hL, normalized "
        f"EBITDA ${ebitda:,.0f}M (margin {margin:.1f}%), net profit ${netp:,.0f}M. As with FY2022, only "
        f"the company-wide total is loaded into the structured database for this year.", src, url))

    # --- Country-level qualitative color (real quotes, from the FY2025 SEC EX-99.2 filing) ---
    docs.append(doc(nid(), "FY2025 Country-Level Commentary (Selected Markets)", date(2026, 2, 12),
        "filing_excerpt", ["country color", "FY2025", "volumes"],
        [], ["United States", "Brazil", "Mexico", "China", "Colombia", "Argentina", "South Korea"],
        """
Selected country-level volume commentary from AB InBev's FY2025 annual filing (SEC Exhibit 99.2):
- United States: sales-to-retailers and sales-to-wholesalers both declined 3.2% in 2025.
- Brazil: volumes declined 4.1%, with beer volumes down 4.6%.
- Mexico: volumes were flat in 2025.
- China: volumes declined 8.6%.
- Colombia: volumes increased by low-single digits.
- Argentina: volumes declined by mid-single digits.
- South Korea: volumes declined by low-single digits in 2025.

None of these country-level figures have a corresponding row in the structured database -- AB InBev
discloses volume trends like these narratively, by country, but does not publish a structured
country-by-country revenue/volume table. A question about any of these countries should be answered
from this document, with the relevant zone's structured KPIs (North America, South America, Middle
Americas, Asia Pacific respectively) offered as the closest structured figure available.
""", "AB InBev FY2025 Annual Report, Exhibit 99.2 (SEC EDGAR)",
        "https://www.sec.gov/Archives/edgar/data/1668717/000119312526049841/d891969dex992.htm"))

    # --- Brand / megabrand performance summary ---
    docs.append(doc(nid(), "Megabrand Performance Summary, FY2024-FY2025", date(2026, 2, 12),
        "market_research", ["brands", "megabrands", "FY2024", "FY2025"],
        ["Budweiser", "Corona", "Stella Artois", "Michelob Ultra"], ["Mexico", "United States"],
        """
AB InBev's "megabrands" -- its global and multi-country brand portfolio, anchored by Budweiser,
Corona, Stella Artois and Michelob Ultra -- grew revenue 4.6% in FY2024 and 4.1% in FY2025, both
years ahead of total company revenue growth. Corona (outside Mexico, where Constellation Brands
holds a permanent license to the Corona/Modelo brand family) grew revenue by low-teens percent in
FY2024 and 8.3% in FY2025, with double-digit volume growth in FY2025. Michelob Ultra was the #1
volume share gainer in the U.S. beer industry in FY2025 and, per the company, became the leading
brand by volume in that market. As with all brand-level figures in this build, these are qualitative/
percentage disclosures only -- there is no absolute brand-level revenue or volume figure published,
and none is stored in the structured database.
""", "AB InBev FY2024 and FY2025 Full-Year Results (BusinessWire)",
        "https://www.businesswire.com/news/home/20250225267454/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2024-Results"))

    # --- Non-GAAP metrics glossary ---
    docs.append(doc(nid(), "Glossary: Organic Growth and Normalized EBITDA", date(2026, 2, 11),
        "metadata_note", ["glossary", "definitions", "non-gaap"], [], [],
        """
AB InBev reports two non-GAAP metrics used throughout this dataset and its documents:
- **Organic revenue growth**: revenue growth excluding the effects of foreign-currency translation
  and scope changes (acquisitions/disposals) -- intended to isolate underlying business performance
  from FX and portfolio effects.
- **Normalized EBITDA**: EBITDA (earnings before interest, tax, depreciation and amortization)
  adjusted to exclude non-recurring items, so it can be compared cleanly period over period.
EBITDA margin (normalized EBITDA / revenue) is not separately disclosed by the company for every
period; where it appears in this dataset's structured rows, it has been computed from the two
disclosed figures, and is labeled as computed rather than reported.
""", "AB InBev quarterly and full-year results releases (BusinessWire) -- definitions section",
        "https://www.businesswire.com/news/home/20260211688662/en/AB-InBev-Reports-Full-Year-and-Fourth-Quarter-2025-Results"))

    # --- Competitive landscape (real competitors, qualitative only) ---
    docs.append(doc(nid(), "Competitive Landscape Overview: Global Brewing Industry", date(2025, 8, 1),
        "competitor_intel", ["competitor", "market_overview"], [], [],
        f"""
AB InBev's principal global and regional peers by volume include {', '.join(KNOWN_COMPETITORS)}.
This build does not maintain structured (SQL-queryable) financial data for any of these
companies -- they are real businesses, but outside {COMPANY_NAME}'s own disclosed reporting, so
any question about a named competitor's own financials should be answered via web search (their own
public results), never by inventing a figure here. One notable brand-licensing nuance: Constellation
Brands, not AB InBev, holds the U.S. beer rights to Corona and Modelo, even though AB InBev owns
those brands (via Grupo Modelo) everywhere else in the world.
""", "General industry knowledge; brand-licensing fact per AB InBev/Constellation Brands public disclosures",
        "https://www.ab-inbev.com/investors"))

    # --- Reporting scope / metadata note ---
    docs.append(doc(nid(), f"{COMPANY_NAME} Data and Reporting Scope Notes", date(2026, 2, 12),
        "metadata_note", ["reporting", "scope"], [], [],
        f"""
This build's structured database covers real, publicly disclosed {COMPANY_NAME} results: revenue,
volume, normalized EBITDA, EBITDA margin (computed), organic revenue growth and net profit, at
zone x quarter grain for Q1 2024-Q4 2025, and zone/company x year grain for FY2022-FY2025.
There is no structured brand-level or country-level data -- AB InBev does not publish financials at
that granularity -- so brand and country questions are answered from qualitative commentary in these
documents instead, with an explicit note when that substitution happens.
""", "Internal reporting-scope note for this build", "https://www.ab-inbev.com/investors"))

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
