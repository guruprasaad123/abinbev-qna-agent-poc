"""
Generate the synthetic unstructured document corpus for Anheuser-Busch InBev (AB InBev).

Design:
  - 28 documents across 10 realistic corporate storylines covering AB InBev's global operations:
      * Corona Cero Worldwide Olympic Partnership & Beyond Beer moderation trends
      * BEES B2B digital marketplace expansion across traditional trade
      * Michelob ULTRA active-lifestyle premiumization in North America & Mexico
      * TaDa Delivery direct-to-consumer cold beer network
      * ESG 2025 Sustainability & Water Watershed Stewardship (Monterrey & Leuven)
      * Budweiser FIFA World Cup and global sports sponsorships
      * Revenue Management & Net Revenue per hectoliter (NR/hL) realization
      * Competitor benchmarking against Heineken NV, Carlsberg, and Molson Coors
      * Circular economy: Returnable glass bottles (RGB) in Latin America
      * Belgian heritage & specialty craft: Stella Artois draught and Hoegaarden in APAC
  - Documents embed live values pulled from data/db/abinbev.db (YoY revenue growth,
    market share, ACV/reach) to guarantee quantitative and qualitative coherence.
  - Manifest written to data/unstructured/manifest.json for metadata-driven retrieval.
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import COMPANY_NAME, COMPANY_SHORT_NAME

ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "data" / "unstructured"
DB_PATH = ROOT / "data" / "db" / "abinbev.db"

KNOWN_COMPETITORS = ["Heineken", "Carlsberg", "Molson Coors", "Constellation Brands"]


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

    # --- Storyline 1: Corona Cero Worldwide Olympic Partnership & Beyond Beer Momentum ---
    growth_cero_uk, _, _ = yoy_growth(cur, "Corona Cero", "United Kingdom", 2025)
    growth_cero_mx, _, _ = yoy_growth(cur, "Corona Cero", "Mexico", 2025)

    docs.append(doc(nid(), "AB InBev Announces Corona Cero as Worldwide Olympic Partner", date(2025, 1, 15),
        "press_release", ["olympics", "non_alcoholic", "beyond_beer", "global_partnership"], ["Corona Cero", "Corona"], ["United Kingdom", "Belgium", "Mexico"],
        f"""
{COMPANY_NAME} ({COMPANY_SHORT_NAME}) today announced a historic global partnership with the International Olympic
Committee (IOC), naming Corona Cero the Worldwide Olympic Partner for the Olympic and Paralympic Games.
This partnership highlights AB InBev's commitment to responsible consumption and accelerating the
growth of non-alcoholic beer. Corona Cero 0.0% offers consumers the authentic taste of Corona with
zero alcohol. "Beer and sports bring people together, and Corona Cero exemplifies our dedication to
offering consumer choice and moderation on the global stage," said the Chief Commercial Officer.
Rollout across major European and Latin American retail and on-premise channels is underway.
"""))

    docs.append(doc(nid(), "Q1 2025 Earnings Commentary: Corona Cero Acceleration in Europe and Mexico", date(2025, 4, 30),
        "earnings_commentary", ["earnings", "non_alcoholic", "beyond_beer", "growth"], ["Corona Cero"], ["United Kingdom", "Mexico", "Belgium"],
        f"""
Corona Cero delivered exceptional performance in early 2025, buoyed by the global Olympic campaign.
In the United Kingdom, Corona Cero net revenue expanded {growth_cero_uk if growth_cero_uk else 'over 20'}% year-over-year,
while Mexico posted net revenue growth of {growth_cero_mx if growth_cero_mx else 'over 18'}%. Distribution (ACV)
in the UK reached {latest_acv(cur, 'Corona Cero', 'United Kingdom')}% as grocery and On-Premise accounts expanded shelf space.
Management highlighted that the Beyond Beer segment continues to command premium revenue per hectoliter
and higher gross margins than traditional mainstream lagers.
"""))

    docs.append(doc(nid(), "Market Research Note: The Moderation Mega-Trend and No/Low Alcohol Beer", date(2025, 6, 20),
        "market_research", ["consumer_trend", "non_alcoholic", "moderation", "gen_z"], ["Corona Cero"], ["United Kingdom", "United States", "Mexico"],
        f"""
