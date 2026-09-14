"""
High-Level Test Suite: 05. Analytics, Temporal Reasoning & Derived Calculations
Covers Attributes 14, 15, 19, 20 & Coding Sub-Agent:
- Standardized formatting (markdown tables, unit-aware USD/hL/%)
- Temporal reasoning (historical, current YTD 2026, multi-year YoY)
- Enterprise-wide comparative queries & superlative analysis (poor/best years)
- Multi-entity, multi-KPI, and multi-channel comparisons
- Sandboxed derived calculations via Coding Sub-Agent (CAGR, projections)
"""
import unittest
import math
import statistics
import datetime
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.tools.code_tool import run_code
from src.formatting import format_value, rows_to_markdown_table


class TestAnalyticsTemporal(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Unit-Aware Formatting & Markdown Tables ---
    def test_01_format_currency_millions(self):
        val = format_value("net_revenue_usd", 140971636)
        self.assertIn("$", val)
        self.assertIn("140", val)

    def test_02_format_volume_hectoliters(self):
        val = format_value("volume", 1790001)
        self.assertIn("1,790,001", val)

    def test_03_format_percentage(self):
        val = format_value("market_share_pct", 18.5)
        self.assertIn("%", val)

    def test_04_markdown_table_structure(self):
        cols = ["brand", "year", "net_revenue_usd"]
        rows = [("Budweiser", 2025, 45000000), ("Corona", 2025, 52000000)]
        tbl = rows_to_markdown_table(cols, rows)
        self.assertIn("| Brand | Year | Net Revenue (USD) |", tbl)
        self.assertIn("| Budweiser |", tbl)
        self.assertIn("| Corona |", tbl)

    def test_05_markdown_table_empty_handling(self):
        tbl = rows_to_markdown_table(["Col1"], [])
        self.assertEqual(tbl, "_No matching rows found._")

    # --- Temporal Reasoning: Historical & Current YTD Periods ---
    def test_06_temporal_historical_2023(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2023?")
        self.assertIn("2023", r.sql_used)
        self.assertIn("structured", r.sub_agents_used)

    def test_07_temporal_historical_2024(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2024?")
        self.assertIn("2024", r.sql_used)

    def test_08_temporal_historical_2025(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertIn("2025", r.sql_used)

    def test_09_temporal_ytd_2026_boundary(self):
        # 2026 data in database covers 8 months (Jan - Aug 2026)
        r = self.orch.handle_turn("Show Stella Artois in Belgium in 2026")
        self.assertIn("2026", r.sql_used or r.answer)

    # --- Enterprise-Wide Comparative & Superlative Queries ---
    def test_10_superlative_poor_year_detection(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertEqual(r.intent, "comparison")
        self.assertIn("GROUP BY year", r.sql_used)
        # 2023 was the lowest full year
        self.assertIn("2023", r.answer)

    def test_11_superlative_poor_year_cites_percentages(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("9.66%", r.answer)
        self.assertIn("18.04%", r.answer)

    def test_12_superlative_poor_year_notes_2026_ytd(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("2026", r.answer)
        self.assertTrue("8 months" in r.answer or "YTD" in r.answer or "annualized" in r.answer.lower())

    def test_13_comparative_best_year_query(self):
        r = self.orch.handle_turn("Which year was the best year for AB InBev comparatively?")
        self.assertEqual(r.intent, "comparison")
        self.assertIn("GROUP BY year", r.sql_used)

    def test_14_multi_year_trend_query(self):
        r = self.orch.handle_turn("Show net revenue trend across years for AB InBev")
        self.assertEqual(r.intent, "comparison")
        self.assertIn("GROUP BY year", r.sql_used)

    # --- Multi-Entity and Multi-KPI Comparisons ---
    def test_15_compare_two_brands(self):
        r = self.orch.handle_turn("Compare Budweiser and Corona in the United States in 2025")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("Budweiser", r.sql_used)

    def test_16_compare_two_countries(self):
        r = self.orch.handle_turn("Compare Corona sales in Mexico vs United States in 2025")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("Mexico", r.sql_used)

    def test_17_compare_multiple_kpis(self):
        r = self.orch.handle_turn("Show both volume and net revenue for Michelob ULTRA in US in 2025")
        self.assertIn("volume", r.sql_used)
        self.assertIn("net_revenue_usd", r.sql_used)

    def test_18_compare_channels(self):
        r = self.orch.handle_turn("Compare Bud Light volume by channel in US in 2025")
        self.assertIn("channel", r.sql_used.lower())

    def test_19_bees_digital_channel_aggregation(self):
        r = self.orch.handle_turn("How much volume went through BEES in US in 2025?")
        self.assertIn("BEES & E-commerce", r.sql_used)

    # --- Sandboxed Coding Calculations ---
    def test_20_coding_simple_arithmetic(self):
        res = run_code("result = 100 * (1 + 0.10) ** 3")
        self.assertTrue(res.ok)
        self.assertAlmostEqual(res.result, 133.1, places=1)

    def test_21_coding_cagr_calculation(self):
        code = """
start_val = 140.97
end_val = 172.00
years = 2
result = round(((end_val / start_val) ** (1 / years) - 1) * 100, 2)
"""
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertGreater(res.result, 10.0)

    def test_22_coding_future_projection(self):
        code = """
revenue_2025 = 172.0
growth_rate = 0.08
result = round(revenue_2025 * ((1 + growth_rate) ** 3), 2)
"""
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertGreater(res.result, 210.0)

    def test_23_coding_statistics_module_available(self):
        code = "result = statistics.mean([10, 20, 30, 40, 50])"
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertEqual(res.result, 30)

    def test_24_coding_math_module_available(self):
        code = "result = round(math.sqrt(144), 1)"
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertEqual(res.result, 12.0)

    def test_25_coding_datetime_module_available(self):
        code = "result = datetime.date(2026, 8, 1).year"
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertEqual(res.result, 2026)

    def test_26_coding_captures_stdout(self):
        code = "print('Assumption: 6% constant CAGR')\nresult = 42"
        res = run_code(code)
        self.assertTrue(res.ok)
        self.assertIn("Assumption: 6% constant CAGR", res.stdout)
        self.assertEqual(res.result, 42)

    def test_27_coding_blocks_os_import(self):
        res = run_code("import os\nresult = os.name")
        self.assertFalse(res.ok)

    def test_28_coding_blocks_sys_import(self):
        res = run_code("import sys\nresult = sys.version")
        self.assertFalse(res.ok)

    def test_29_coding_blocks_open_file(self):
        res = run_code("result = open('data/db/abinbev.db').read()")
        self.assertFalse(res.ok)

    def test_30_coding_blocks_eval_exec(self):
        res = run_code("result = eval('2 + 2')")
        self.assertFalse(res.ok)

    def test_31_coding_blocks_dunder_import(self):
        res = run_code("result = __import__('os').getcwd()")
        self.assertFalse(res.ok)

    def test_32_coding_timeout_enforcement(self):
        # Hard 5-second alarm kills infinite loops
        res = run_code("while True: pass")
        self.assertFalse(res.ok)
        self.assertIn("timeout", res.error.lower())

    def test_33_orchestrator_routes_cagr_to_coding(self):
        r = self.orch.handle_turn("Calculate CAGR if revenue grew from 100 to 200 over 5 years")
        self.assertIn("coding", r.sub_agents_used)
        self.assertIn("code_used", r.intermediate_steps)

    def test_34_orchestrator_routes_growth_projection_to_coding(self):
        r = self.orch.handle_turn("If Corona grew by 7% per year for 4 years calculate the projection")
        self.assertIn("coding", r.sub_agents_used)

    def test_35_orchestrator_preserves_code_in_intermediate_steps(self):
        r = self.orch.handle_turn("Calculate CAGR for revenue growing from 150 to 300 over 3 years")
        self.assertIn("code_used", r.intermediate_steps)
        self.assertTrue(len(r.intermediate_steps["code_used"]) > 0)


if __name__ == "__main__":
    unittest.main()
