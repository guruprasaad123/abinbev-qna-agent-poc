"""
Capability Test Suite: Capabilities 06 to 08
- Cap 06: Support semantic understanding, including aliases, abbreviations, and typo correction
- Cap 07: Support multilingual and mixed-language queries
- Cap 08: Support conversation context preservation across interactions
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestCapabilities06to08(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Capability 6: Semantic Understanding (Aliases, Abbreviations, Typos) ---
    def test_cap06_brand_alias_bud_to_budweiser(self):
        r = self.orch.handle_turn("Show Bud revenue in US in 2025")
        self.assertIn("Budweiser", r.sql_used)

    def test_cap06_brand_alias_bl_to_bud_light(self):
        r = self.orch.handle_turn("Show BL volume in US in 2025")
        self.assertIn("Bud Light", r.sql_used)

    def test_cap06_brand_alias_stella(self):
        r = self.orch.handle_turn("Show Stella volume in UK in 2025")
        self.assertIn("Stella Artois", r.sql_used)

    def test_cap06_brand_alias_ultra(self):
        r = self.orch.handle_turn("Show Ultra share in US in 2025")
        self.assertIn("Michelob ULTRA", r.sql_used)

    def test_cap06_brand_alias_cero(self):
        r = self.orch.handle_turn("Show Cero sales in UK in 2025")
        self.assertIn("Corona Cero", r.sql_used)

    def test_cap06_typo_coron(self):
        r = self.orch.handle_turn("What was Coron sales in Mexico in 2025?")
        self.assertIn("Corona", r.sql_used)

    def test_cap06_typo_hoegarden(self):
        r = self.orch.handle_turn("What was Hoegarden volume in China in 2025?")
        self.assertIn("Hoegaarden", r.sql_used)

    def test_cap06_geo_abbreviation_us(self):
        r = self.orch.handle_turn("Budweiser in US in 2025")
        self.assertIn("United States", r.sql_used)

    def test_cap06_geo_abbreviation_uk(self):
        r = self.orch.handle_turn("Stella Artois in UK in 2025")
        self.assertIn("United Kingdom", r.sql_used)

    def test_cap06_kpi_abbreviation_rev(self):
        r = self.orch.handle_turn("Corona rev in Mexico in 2025")
        self.assertIn("net_revenue_usd", r.sql_used)

    def test_cap06_kpi_abbreviation_vol(self):
        r = self.orch.handle_turn("Bud Light vol in US in 2025")
        self.assertIn("volume", r.sql_used)

    # --- Capability 7: Multilingual & Mixed-Language Queries ---
    def test_cap07_spanish_query_resolution(self):
        r = self.orch.handle_turn("¿Cuáles fueron los ingresos de Corona en México en 2025?")
        self.assertEqual(r.raw_nlu.get("language"), "es")
        self.assertIn("Corona", r.sql_used)
        self.assertIn("Mexico", r.sql_used)

    def test_cap07_french_query_resolution(self):
        r = self.orch.handle_turn("Quelle était la part de marché de Stella Artois en Belgique en 2024?")
        self.assertEqual(r.raw_nlu.get("language"), "fr")
        self.assertIn("Stella Artois", r.sql_used)
        self.assertIn("Belgium", r.sql_used)

    def test_cap07_hindi_query_resolution(self):
        r = self.orch.handle_turn("2025 mein Budweiser ka revenue United States mein kitna tha?")
        self.assertEqual(r.raw_nlu.get("language"), "hi")
        self.assertIn("Budweiser", r.sql_used)
        self.assertIn("United States", r.sql_used)

    def test_cap07_spanglish_mixed_language(self):
        r = self.orch.handle_turn("Dame el volume de Bud Light in US for 2025")
        self.assertIn("Bud Light", r.sql_used)
        self.assertIn("United States", r.sql_used)

    def test_cap07_hinglish_mixed_language(self):
        r = self.orch.handle_turn("Corona ka net revenue in Mexico 2025 batao")
        self.assertIn("Corona", r.sql_used)
        self.assertIn("Mexico", r.sql_used)

    # --- Capability 8: Conversation Context Preservation ---
    def test_cap08_preserves_active_filters_brand(self):
        self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")

    def test_cap08_preserves_active_filters_country(self):
        self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Mexico")

    def test_cap08_preserves_active_filters_period(self):
        self.orch.handle_turn("What was Corona in Mexico in 2024?")
        self.assertEqual(self.orch.memory.active_filters.get("period"), "2024")

    def test_cap08_context_block_contains_active_entities(self):
        self.orch.handle_turn("What was Stella Artois in Belgium in 2025?")
        ctx = self.orch.memory.context_block()
        self.assertIn("Stella Artois", ctx)
        self.assertIn("Belgium", ctx)

    def test_cap08_preserves_turn_history(self):
        self.orch.handle_turn("Turn 1 message")
        self.orch.handle_turn("Turn 2 message")
        self.assertEqual(len(self.orch.memory.raw_turns), 4)

    def test_cap08_clears_filters_when_requested(self):
        self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.orch.memory.clear_filters()
        self.assertEqual(len(self.orch.memory.active_filters), 0)

    def test_cap08_company_wide_clears_stale_brand(self):
        self.orch.handle_turn("What was Budweiser in US in 2025?")
        r2 = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertNotIn("brand='Budweiser'", r2.sql_used)


if __name__ == "__main__":
    unittest.main()