Consumer demand for non-alcoholic beer is transitioning from a niche category to a mainstream drinking occasion.
Industry survey data indicates that over 54% of consumers aged 21-34 actively look for 0.0% alternatives during
weekday dining, social gatherings, and fitness occasions. In key markets like the United Kingdom and Mexico,
Corona Cero has capitalized on this trend by associating non-alcoholic beer with relaxation and active outdoor
lifestyles rather than deprivation. Distribution reach and premium brand equity remain the decisive drivers
of brand choice in the no-alcohol space.
"""))

    # --- Storyline 2: BEES Digital B2B Platform Expansion & Ecosystem Monetization ---
    docs.append(doc(nid(), "AB InBev's BEES Platform Surpasses $35 Billion in Annualized Gross Merchandise Value", date(2025, 2, 18),
        "press_release", ["bees", "digital_transformation", "b2b_platform", "traditional_trade"], ["Brahma", "Corona", "Budweiser"], ["Brazil", "Mexico", "China"],
        f"""
{COMPANY_SHORT_NAME} today announced that its proprietary B2B digital marketplace, BEES, has surpassed $35 billion
in annualized Gross Merchandise Value (GMV), serving over 3.2 million monthly active small and medium retailers.
BEES enables small mom-and-pop store owners (traditional trade bodegas and tienditas) in countries like Brazil,
Mexico, and China to order beer, manage inventory, earn rewards, and access essential consumer goods 24/7.
The platform's algorithm-driven suggested orders have significantly reduced stock-outs across core brands
including Brahma, Corona, and Budweiser.
"""))

    docs.append(doc(nid(), "Strategy Memo: Modernizing the Traditional Trade via the BEES Ecosystem", date(2025, 5, 12),
        "strategy_memo", ["bees", "traditional_trade", "route_to_market", "digital"], ["Brahma", "Bud Light"], ["Brazil", "Mexico"],
        f"""
MEMORANDUM TO EXECUTIVE LEADERSHIP
Subject: Monetizing the Digital Ecosystem via BEES Marketplace
The traditional trade channel represents over 35% of our global volume, particularly in Latin America.
BEES transforms this historically fragmented channel into an interconnected digital network.
Key strategic outcomes include:
1. Higher digital order frequency: Retailers order 1.8x more frequently on BEES compared to manual sales visits.
2. Cross-selling third-party products: Non-beer products generated over $1.5 billion in marketplace GMV.
3. Pricing compliance: Dynamic discount management on BEES protects price realization across Brahma and Budweiser.
Recommendation: Expand BEES Pay credit solutions to improve cash flow for high-volume retail accounts in Brazil and Mexico.
"""))

    docs.append(doc(nid(), "Q2 2025 Earnings Commentary: Digital Route-to-Market Highlights", date(2025, 7, 28),
        "earnings_commentary", ["earnings", "bees", "digital_sales", "traditional_trade"], ["Brahma", "Corona"], ["Brazil", "Mexico", "India"],
        f"""
Digital ordering via the BEES platform now accounts for more than 70% of total company net revenue in Brazil
and Mexico. Brahma distribution in Brazil reached {latest_acv(cur, 'Brahma', 'Brazil')}% ACV, supported by BEES
automated replenishment in the traditional trade. Digital capture has improved supply chain visibility and
reduced logistics overhead, contributing to overall gross margin resilience despite higher packaging raw material costs.
"""))

    # --- Storyline 3: Michelob ULTRA Active Lifestyle Premiumization ---
    growth_ultra_us, _, _ = yoy_growth(cur, "Michelob ULTRA", "United States", 2025)
    growth_ultra_mx, _, _ = yoy_growth(cur, "Michelob ULTRA", "Mexico", 2025)

    docs.append(doc(nid(), "Michelob ULTRA Expands Premium Active Footprint into Mexico and Canada", date(2025, 3, 22),
        "press_release", ["michelob_ultra", "premiumization", "active_lifestyle"], ["Michelob ULTRA"], ["United States", "Mexico", "Canada"],
        f"""
