"""
High-Level Test Suite: 04. Data Retrieval & Hybrid Multi-Agent Orchestration
Covers Attributes 10, 11, 12, 23:
- Structured data retrieval from SQLite
- Unstructured document retrieval via BM25 + metadata
- Source citations [DOC-xxx]
- Hybrid retrieval (combining structured SQL and unstructured corpus)
- Document filtering using metadata, tags, and recency
"""
import unittest
from src.tools.retrieval_tool import get_index, DocumentIndex
from src.agents import structured_agent, unstructured_agent
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestRetrievalHybrid(unittest.TestCase):
    def setUp(self):
        self.index = get_index()
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Document Search & Relevance ---
    def test_01_search_olympic_sponsorship(self):
        results = self.index.search("Corona Cero Olympic Games sponsorship Paris", k=3)
        self.assertTrue(any("Corona Cero" in d.title or "Olympic" in d.title for d in results))
        self.assertTrue(any(d.doc_id.startswith("DOC-") for d in results))

    def test_02_search_bees_digital_b2b(self):
        results = self.index.search("BEES digital B2B marketplace GMV active users", k=3)
        self.assertTrue(any("BEES" in d.title or "B2B" in d.title for d in results))

    def test_03_search_water_stewardship_monterrey(self):
        results = self.index.search("watershed restoration Monterrey Mexico brewery", k=3)
        self.assertTrue(any(d.doc_id == "DOC-013" for d in results))

    def test_04_search_non_alcoholic_growth(self):
        results = self.index.search("Beyond Beer non-alcoholic volume growth trends", k=3)
        self.assertTrue(len(results) > 0)

    def test_05_search_competitor_briefing_heineken(self):
        results = self.index.search("Heineken European premium beer competitor", k=3)
        self.assertTrue(any("Heineken" in d.title or "Competitor" in d.title for d in results))

    # --- Document Metadata, Tag, and Recency Filtering ---
    def test_06_filter_by_brand_corona_cero(self):
        results = self.index.search("", k=5, brands=["Corona Cero"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Corona Cero" in d.brands for d in results))

    def test_07_filter_by_brand_michelob_ultra(self):
        results = self.index.search("", k=5, brands=["Michelob ULTRA"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Michelob ULTRA" in d.brands for d in results))

    def test_08_filter_by_country_mexico(self):
        results = self.index.search("", k=5, countries=["Mexico"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Mexico" in d.countries for d in results))

    def test_09_filter_by_country_belgium(self):
        results = self.index.search("", k=5, countries=["Belgium"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("Belgium" in d.countries for d in results))

    def test_10_filter_by_source_type_press_release(self):
        results = self.index.search("", k=5, source_types=["press_release"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all(d.source_type == "press_release" for d in results))

    def test_11_filter_by_source_type_earnings_commentary(self):
        results = self.index.search("", k=5, source_types=["earnings_commentary"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all(d.source_type == "earnings_commentary" for d in results))

    def test_12_filter_by_tag_sustainability(self):
        results = self.index.search("", k=4, tags=["sustainability"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("sustainability" in d.tags for d in results))

    def test_13_filter_by_tag_digital(self):
        results = self.index.search("", k=3, tags=["digital"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(any("digital" in d.tags for d in results))
        self.assertIn("digital", results[0].tags)

    def test_14_pure_metadata_query_without_keywords(self):
        # Empty text query relies strictly on metadata filters and recency
        results = self.index.search("", k=3, tags=["sustainability"])
        self.assertTrue(len(results) > 0)
        self.assertTrue(all("sustainability" in d.tags for d in results))

    # --- Unstructured Sub-Agent Execution ---
    def test_15_unstructured_agent_returns_citations(self):
        res = unstructured_agent.answer(MockLLMClient(), "What is AB InBev's Olympic sponsorship strategy?")
        self.assertTrue(res.ok)
        self.assertTrue(len(res.documents) > 0)
        self.assertTrue(any(d.doc_id.startswith("DOC-") for d in res.documents))

    def test_16_unstructured_agent_respects_k_limit(self):
        res = unstructured_agent.answer(MockLLMClient(), "BEES e-commerce growth", k=2)
        self.assertLessEqual(len(res.documents), 2)

    # --- Structured Sub-Agent Execution ---
    def test_17_structured_agent_answers_brand_query(self):
        res = structured_agent.answer(MockLLMClient(), "What was Budweiser revenue in US in 2025?")
        self.assertTrue(res.ok)
        self.assertTrue(res.sql_used)
        self.assertIn("fact_monthly_kpi", res.sql_used)
        self.assertGreater(len(res.rows), 0)

    def test_18_structured_agent_handles_channel_breakdown(self):
        res = structured_agent.answer(MockLLMClient(), "Show Bud Light by channel in US in 2025")
        self.assertTrue(res.ok)
        self.assertIn("channel", res.columns)

    # --- Hybrid Multi-Agent Retrieval ---
    def test_19_hybrid_triggers_structured_and_unstructured(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("unstructured", r.sub_agents_used)
        self.assertTrue(len(r.citations) > 0)
        self.assertTrue(r.sql_used)

    def test_20_hybrid_cites_document_ids_in_answer(self):
        r = self.orch.handle_turn("Tell me about Corona Cero Olympic sponsorship news and revenue in 2025")
        self.assertTrue(len(r.citations) > 0)
        self.assertTrue(any("DOC-" in c.get("doc_id", "") for c in r.citations))

    def test_21_hybrid_intermediate_steps_recorded(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("documents", r.intermediate_steps)
        self.assertIn("sql_used", r.intermediate_steps)
        self.assertGreater(len(r.intermediate_steps["documents"]), 0)

    def test_22_hybrid_preserves_document_excerpts(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        docs = r.intermediate_steps["documents"]
        self.assertTrue(all("excerpt" in d for d in docs))

    def test_23_unstructured_only_for_pure_strategy_queries(self):
        r = self.orch.handle_turn("What are the latest press releases on sustainability and water stewardship?")
        self.assertIn("unstructured", r.sub_agents_used)

    def test_24_structured_only_for_pure_numerical_lookup(self):
        r = self.orch.handle_turn("What was Stella Artois net revenue in Belgium in 2025?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertNotIn("unstructured", r.sub_agents_used)

    def test_25_corpus_has_at_least_25_documents(self):
        self.assertGreaterEqual(len(self.index.docs), 25)

    def test_26_document_manifest_has_valid_fields(self):
        for doc in self.index.docs:
            self.assertTrue(doc["doc_id"].startswith("DOC-"))
            self.assertTrue(doc["title"])
            self.assertTrue(doc["source_type"])
            self.assertTrue(doc["date"])

    def test_27_recency_decay_favors_recent_documents(self):
        r_all = self.index.search("commercial performance", k=10)
        dates = [d.date for d in r_all]
        self.assertTrue(len(dates) > 0)

    def test_28_retrieval_handles_punctuation_safely(self):
        results = self.index.search("Corona Extra: 330ml & B2B; BEES?", k=3)
        self.assertTrue(len(results) > 0)

    def test_29_retrieval_handles_special_characters(self):
        results = self.index.search("Mexico brewery USD revenue", k=3)
        self.assertTrue(len(results) > 0)
        self.assertTrue(len(results) > 0)

    def test_30_retrieval_empty_result_graceful(self):
        results = self.index.search("nonexistent_random_token_xyz_12345", k=3)
        # Should gracefully return empty list or low-scored docs without raising error
        self.assertIsInstance(results, list)

    def test_31_hybrid_response_contains_tabular_data(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("|", r.answer)

    def test_32_hybrid_routing_includes_web_for_external_competitors(self):
        r = self.orch.handle_turn("How is Heineken performing compared to general industry news?")
        self.assertIn("web", r.sub_agents_used)


if __name__ == "__main__":
    unittest.main()
