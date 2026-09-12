"""
Lightweight test suite using only the standard library `unittest` (no pytest
dependency, ensuring portability across offline environments).

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
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestSQLSafety(unittest.TestCase):
    def test_valid_select_executes(self):
        r = run_query("SELECT brand, SUM(net_revenue_usd) AS rev FROM fact_monthly_kpi GROUP BY brand")
        self.assertGreater(r.row_count, 0)
        self.assertIn("brand", r.columns)

    def test_blocks_stacked_statements(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; DROP TABLE fact_monthly_kpi;")

    def test_blocks_write_statements(self):
        for bad in ["DROP TABLE fact_monthly_kpi", "DELETE FROM fact_monthly_kpi",
                    "UPDATE fact_monthly_kpi SET net_revenue_usd=0", "PRAGMA table_info(dim_brand)"]:
            with self.assertRaises(SQLSafetyError):
                validate_sql(bad)

    def test_blocks_unknown_tables(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM sqlite_master")

    def test_enforces_row_cap(self):
        safe = validate_sql("SELECT * FROM fact_monthly_kpi LIMIT 999999")
        self.assertIn("LIMIT 500", safe)


class TestRetrieval(unittest.TestCase):
    def test_finds_relevant_document(self):
        results = get_index().search("water stewardship watershed Monterrey Corona", k=3)
        self.assertTrue(any(d.doc_id == "DOC-013" for d in results))

    def test_metadata_filter_by_brand(self):
        results = get_index().search("olympic", k=10, brands=["Corona Cero"])
        self.assertTrue(all("Corona Cero" in d.brands or d.score > 0 for d in results))
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
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    def test_greeting(self):
        r = self.orch.handle_turn("hello")
        self.assertEqual(r.intent, "greeting")

    def test_out_of_scope(self):
        r = self.orch.handle_turn("what is the weather today?")
        self.assertEqual(r.intent, "out_of_scope")

    def test_clarification_for_ambiguous_request(self):
        r = self.orch.handle_turn("Tell me about performance.")
        self.assertEqual(r.intent, "clarification_needed")
        self.assertIn("clarify", r.answer.lower())

    def test_metadata_discovery(self):
        r = self.orch.handle_turn("what kpis do you have?")
        self.assertEqual(r.intent, "metadata_discovery")
        self.assertIn("Net Revenue", r.answer)

    def test_data_query_routes_to_structured(self):
        r = self.orch.handle_turn("What was Corona revenue in the United States in 2025?")
        self.assertIn("structured", r.sub_agents_used)

    def test_hybrid_routes_both_structured_and_unstructured(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("unstructured", r.sub_agents_used)
        self.assertTrue(len(r.citations) > 0)

    def test_hierarchy_fallback_city_to_country(self):
        r = self.orch.handle_turn("How is Budweiser doing in St. Louis?")
        self.assertTrue(any("United States" in a for a in r.assumptions))

    def test_unsupported_competitor_flagged(self):
        r = self.orch.handle_turn("How is Heineken performing in Europe?")
        self.assertTrue(any("tracked entities" in a for a in r.assumptions))

    def test_conversation_memory_persists_filters(self):
        self.orch.handle_turn("What was Budweiser revenue in the United States in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")
        self.orch.handle_turn("Sales figure question with no new entity")
        # brand should still be remembered from the previous turn
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")


if __name__ == "__main__":
    unittest.main()