Building on its explosive growth as the second-largest beer brand by volume in the United States, Michelob ULTRA
is aggressively scaling its presence across Mexico and Canada. Michelob ULTRA delivers 95 calories and 2.6 grams
of carbohydrates, meeting the growing consumer demand for active, health-conscious lifestyle beverages.
Marketing will feature sponsorships with major running clubs, pickleball tournaments, and golf associations.
Initial shipments through Modern Trade hypermarkets and On-Premise sports bars commenced this month.
"""))

    docs.append(doc(nid(), "Market Research Note: Premium Light & Wellness Positioning in North America", date(2025, 6, 8),
        "market_research", ["consumer_trend", "wellness", "premium_light"], ["Michelob ULTRA", "Bud Light"], ["United States", "Canada"],
        f"""
Consumer preference in the North American beer market continues to shift decisively toward premiumization
and active lifestyle propositions. Michelob ULTRA's value proposition of crisp taste with low carbs has
allowed it to attract consumers from both mainstream light beers and hard seltzers. In the United States,
Michelob ULTRA achieved a market share of {latest_share(cur, 'Michelob ULTRA', 'United States')}%, reflecting steady
share gains against legacy light lagers. The brand maintains strong pricing power, retailing at an average
premium of 15% over mainstream lagers.
"""))

    docs.append(doc(nid(), "Q3 2025 Earnings Commentary: Michelob ULTRA Profitability and Volume Surge", date(2025, 10, 29),
        "earnings_commentary", ["earnings", "michelob_ultra", "margin_expansion"], ["Michelob ULTRA"], ["United States", "Mexico"],
        f"""
Michelob ULTRA net revenue grew {growth_ultra_us if growth_ultra_us else 'double-digit'}% year-over-year in the United States
and {growth_ultra_mx if growth_ultra_mx else 'over 15'}% in Mexico during 2025. Management noted that Michelob ULTRA's
higher net revenue per hectoliter ($75-$80/hL) and superior gross margin ({latest_share(cur, 'Michelob ULTRA', 'United States')}%+ share)
have been major contributors to EBITDA margin expansion in the North America and Middle Americas zones.
"""))

    # --- Storyline 4: TaDa Delivery Direct-to-Consumer Cold Beer Expansion ---
    docs.append(doc(nid(), "TaDa Delivery Reaches 25 Million Annual Orders in South America", date(2025, 4, 14),
        "press_release", ["tada_delivery", "d2c", "e_commerce", "cold_beer"], ["Brahma", "Corona", "Budweiser"], ["Brazil", "Mexico"],
        f"""
{COMPANY_NAME} announced today that TaDa Delivery, its direct-to-consumer cold beer and beverage delivery app,
surpassed 25 million orders in 2025 across Brazil and Mexico. TaDa Delivery leverages local retail partners and
micro-fulfillment hubs to deliver cold beer to consumers in under 30 minutes at competitive supermarket prices.
The service has proven especially effective at driving trial for premium brands like Corona and Stella Artois
during evening and weekend home-entertainment occasions.
"""))

    docs.append(doc(nid(), "Earnings Call Commentary: Direct-to-Consumer Insights & Occasion Capture", date(2025, 8, 5),
        "earnings_commentary", ["earnings", "d2c", "tada_delivery", "consumer_insights"], ["Corona", "Brahma"], ["Brazil", "Mexico"],
        f"""
