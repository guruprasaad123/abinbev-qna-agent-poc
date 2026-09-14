"""
Capability Test Suite: Capabilities 09 to 12
- Cap 09: Support secure access with SQL safety controls
- Cap 10: Support structured and unstructured data retrieval from multiple data sources
- Cap 11: Support document retrieval with source citations
- Cap 12: Support hybrid data retrieval
"""
import unittest
from src.tools.sql_tool import run_query, validate_sql, SQLSafetyError
from src.tools.retrieval_tool import get_index
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestCapabilities09to12(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())
        self.index = get_index()

    # --- Capability 9: Secure Access with SQL Safety Controls ---
    def test_cap09_valid_select_executes(self):
        r = run_query("SELECT brand, SUM(net_revenue_usd) AS rev FROM fact_monthly_kpi GROUP BY brand LIMIT 5")
        self.assertGreater(r.row_count, 0)
        self.assertIn("rev", r.columns)

    def test_cap09_block_stacked_statement(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; DROP TABLE dim_brand;")

    def test_cap09_block_drop_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("DROP TABLE fact_monthly_kpi")

    def test_cap09_block_delete(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("DELETE FROM fact_monthly_kpi WHERE 1=1")

    def test_cap09_block_insert(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("INSERT INTO dim_brand (brand) VALUES ('Hacked')")

    def test_cap09_block_update(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("UPDATE fact_monthly_kpi SET net_revenue_usd = 0")

    def test_cap09_block_unknown_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM secret_passwords")

    def test_cap09_row_cap_enforced(self):
        safe = validate_sql("SELECT brand FROM fact_monthly_kpi LIMIT 999999")
        self.assertIn("LIMIT 500", safe)

    # --- Capability 10: Structured and Unstructured Retrieval ---
    def test_cap10_structured_retrieval_fact_table(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertTrue(r.sql_used)

    def test_cap10_unstructured_retrieval_document_corpus(self):
        r = self.orch.handle_turn("What are the latest press releases on water stewardship and sustainability?")
        self.assertIn("unstructured", r.sub_agents_used)
        self.assertTrue(len(r.citations) > 0)

    def test_cap10_structured_source_sqlite(self):
        r = run_query("SELECT COUNT(*) AS c FROM fact_monthly_kpi")
        self.assertGreater(r.rows[0][0], 10000)

    def test_cap10_unstructured_source_corpus_size(self):
        self.assertGreaterEqual(len(self.index.docs), 25)

    # --- Capability 11: Document Retrieval with Source Citations ---
    def test_cap11_retrieval_returns_doc_ids(self):
        results = self.index.search("Corona Cero Olympic Games", k=3)
        self.assertTrue(any(d.doc_id.startswith("DOC-") for d in results))

    def test_cap11_retrieval_metadata_complete(self):
        results = self.index.search("BEES marketplace", k=3)
        for doc in results:
            self.assertTrue(doc.doc_id)
            self.assertTrue(doc.title)
            self.assertTrue(doc.date)
            self.assertTrue(doc.source_type)

    def test_cap11_citations_in_orchestrator_response(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertTrue(len(r.citations) > 0)
        self.assertTrue(any("DOC-" in c.get("doc_id", "") for c in r.citations))

    def test_cap11_inline_citations_in_answer(self):
        r = self.orch.handle_turn("What are the latest sustainability press releases on watershed protection?")
        self.assertIn("[DOC-", r.answer)

    # --- Capability 12: Hybrid Data Retrieval ---
    def test_cap12_hybrid_dispatches_structured_and_unstructured(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("unstructured", r.sub_agents_used)

    def test_cap12_hybrid_synthesizes_both_data_types(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        # Has table from structured data
        self.assertIn("|", r.answer)
        # Has citations from unstructured data
        self.assertTrue(len(r.citations) > 0)

    def test_cap12_hybrid_steps_contain_sql_and_docs(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        self.assertIn("sql_used", r.intermediate_steps)
        self.assertIn("documents", r.intermediate_steps)

    def test_cap12_hybrid_preserves_both_evidence_blocks(self):
        r = self.orch.handle_turn("Why did Corona Cero grow in the United Kingdom, any press releases?")
        docs = r.intermediate_steps.get("documents", [])
        sql = r.intermediate_steps.get("sql_used", "")
        self.assertTrue(len(docs) > 0)
        self.assertTrue(len(sql) > 0)


if __name__ == "__main__":
    unittest.main()
