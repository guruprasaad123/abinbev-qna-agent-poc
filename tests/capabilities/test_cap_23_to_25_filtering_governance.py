"""
Capability Test Suite: Capabilities 23 to 25
- Cap 23: Support document filtering using metadata, tags, and recency
- Cap 24: Support transparent reporting of assumptions, data availability, and system limitations
- Cap 25: Support graceful handling of unsupported or unavailable requests
"""
import unittest
from src.tools.retrieval_tool import get_index
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestCapabilities23to25(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
        self.index = get_index()

    # --- Capability 23: Document Filtering by Metadata, Tags & Recency ---
    def test_cap23_filter_documents_by_brand(self):
        results = self.index.search("", k=5, brands=["Corona Cero"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Corona Cero" in d.brands for d in results))

    def test_cap23_filter_documents_by_country(self):
        results = self.index.search("", k=5, countries=["Mexico"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Mexico" in d.countries for d in results))

    def test_cap23_filter_documents_by_source_type(self):
        results = self.index.search("", k=5, source_types=["press_release"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all(d.source_type == "press_release" for d in results))

    def test_cap23_filter_documents_by_tag(self):
        results = self.index.search("", k=4, tags=["sustainability"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("sustainability" in d.tags for d in results))

    def test_cap23_recency_boost_ranks_recent_docs_higher(self):
        r_rec = self.index.search("growth", k=5, recency_weight=1.5)
        r_old = self.index.search("growth", k=5, recency_weight=0.0)
        self.assertTrue(len(r_rec) > 0)
        self.assertTrue(len(r_old) > 0)

    # --- Capability 24: Transparent Reporting of Assumptions & Limitations ---
    def test_cap24_assumptions_list_on_response(self):
        r = self.orch.handle_turn("What was Corona revenue in Monterrey in 2025?")
        self.assertIsInstance(r.assumptions, list)
        self.assertTrue(len(r.assumptions) > 0)

    def test_cap24_assumption_surfaces_city_rollup(self):
        r = self.orch.handle_turn("What was Stella Artois sales in Leuven in 2025?")
        self.assertTrue(any("Leuven" in a for a in r.assumptions))
        self.assertTrue(any("Belgium" in a for a in r.assumptions))

    def test_cap24_assumption_surfaces_competitor_boundary(self):
        r = self.orch.handle_turn("How is Heineken performing in Europe?")
        self.assertTrue(any("Heineken" in a for a in r.assumptions))
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_cap24_assumption_surfaces_ytd_partial_period(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("2026", r.answer)

    def test_cap24_developer_steps_audit_trail(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertIn("nlu", r.intermediate_steps)
        self.assertIn("needed_subagents", r.intermediate_steps)

    # --- Capability 25: Graceful Handling of Unsupported / Unavailable Requests ---
    def test_cap25_unsupported_entity_does_not_crash(self):
        r = self.orch.handle_turn("How is Tesla performing in sales?")
        self.assertIsInstance(r.answer, str)
        self.assertTrue(len(r.answer) > 0)

    def test_cap25_unsupported_city_falls_back_gracefully(self):
        r = self.orch.handle_turn("How is Budweiser in NonExistentVillage999 in 2025?")
        self.assertIsInstance(r.answer, str)

    def test_cap25_out_of_scope_graceful_message(self):
        r = self.orch.handle_turn("What is the weather in London today?")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertIn("outside what i can help with", r.answer.lower())

    def test_cap25_empty_input_graceful_handling(self):
        r = self.orch.handle_turn("")
        self.assertIsInstance(r.answer, str)

    def test_cap25_whitespace_only_handling(self):
        r = self.orch.handle_turn("    \n\t  ")
        self.assertIsInstance(r.answer, str)

    def test_cap25_random_gibberish_handling(self):
        r = self.orch.handle_turn("asdkfjhalksjdfhlaskjdfh")
        self.assertIsInstance(r.answer, str)


if __name__ == "__main__":
    unittest.main()