TaDa Delivery continued its profitable expansion in Latin America, achieving positive unit economics in key urban
centers including Sao Paulo and Mexico City. The platform provides valuable first-party consumer data on purchase
frequency, basket size, and occasion preferences, which AB InBev's revenue management teams use to optimize promo
spend and channel-specific SKU packaging.
"""))

    # --- Storyline 5: ESG 2025 Sustainability Goals: Watersheds & Renewable Electricity ---
    docs.append(doc(nid(), "AB InBev Reaches 100% Renewable Electricity at Key Breweries in Belgium and Brazil", date(2025, 2, 25),
        "sustainability", ["sustainability", "esg", "renewable_energy", "net_zero"], ["Stella Artois", "Brahma"], ["Belgium", "Brazil"],
        f"""
In line with its 2025 Sustainability Goals, {COMPANY_NAME} has achieved 100% renewable electricity supply across
all operational breweries in Belgium and Brazil. Major power purchase agreements (PPAs) with off-site solar
and wind farms now power the historic Stella Artois brewery in Leuven and the high-volume Brahma facilities in
Sao Paulo. The milestone reduces scope 2 carbon emissions by approximately 240,000 metric tons annually.
"""))

    docs.append(doc(nid(), "Sustainability Update: Watershed Protection and Water Stewardship in Mexico", date(2025, 5, 20),
        "sustainability", ["sustainability", "esg", "water_stewardship", "watershed"], ["Corona"], ["Mexico", "United States"],
        f"""
Water is the primary ingredient in brewing beer. AB InBev's flagship Monterrey brewery in Mexico has achieved
a world-class water efficiency ratio of 2.1 hectoliters of water per hectoliter of beer produced, far surpassing
the global brewing benchmark of 3.2 hL/hL. In partnership with local water authorities and NGOs, AB InBev invested
over $12 million in reforestation, aquifer recharge, and infrastructure upgrades across the San Juan River basin,
securing measurable water availability for surrounding communities.
"""))

    docs.append(doc(nid(), "Strategy Memo: Circular Packaging and Net-Zero Carbon Brewery Roadmap", date(2025, 9, 14),
        "strategy_memo", ["sustainability", "esg", "packaging", "circular_economy"], ["Corona", "Stella Artois"], ["Belgium", "United Kingdom", "United States"],
        f"""
MEMORANDUM: 2030 Climate Action & Circular Packaging Architecture
Executive Summary:
1. Target: 100% of our products in packaging that is returnable or made from majority recycled content.
2. Lightweighting: Scaled 330ml lightweight glass bottles for Corona and Stella Artois, saving 18% glass by weight.
3. Thermal efficiency: Electrification of brewing kettles using biogas and high-temperature heat pumps in Leuven, Belgium.
4. Capital expenditure impact: ESG investments in water and energy yield a payback period under 3.8 years through
reduced utility overhead and regulatory compliance credits.
"""))

    # --- Storyline 6: Budweiser Global Sports & Culture Partnerships (FIFA World Cup) ---
    docs.append(doc(nid(), "Budweiser Renews Official Sponsorship for the 2026 FIFA World Cup in North America", date(2024, 11, 10),
        "press_release", ["budweiser", "sponsorship", "fifa_world_cup", "sports_marketing"], ["Budweiser", "Bud Light"], ["United States", "Mexico", "Canada"],
        f"""
{COMPANY_NAME} has officially renewed its long-standing partnership with FIFA as the Official Beer Sponsor of the
2026 FIFA World Cup across the United States, Mexico, and Canada. As the biggest sporting event in history, the
tournament will showcase Budweiser and Budweiser Zero to an estimated 5 billion viewers worldwide. Marketing spend
will focus on celebratory packaging, stadium on-premise draught experiences, and integrated digital fan activations
on social media and TaDa Delivery apps.
"""))

    docs.append(doc(nid(), "Earnings Commentary: Brand Equity and Sponsorship ROI Across Global Megabrands", date(2025, 8, 22),
        "earnings_commentary", ["earnings", "marketing_spend", "brand_equity", "roi"], ["Budweiser", "Corona"], ["United States", "China", "United Kingdom"],
        f"""
