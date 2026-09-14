"""
Lightweight test suite using only the standard library `unittest` (no pytest
dependency, since this needs to run in any environment including offline
ones with a restricted package mirror -- see docs/DESIGN_DECISIONS.md).

Run with:  python3 -m unittest discover -s tests -v
These all run with MockLLMClient -- zero cost, zero network, no API key
needed -- so they can gate a CI pipeline even without provider credentials.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.sql_tool import run_query, validate_sql, SQLSafetyError
from src.tools.retrieval_tool import get_index
from src.tools.code_tool import run_code
from src.tools.embedding_tool import cosine_similarity, load_cached_document_embeddings
from src.orchestrator import Orchestrator, _classify_complexity
from src.llm_client import MockLLMClient


class TestSQLSafety(unittest.TestCase):
    def test_valid_select_executes(self):
        r = run_query("SELECT zone, SUM(revenue_usd_m) AS rev FROM fact_kpi WHERE grain='quarterly' GROUP BY zone")
        self.assertGreater(r.row_count, 0)
        self.assertIn("zone", r.columns)

    def test_blocks_stacked_statements(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_kpi; DROP TABLE fact_kpi;")

    def test_blocks_write_statements(self):
        for bad in ["DROP TABLE fact_kpi", "DELETE FROM fact_kpi",
                    "UPDATE fact_kpi SET revenue_usd_m=0", "PRAGMA table_info(dim_zone_country)"]:
            with self.assertRaises(SQLSafetyError):
                validate_sql(bad)

    def test_blocks_unknown_tables(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM sqlite_master")

    def test_enforces_row_cap(self):
        safe = validate_sql("SELECT * FROM fact_kpi LIMIT 999999")
        self.assertIn("LIMIT 500", safe)


class TestRetrieval(unittest.TestCase):
    def test_finds_relevant_document(self):
        results = get_index().search("Corona Michelob Ultra megabrand revenue growth", k=3)
        self.assertTrue(any(d.doc_id == "DOC-012" for d in results))

    def test_metadata_filter_by_brand(self):
        results = get_index().search("brand performance", k=10, brands=["Corona"])
        self.assertTrue(all("Corona" in d.brands or d.score > 0 for d in results))
        self.assertTrue(len(results) > 0)


class TestCodeSandbox(unittest.TestCase):
    def test_runs_simple_arithmetic(self):
        r = run_code("result = 2 ** 10")
        self.assertTrue(r.ok)
        self.assertEqual(r.result, 1024)

    def test_blocks_import(self):
        r = run_code("import os\nresult = os.getcwd()")
        self.assertFalse(r.ok)

    def test_blocks_file_access(self):
        r = run_code("result = open('/etc/passwd').read()")
        self.assertFalse(r.ok)


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_classify=MockLLMClient(), llm_generate=MockLLMClient(),
                                  llm_synthesize=MockLLMClient())

    def test_greeting(self):
        r = self.orch.handle_turn("hello")
        self.assertEqual(r.intent, "greeting")

    def test_out_of_scope(self):
        r = self.orch.handle_turn("what is the weather today?")
        self.assertEqual(r.intent, "out_of_scope")

    def test_metadata_discovery(self):
        r = self.orch.handle_turn("what kpis do you have?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Revenue", r.answer)

    def test_data_query_routes_to_structured(self):
        r = self.orch.handle_turn("What was North America revenue in Q1 2024?")
        self.assertIn("structured", r.sub_agents_used)

    def test_hybrid_routes_both_structured_and_unstructured(self):
        r = self.orch.handle_turn("Why did Corona grow in Mexico, any press releases?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("unstructured", r.sub_agents_used)
        self.assertTrue(len(r.citations) > 0)

    def test_hierarchy_fallback_country_to_zone(self):
        r = self.orch.handle_turn("How is revenue in Brazil doing?")
        self.assertTrue(any("South America" in a for a in r.assumptions))

    def test_unsupported_competitor_flagged(self):
        r = self.orch.handle_turn("How is Heineken performing?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_conversation_memory_persists_filters(self):
        self.orch.handle_turn("What was North America revenue in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("zone"), "North America")
        self.orch.handle_turn("Revenue figure question with no new entity")
        # zone should still be remembered from the previous turn
        self.assertEqual(self.orch.memory.active_filters.get("zone"), "North America")


class TestSynthesisComplexityRouting(unittest.TestCase):
    """_classify_complexity is pure/deterministic -- no LLM call needed to
    test it, unlike the rest of the synthesis-tier routing feature."""

    def test_single_entity_single_subagent_is_simple(self):
        nlu = {"intent": "data_query", "entities": {"zones": ["North America"], "kpis": ["revenue_usd_m"]}}
        self.assertEqual(_classify_complexity(nlu, ["structured"]), "simple")

    def test_comparison_intent_is_moderate(self):
        nlu = {"intent": "comparison", "entities": {"zones": ["North America"], "kpis": ["revenue_usd_m"]}}
        self.assertEqual(_classify_complexity(nlu, ["structured"]), "moderate")

    def test_two_subagents_is_moderate(self):
        nlu = {"intent": "data_query", "entities": {"zones": ["North America"], "kpis": ["revenue_usd_m"]}}
        self.assertEqual(_classify_complexity(nlu, ["structured", "unstructured"]), "moderate")

    def test_multi_zone_entity_is_moderate(self):
        nlu = {"intent": "data_query", "entities": {"zones": ["North America", "EMEA"], "kpis": ["revenue_usd_m"]}}
        self.assertEqual(_classify_complexity(nlu, ["structured"]), "moderate")

    def test_three_or_more_subagents_is_complex(self):
        nlu = {"intent": "data_query", "entities": {}}
        self.assertEqual(_classify_complexity(nlu, ["structured", "unstructured", "web"]), "complex")

    def test_retry_always_escalates_to_complex(self):
        nlu = {"intent": "data_query", "entities": {"zones": ["North America"], "kpis": ["revenue_usd_m"]}}
        self.assertEqual(_classify_complexity(nlu, ["structured"], is_retry=True), "complex")


class TestEmbeddingGracefulDegradation(unittest.TestCase):
    """src/tools/embedding_tool.py's deterministic pieces -- the actual
    fastembed model call is NOT exercised here (that needs the optional
    `embeddings` extra installed); what's tested is that retrieval behaves
    correctly with or without it, never requiring it. See
    tests/live/cases/cap12_hybrid_retrieval.py for a live-model exercise of
    the actual semantic signal."""

    def test_cosine_similarity_identical_vectors_is_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=6)

    def test_cosine_similarity_orthogonal_vectors_is_zero(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, places=6)

    def test_cosine_similarity_opposite_vectors_is_negative_one(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0, places=6)

    def test_cosine_similarity_handles_zero_vector_without_crashing(self):
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_mismatched_doc_id_set_returns_none_not_a_stale_cache(self):
        # data/unstructured/embeddings_cache.json (if present) covers the
        # real 15-doc corpus -- asking for a different/incomplete doc_id set
        # must be treated as "cache doesn't cover this," not silently used.
        self.assertIsNone(load_cached_document_embeddings(["DOC-001"]))

    def test_document_index_search_works_without_embeddings_available(self):
        """The real, end-to-end guarantee: search() must never require
        fastembed to be installed or the cache to exist -- retrieval already
        worked this way before embeddings were added, and must keep working
        this way regardless of what's installed in a given environment."""
        idx = get_index()
        results = idx.search("What was North America's revenue in Q1 2024?", k=3)
        self.assertTrue(len(results) > 0)


if __name__ == "__main__":
    unittest.main()
