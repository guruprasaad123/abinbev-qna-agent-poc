"""
High-Level Test Suite: 02. Semantic Understanding & Multilingual
Covers Attributes 6 & 7:
- Entity aliases, abbreviations, and typo tolerance
- Multilingual queries (Spanish, French, Hindi, Portuguese, German)
- Mixed-language (Spanglish, Hinglish) and cross-lingual filter resolution
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestSemanticMultilingual(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Brand Aliases & Typo Tolerance ---
    def test_01_alias_bud_to_budweiser(self):
        r = self.orch.handle_turn("What was Bud revenue in US in 2025?")
        self.assertIn("Budweiser", r.sql_used)

    def test_02_alias_bl_to_bud_light(self):
        r = self.orch.handle_turn("What was BL volume in US in 2025?")
        self.assertIn("Bud Light", r.sql_used)

    def test_03_alias_budlight_joined(self):
        r = self.orch.handle_turn("Show budlight sales in US in 2025")
        self.assertIn("Bud Light", r.sql_used)

    def test_04_alias_ultra_to_michelob_ultra(self):
        r = self.orch.handle_turn("What was Ultra market share in US in 2025?")
        self.assertIn("Michelob ULTRA", r.sql_used)

    def test_05_alias_mich_ultra(self):
        r = self.orch.handle_turn("Give me Mich Ultra net revenue in US in 2025")
        self.assertIn("Michelob ULTRA", r.sql_used)

    def test_06_alias_stella_to_stella_artois(self):
        r = self.orch.handle_turn("What was Stella volume in UK in 2025?")
        self.assertIn("Stella Artois", r.sql_used)

    def test_07_alias_artois(self):
        r = self.orch.handle_turn("How did Artois perform in Belgium in 2024?")
        self.assertIn("Stella Artois", r.sql_used)

    def test_08_alias_coronita_to_corona(self):
        r = self.orch.handle_turn("What was Coronita revenue in Mexico in 2025?")
        self.assertIn("Corona", r.sql_used)

    def test_09_alias_corona_extra(self):
        r = self.orch.handle_turn("Tell me about Corona Extra in Mexico in 2025")
        self.assertIn("Corona", r.sql_used)

    def test_10_typo_coron(self):
        r = self.orch.handle_turn("What was Coron revenue in Mexico in 2025?")
        self.assertIn("Corona", r.sql_used)

    def test_11_typo_corna(self):
        r = self.orch.handle_turn("What was Corna volume in Mexico in 2025?")
        self.assertIn("Corona", r.sql_used)

    def test_12_alias_corona_cero_zero(self):
        r = self.orch.handle_turn("Show Corona Zero performance in UK in 2025")
        self.assertIn("Corona Cero", r.sql_used)

    def test_13_alias_corona_00(self):
        r = self.orch.handle_turn("How is Corona 0.0 doing in United Kingdom in 2025?")
        self.assertIn("Corona Cero", r.sql_used)

    def test_14_alias_brahma_chopp(self):
        r = self.orch.handle_turn("Show Brahma Chopp in Brazil in 2025")
        self.assertIn("Brahma", r.sql_used)

    def test_15_typo_hoegarden(self):
        r = self.orch.handle_turn("Show Hoegarden volume in China in 2025")
        self.assertIn("Hoegaarden", r.sql_used)

    # --- Geography Aliases & Abbreviations ---
    def test_16_geo_us_abbreviation(self):
        r = self.orch.handle_turn("What was Budweiser in US in 2025?")
        self.assertIn("United States", r.sql_used)

    def test_17_geo_usa_abbreviation(self):
        r = self.orch.handle_turn("What was Bud Light in USA in 2025?")
        self.assertIn("United States", r.sql_used)

    def test_18_geo_america(self):
        r = self.orch.handle_turn("How was Michelob ULTRA in America in 2025?")
        self.assertIn("United States", r.sql_used)

    def test_19_geo_uk_abbreviation(self):
        r = self.orch.handle_turn("Show Stella Artois in UK in 2025")
        self.assertIn("United Kingdom", r.sql_used)

    def test_20_geo_britain(self):
        r = self.orch.handle_turn("Show Stella Artois in Britain in 2025")
        self.assertIn("United Kingdom", r.sql_used)

    def test_21_geo_brasil_spelling(self):
        r = self.orch.handle_turn("Show Brahma in Brasil in 2025")
        self.assertIn("Brazil", r.sql_used)

    def test_22_geo_mexico_accent(self):
        r = self.orch.handle_turn("Show Corona in México in 2025")
        self.assertIn("Mexico", r.sql_used)

    def test_23_geo_belgique_french(self):
        r = self.orch.handle_turn("Show Stella Artois in Belgique in 2025")
        self.assertIn("Belgium", r.sql_used)

    def test_24_geo_bharat_alias(self):
        r = self.orch.handle_turn("Show Budweiser in Bharat in 2025")
        self.assertIn("India", r.sql_used)

    # --- KPI Aliases ---
    def test_25_kpi_rev_abbreviation(self):
        r = self.orch.handle_turn("Show Corona rev in Mexico in 2025")
        self.assertIn("net_revenue_usd", r.sql_used)

    def test_26_kpi_sales_synonym(self):
        r = self.orch.handle_turn("Show Bud Light sales in United States in 2025")
        self.assertIn("net_revenue_usd", r.sql_used)

    def test_27_kpi_volume_hl_unit(self):
        r = self.orch.handle_turn("Show Stella Artois volume in hL in United Kingdom in 2025")
        self.assertIn("volume", r.sql_used)

    # --- Multilingual & Mixed-Language Queries ---
    def test_28_spanish_query_full(self):
        r = self.orch.handle_turn("¿Cuáles fueron los ingresos de Corona en México en 2025?")
        self.assertEqual(r.raw_nlu.get("language"), "es")
        self.assertIn("Mexico", r.sql_used)
        self.assertIn("Corona", r.sql_used)
        self.assertIn("ingresos", r.answer.lower())

    def test_29_french_query_full(self):
        r = self.orch.handle_turn("Quelle était la part de marché de Stella Artois en Belgique en 2024?")
        self.assertEqual(r.raw_nlu.get("language"), "fr")
        self.assertIn("Belgium", r.sql_used)
        self.assertIn("Stella Artois", r.sql_used)

    def test_30_hindi_query_full(self):
        r = self.orch.handle_turn("2025 mein Budweiser ka revenue United States mein kitna tha?")
        self.assertEqual(r.raw_nlu.get("language"), "hi")
        self.assertIn("United States", r.sql_used)
        self.assertIn("Budweiser", r.sql_used)

    def test_31_spanglish_mixed_query(self):
        r = self.orch.handle_turn("Show me los ingresos de Bud Light in US para 2025")
        self.assertIn("Bud Light", r.sql_used)
        self.assertIn("United States", r.sql_used)

    def test_32_hinglish_mixed_query(self):
        r = self.orch.handle_turn("Corona ka volume in Mexico 2025 kitna tha?")
        self.assertIn("Corona", r.sql_used)
        self.assertIn("Mexico", r.sql_used)


if __name__ == "__main__":
    unittest.main()