Marketing spend efficiency improved by 80 basis points during the first half of 2025. Budweiser marketing spend
in the United States totaled over $85 million, supporting national sports sponsorships and summer music festival
campaigns. Net revenue response has stabilized in North America while driving high-single-digit brand equity
gains in China and India, where Budweiser is positioned as an aspirational international premium lager.
"""))

    # --- Storyline 7: Revenue Management & Net Revenue per Hectoliter (NR/hL) Realization ---
    docs.append(doc(nid(), "Earnings Review: Disciplined Revenue Management Drives Net Revenue per Hectoliter Growth", date(2025, 4, 18),
        "earnings_commentary", ["earnings", "pricing", "asp", "revenue_management"], ["Budweiser", "Stella Artois", "Corona"], ["United States", "Brazil", "Belgium"],
        f"""
During fiscal year 2024 and year-to-date 2025, AB InBev applied disciplined revenue management actions to offset
commodity cost pressures (barley, aluminum, and freight). Global Net Revenue per hectoliter (ASP) increased
by 5.2% on a constant currency basis, driven by premium brand mix and targeted price adjustments. Gross margin
remained robust at 52-54% across major operating divisions, reflecting the pricing power of our global brands.
"""))

    docs.append(doc(nid(), "Strategy Memo: Pack-Price Architecture and Promo Spend Effectiveness", date(2025, 7, 10),
        "strategy_memo", ["pricing", "pack_price_architecture", "promo_spend", "profitability"], ["Corona", "Bud Light"], ["United States", "Mexico"],
        f"""
EXECUTIVE BRIEFING: Pack-Price Architecture Optimization
To navigate inflation while safeguarding retail volume, the revenue management committee approved the following
pack-price guidelines:
- Expand multi-pack variety formats (e.g. 12-packs and 24-packs) in Modern Trade to protect volume and household penetration.
- Restrict deep price discounting; shift trade promotion budgets into in-store digital merchandising on BEES.
- Maintain a minimum 25% price premium for Corona Extra and Stella Artois over mainstream core lager SKUs.
"""))

    # --- Storyline 8: Competitor Benchmarking (External Market Intelligence) ---
    docs.append(doc(nid(), "Competitive Intelligence: Heineken NV Expansion in European Premium and 0.0%", date(2025, 3, 14),
        "competitor_intel", ["competitor", "heineken", "europe", "market_intelligence"], ["Corona", "Corona Cero", "Stella Artois"], ["United Kingdom", "Belgium"],
        f"""
COMPETITOR BRIEFING: Heineken NV (External Competitor)
Heineken NV continues to invest heavily in its flagship Heineken 0.0 brand across Western Europe and Brazil.
Key competitive dynamics:
1. European 0.0% share: Heineken 0.0 remains the volume leader in European grocery channels, but Corona Cero
gained significant ground in Q2 2025 following its Olympic sponsorship announcement.
2. Pricing: Heineken is pricing parity to Stella Artois in the UK on-premise trade ($82-$85/hL).
Note: Heineken is an independent global competitor. AB InBev maintains no equity stake or shared distribution.
"""))

    docs.append(doc(nid(), "Competitive Intelligence: Carlsberg Group European and Asian Footprint", date(2025, 5, 29),
        "competitor_intel", ["competitor", "carlsberg", "asia", "market_intelligence"], ["Budweiser", "Hoegaarden"], ["China", "India"],
        f"""
