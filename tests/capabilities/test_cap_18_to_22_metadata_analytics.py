"""
Capability Test Suite: Capabilities 18 to 22
- Cap 18: Support metadata queries
- Cap 19: Support multiple KPIs, entities, dimensions, and hierarchical business structures
- Cap 20: Support analytical comparisons across KPIs, entities, periods, and business domains
- Cap 21: Support hierarchy-aware fallback for unsupported entities or granularities
- Cap 22: Support metadata discovery for available KPIs, dimensions, periods, and datasets
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.config import (
    CATEGORY_HIERARCHY, GEO_HIERARCHY, ALL_BRANDS, ALL_COUNTRIES,
    ALL_CHANNELS, ALL_KPIS, CITY_TO_COUNTRY
)


class TestCapabilities18to22(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Capability 18 & 22: Metadata Queries & Schema Discovery ---
    def test_cap18_query_metadata_kpis(self):
        r = self.orch.handle_turn("What KPIs are available?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Net Revenue", r.answer)
        self.assertIn("Volume", r.answer)

    def test_cap18_query_metadata_brands(self):
        r = self.orch.handle_turn("Which brands are available in the system?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Corona", r.answer)
        self.assertIn("Budweiser", r.answer)

    def test_cap22_discovery_lists_brand_categories(self):
        r = self.orch.handle_turn("What data is available in the catalog?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Premium & Above", r.answer)
        self.assertIn("Core & Value", r.answer)
        self.assertIn("Beyond Beer", r.answer)

    def test_cap22_discovery_lists_markets_and_channels(self):
        r = self.orch.handle_turn("What markets and channels are available?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("United States", r.answer)
        self.assertIn("BEES & E-commerce", r.answer)

    def test_cap22_discovery_lists_date_coverage(self):
        r = self.orch.handle_turn("What date range is available?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("2023", r.answer)
        self.assertIn("2026", r.answer)

    # --- Capability 19: Multiple KPIs, Entities, Dimensions & Hierarchies ---
    def test_cap19_category_hierarchy_structure(self):
        self.assertIn("Premium & Above", CATEGORY_HIERARCHY)
        self.assertIn("Core & Value", CATEGORY_HIERARCHY)
        self.assertIn("Beyond Beer", CATEGORY_HIERARCHY)

    def test_cap19_geo_hierarchy_structure(self):
        self.assertIn("North America", GEO_HIERARCHY)
        self.assertIn("Europe", GEO_HIERARCHY)
        self.assertIn("Middle Americas", GEO_HIERARCHY)

    def test_cap19_multi_kpi_query(self):
        r = self.orch.handle_turn("Show volume and revenue for Budweiser in US in 2025")
        self.assertIn("volume", r.sql_used)
        self.assertIn("net_revenue_usd", r.sql_used)

    def test_cap19_multi_dimension_channel_query(self):
        r = self.orch.handle_turn("Show Bud Light sales by channel in US in 2025")
        self.assertIn("channel", r.sql_used.lower())

    # --- Capability 20: Analytical Comparisons ---
    def test_cap20_compare_two_brands(self):
        r = self.orch.handle_turn("Compare Budweiser and Corona in US in 2025")
        self.assertEqual(r.intent, "comparison")
        self.assertIn("brand IN", r.sql_used)
        self.assertIn("Budweiser", r.sql_used)
        self.assertIn("Corona", r.sql_used)

    def test_cap20_compare_two_countries(self):
        r = self.orch.handle_turn("Compare Corona in Mexico vs United States in 2025")
        self.assertIn("Mexico", r.sql_used)

    def test_cap20_compare_two_years(self):
        r = self.orch.handle_turn("Compare Budweiser performance in 2024 vs 2025")
        self.assertEqual(r.intent, "comparison")

    def test_cap20_compare_poor_year_superlative(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("2023", r.answer)
        self.assertIn("9.66%", r.answer)

    # --- Capability 21: Hierarchy-Aware Fallback ---
    def test_cap21_city_st_louis_to_united_states(self):
        r = self.orch.handle_turn("How is Budweiser in St. Louis in 2025?")
        self.assertIn("United States", r.sql_used)
        self.assertTrue(any("St. Louis" in a for a in r.assumptions))

    def test_cap21_city_monterrey_to_mexico(self):
        r = self.orch.handle_turn("How is Corona in Monterrey in 2025?")
        self.assertIn("Mexico", r.sql_used)
        self.assertTrue(any("Monterrey" in a for a in r.assumptions))

    def test_cap21_city_leuven_to_belgium(self):
        r = self.orch.handle_turn("How is Stella Artois in Leuven in 2025?")
        self.assertIn("Belgium", r.sql_used)
        self.assertTrue(any("Leuven" in a for a in r.assumptions))

    def test_cap21_city_brussels_to_belgium(self):
        r = self.orch.handle_turn("How is Stella Artois in Brussels in 2025?")
        self.assertIn("Belgium", r.sql_used)
        self.assertTrue(any("Brussels" in a for a in r.assumptions))

    def test_cap21_city_shanghai_to_china(self):
        r = self.orch.handle_turn("How is Budweiser in Shanghai in 2025?")
        self.assertIn("China", r.sql_used)
        self.assertTrue(any("Shanghai" in a for a in r.assumptions))

    def test_cap21_city_mumbai_to_india(self):
        r = self.orch.handle_turn("How is Budweiser in Mumbai in 2025?")
        self.assertIn("India", r.sql_used)
        self.assertTrue(any("Mumbai" in a for a in r.assumptions))

    def test_cap21_city_sao_paulo_to_brazil(self):
        r = self.orch.handle_turn("How is Brahma in Sao Paulo in 2025?")
        self.assertIn("Brazil", r.sql_used)
        self.assertTrue(any("Sao Paulo" in a for a in r.assumptions))

    def test_cap21_unsupported_competitor_flagged(self):
        r = self.orch.handle_turn("How is Heineken performing in Europe?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))


if __name__ == "__main__":
    unittest.main()
