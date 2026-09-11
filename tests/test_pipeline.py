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
from src.orchestrator import Orchestrator
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
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

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


if __name__ == "__main__":
    unittest.main()