COMPETITOR BRIEFING: Carlsberg Group (External Competitor)
Carlsberg has accelerated its 'Accelerate SAIL' strategy, focusing on premium lagers and specialty craft acquisitions
in Western Europe and Western China. In China, Carlsberg's 1664 Blanc specialty wheat brand directly competes with
AB InBev's Hoegaarden in tier-1 on-premise venues. Hoegaarden maintains superior distribution reach via BEES
in eastern and southern Chinese provinces.
"""))

    docs.append(doc(nid(), "Competitive Intelligence: Molson Coors and US Light Beer Dynamics", date(2025, 9, 18),
        "competitor_intel", ["competitor", "molson_coors", "united_states", "market_intelligence"], ["Bud Light", "Michelob ULTRA"], ["United States", "Canada"],
        f"""
COMPETITOR BRIEFING: Molson Coors Beverage Company (External Competitor)
In the United States light beer segment, Molson Coors has positioned Coors Light and Miller Lite aggressively
against Bud Light in convenience and grocery channels. While mainstream light lager volumes remain pressured across
the broader industry, AB InBev's Michelob ULTRA has captured premium market share, offsetting segment headwinds.
"""))

    # --- Storyline 9: Circular Packaging & Returnable Glass Bottles (RGB) ---
    docs.append(doc(nid(), "Returnable Glass Bottle Initiative Expands Across Latin America", date(2025, 6, 25),
        "sustainability", ["sustainability", "packaging", "circular_economy", "latin_america"], ["Brahma", "Corona"], ["Brazil", "Mexico"],
        f"""
{COMPANY_NAME} has expanded its circular packaging program in Brazil and Mexico, scaling 600ml and 1-liter returnable
glass bottles (RGB). In Brazil, returnable bottles now account for over 45% of traditional trade off-premise sales
for Brahma. Consumers pay only for the liquid when returning an empty bottle, making premium beer more affordable
while preventing thousands of tons of one-way packaging waste from reaching landfills.
"""))

    docs.append(doc(nid(), "Market Research Note: Consumer Economics of Returnable Packaging in Brazil", date(2025, 8, 12),
        "market_research", ["consumer_insights", "returnable_glass", "traditional_trade"], ["Brahma"], ["Brazil"],
        f"""
Household survey data in Sao Paulo and Rio de Janeiro reveals that 68% of frequent beer consumers actively choose
returnable glass bottles due to a 20-30% cost savings compared to one-way aluminum cans. The BEES digital app has
further streamlined bottle returns for mom-and-pop store owners by automating reverse logistics credit tracking.
"""))

    # --- Storyline 10: Belgian Heritage & Craft (Stella Artois & Hoegaarden) ---
    growth_stella_uk, _, _ = yoy_growth(cur, "Stella Artois", "United Kingdom", 2025)
    growth_hoeg_cn, _, _ = yoy_growth(cur, "Hoegaarden", "China", 2025)

    docs.append(doc(nid(), "Hoegaarden Wheat Beer Accelerates Premium Venue Growth Across China and India", date(2025, 4, 8),
        "press_release", ["hoegaarden", "craft_specialty", "asia", "premiumization"], ["Hoegaarden"], ["China", "India"],
        f"""
Hoegaarden, the authentic Belgian wheat beer brewed with coriander and orange peel, is seeing strong double-digit
momentum across premium dining and rooftop venues in Shanghai, Beijing, Mumbai, and Bengaluru. Hoegaarden Rosée
has gained exceptional traction among female consumers seeking fruit-infused, sessionable craft beers.
"Asian consumers appreciate the heritage, unique pour ritual, and refreshing taste profile of Hoegaarden,"
stated the Zone President for Asia Pacific.
"""))

    docs.append(doc(nid(), "Market Research: Craft & Specialty Beer Pairing Trends in APAC", date(2025, 7, 18),
        "market_research", ["craft_specialty", "dining", "pairing", "asia"], ["Hoegaarden", "Corona"], ["China", "India"],
        f"""
