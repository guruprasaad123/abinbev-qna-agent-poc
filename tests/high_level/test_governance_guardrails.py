"""
High-Level Test Suite: 06. Governance, Guardrails & Hierarchy Fallback
Covers Attributes 13, 16, 18, 21, 22, 24, 25:
- Hierarchy-aware fallback (city to country roll-up)
- Unsupported entity and competitor detection
- Metadata queries and schema discovery
- Context-aware follow-up suggestions
- Transparent reporting of assumptions and boundary disclosures
- Answer validation, numeric overlap check, and retry mechanisms
- Graceful degradation for unavailable tools/data
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.config import (
    CITY_TO_COUNTRY, KNOWN_COMPETITORS, ALL_BRANDS, ALL_COUNTRIES,
    ALL_CHANNELS, ALL_KPIS, DATA_START, DATA_END
)


class TestGovernanceGuardrails(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Hierarchy-Aware Fallback (City -> Country) ---
    def test_01_hierarchy_fallback_st_louis_to_usa(self):
        r = self.orch.handle_turn("How is Budweiser doing in St. Louis in 2025?")
        self.assertIn("United States", r.sql_used)
        self.assertTrue(any("St. Louis" in a for a in r.assumptions))
        self.assertTrue(any("United States" in a for a in r.assumptions))

    def test_02_hierarchy_fallback_monterrey_to_mexico(self):
        r = self.orch.handle_turn("What was Corona volume in Monterrey in 2025?")
        self.assertIn("Mexico", r.sql_used)
        self.assertTrue(any("Monterrey" in a for a in r.assumptions))

    def test_03_hierarchy_fallback_leuven_to_belgium(self):
        r = self.orch.handle_turn("Show Stella Artois sales in Leuven in 2025")
        self.assertIn("Belgium", r.sql_used)
        self.assertTrue(any("Leuven" in a for a in r.assumptions))

    def test_04_hierarchy_fallback_brussels_to_belgium(self):
        r = self.orch.handle_turn("Show Stella Artois sales in Brussels in 2025")
        self.assertIn("Belgium", r.sql_used)
        self.assertTrue(any("Brussels" in a for a in r.assumptions))

    def test_05_hierarchy_fallback_shanghai_to_china(self):
        r = self.orch.handle_turn("What was Budweiser performance in Shanghai in 2025?")
        self.assertIn("China", r.sql_used)
        self.assertTrue(any("Shanghai" in a for a in r.assumptions))

    def test_06_hierarchy_fallback_london_to_uk(self):
        r = self.orch.handle_turn("What was Corona volume in London in 2025?")
        self.assertIn("United Kingdom", r.sql_used)
        self.assertTrue(any("London" in a for a in r.assumptions))

    def test_07_hierarchy_fallback_mumbai_to_india(self):
        r = self.orch.handle_turn("How is Budweiser doing in Mumbai in 2025?")
        self.assertIn("India", r.sql_used)
        self.assertTrue(any("Mumbai" in a for a in r.assumptions))

    def test_08_hierarchy_fallback_sao_paulo_to_brazil(self):
        r = self.orch.handle_turn("Show Brahma in Sao Paulo in 2025")
        self.assertIn("Brazil", r.sql_used)
        self.assertTrue(any("Sao Paulo" in a for a in r.assumptions))

    # --- Unsupported Entity & Competitor Detection ---
    def test_09_unsupported_heineken_flagged(self):
        r = self.orch.handle_turn("How is Heineken performing in Europe?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_10_unsupported_carlsberg_flagged(self):
        r = self.orch.handle_turn("What is Carlsberg market share in Europe?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_11_unsupported_molson_coors_flagged(self):
        r = self.orch.handle_turn("Compare Molson Coors in North America")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_12_unsupported_asahi_flagged(self):
        r = self.orch.handle_turn("How is Asahi doing in Asia?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    # --- Metadata Queries & Schema Discovery ---
    def test_13_metadata_discovery_available_kpis(self):
        r = self.orch.handle_turn("What KPIs are available?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Net Revenue", r.answer)
        self.assertIn("Volume", r.answer)
        self.assertIn("Market Share", r.answer)

    def test_14_metadata_discovery_available_brands(self):
        r = self.orch.handle_turn("Which brands do you track?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Corona", r.answer)
        self.assertIn("Budweiser", r.answer)
        self.assertIn("Stella Artois", r.answer)

    def test_15_metadata_discovery_available_countries(self):
        r = self.orch.handle_turn("What countries and markets are available?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("United States", r.answer)
        self.assertIn("Mexico", r.answer)
        self.assertIn("Belgium", r.answer)

    def test_16_metadata_discovery_available_channels(self):
        r = self.orch.handle_turn("What channels are reported?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("BEES & E-commerce", r.answer)
        self.assertIn("On-Premise", r.answer)

    def test_17_metadata_discovery_date_range(self):
        r = self.orch.handle_turn("What time period and dates does your data cover?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("2023", r.answer)
        self.assertIn("2026", r.answer)

    def test_18_metadata_discovery_document_types(self):
        r = self.orch.handle_turn("What document types can I search?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("press release", r.answer.lower())

    # --- Context-Aware Follow-Up Suggestions ---
    def test_19_follow_up_suggestions_populated(self):
        r = self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.assertIsInstance(r.follow_up_suggestions, list)
        self.assertGreater(len(r.follow_up_suggestions), 0)

    def test_20_follow_up_suggestions_relate_to_domain(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        suggestions_str = " ".join(r.follow_up_suggestions).lower()
        # Should suggest volume, channel breakdown, adjacent year, or adjacent market
        self.assertTrue(any(w in suggestions_str for w in ("volume", "channel", "2024", "market", "margin", "share")))

    # --- Transparent Reporting of Assumptions & Limitations ---
    def test_21_assumptions_list_present_on_response(self):
        r = self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.assertIsInstance(r.assumptions, list)

    def test_22_assumptions_capture_hierarchy_rollups(self):
        r = self.orch.handle_turn("How is Corona in Monterrey?")
        self.assertTrue(len(r.assumptions) > 0)
        self.assertTrue(any("Monterrey" in a for a in r.assumptions))

    def test_23_assumptions_capture_competitor_disclosures(self):
        r = self.orch.handle_turn("How is Heineken in Europe?")
        self.assertTrue(len(r.assumptions) > 0)
        self.assertTrue(any("Heineken" in a for a in r.assumptions))

    # --- Answer Validation, Numeric Overlap & Retry Mechanism ---
    def test_24_needs_retry_detects_hallucinated_number(self):
        # When drafted answer has completely made-up numbers not in evidence
        evidence_numbers = {"100", "200"}
        drafted_answer = "The revenue was 99999999 and volume was 88888888."
        needs_retry = self.orch._needs_retry(drafted_answer, evidence_numbers)
        self.assertTrue(needs_retry)

    def test_25_needs_retry_passes_grounded_numbers(self):
        # When numbers match evidence
        evidence_numbers = {"140971636", "1790001", "18.0"}
        drafted_answer = "In 2023, net revenue was 140971636 and volume was 1790001 with 18.0% share."
        needs_retry = self.orch._needs_retry(drafted_answer, evidence_numbers)
        self.assertFalse(needs_retry)

    def test_26_needs_retry_handles_no_numbers_gracefully(self):
        evidence_numbers = set()
        drafted_answer = "Strategic execution was strong across all channels."
        needs_retry = self.orch._needs_retry(drafted_answer, evidence_numbers)
        self.assertFalse(needs_retry)

    def test_27_retried_flag_recorded_in_response(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertIsInstance(r.retried, bool)

    # --- Graceful Degradation ---
    def test_28_graceful_handling_of_unsupported_city(self):
        r = self.orch.handle_turn("Show Budweiser in SmallUnknownVillage12345 in 2025")
        # Should not crash, should return a response
        self.assertIsInstance(r.answer, str)
        self.assertTrue(len(r.answer) > 0)

    def test_29_graceful_handling_of_out_of_range_year(self):
        r = self.orch.handle_turn("What was Corona revenue in 1910?")
        self.assertIsInstance(r.answer, str)

    def test_30_graceful_handling_empty_query_string(self):
        r = self.orch.handle_turn("   ")
        self.assertIsInstance(r.answer, str)

    def test_31_raw_nlu_recorded_on_response(self):
        r = self.orch.handle_turn("What was Corona revenue in Mexico in 2025?")
        self.assertIsInstance(r.raw_nlu, dict)
        self.assertIn("intent", r.raw_nlu)
        self.assertIn("entities", r.raw_nlu)

    def test_32_intermediate_steps_recorded_on_response(self):
        r = self.orch.handle_turn("What was Corona revenue in Mexico in 2025?")
        self.assertIsInstance(r.intermediate_steps, dict)
        self.assertIn("nlu", r.intermediate_steps)
        self.assertIn("sql_used", r.intermediate_steps)


if __name__ == "__main__":
    unittest.main()