Consumer demand for premium and specialty wheat beers has outpaced traditional lagers in Asian metropolitan
cities. In China, Hoegaarden volume in the On-Premise dining sector expanded {growth_hoeg_cn if growth_hoeg_cn else 'over 12'}%
in 2025. Diners actively associate Belgian wheat beers with casual dining and social sharing occasions, allowing
venues to command premium price margins.
"""))

    docs.append(doc(nid(), "Stella Artois Draught Expansion and On-Premise Recovery in the UK", date(2025, 9, 30),
        "earnings_commentary", ["stella_artois", "on_premise", "draught", "united_kingdom"], ["Stella Artois"], ["United Kingdom", "Belgium"],
        f"""
Stella Artois recorded strong performance in the United Kingdom, achieving net revenue growth of
{growth_stella_uk if growth_stella_uk else 'over 8'}% year-over-year in 2025. Draught volume across pubs and hospitality
venues drove growth, supported by the 'Perfect Serve' chalice program and marketing campaigns highlighting Stella's
600-year brewing heritage in Leuven, Belgium. Distribution in the UK reached {latest_acv(cur, 'Stella Artois', 'United Kingdom')}% ACV.
"""))

    docs.append(doc(nid(), "Strategy Memo: Global Megabrands as the Engine of Margin Expansion", date(2025, 10, 15),
        "strategy_memo", ["global_megabrands", "premiumization", "ebitda_growth"], ["Budweiser", "Stella Artois", "Corona", "Michelob ULTRA"], ["United States", "Mexico", "Brazil", "China", "United Kingdom"],
        f"""
EXECUTIVE SUMMARY: Megabrand Strategy 2025-2028
Our four Global Megabrands — Budweiser, Stella Artois, Corona, and Michelob ULTRA — continue to lead our category
expansion. Highlights:
1. Megabrands generated over 55% of consolidated net revenue with an average gross margin premium of 450 basis points.
2. Geographic expansion: Corona outside Mexico grew over 9%, while Michelob ULTRA gained share across North America.
3. Digital integration: BEES algorithmic replenishment prioritized high-margin Megabrands, improving supply chain velocity.
Recommendation: Reallocate 15% of lower-margin regional trade promo toward Megabrand global sponsorship activations.
"""))

    docs.append(doc(nid(), "Annual Corporate Summary: Full-Year Operational and Financial Highlights", date(2025, 12, 10),
        "earnings_commentary", ["annual_review", "global_performance", "summary"], ["Corona", "Budweiser", "Brahma", "Michelob ULTRA", "Stella Artois", "Corona Cero"], ["United States", "Mexico", "Brazil", "China", "United Kingdom", "Belgium", "Canada", "India"],
        f"""
{COMPANY_NAME} delivered resilient results for the year, led by premiumization, digital marketplace expansion,
and disciplined revenue management. Total volume reached millions of hectoliters, with our Beyond Beer portfolio
(led by Corona Cero 0.0%) leading growth rates across all zones. The BEES digital platform expanded beyond
beer into broader B2B distribution, while watershed stewardship initiatives in Mexico and Belgium met target
sustainability benchmarks. Management remains confident in long-term EBITDA growth algorithm of 4-8%.
"""))

    # Write each markdown file
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"documents": []}
    for d in docs:
        filename = f"{d['doc_id']}.md"
        filepath = DOC_DIR / filename
        filepath.write_text(f"# {d['title']}\n\n*{d['date']} — {d['source_type'].replace('_', ' ').title()}*\n\n{d['body']}", encoding="utf-8")
        manifest["documents"].append({
            "doc_id": d["doc_id"],
            "file": filename,
            "title": d["title"],
            "date": d["date"],
            "source_type": d["source_type"],
            "tags": d["tags"],
            "brands": d["brands"],
            "countries": d["countries"],
        })

    (DOC_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(docs)} documents -> {DOC_DIR}")
    conn.close()


if __name__ == "__main__":
    build()
