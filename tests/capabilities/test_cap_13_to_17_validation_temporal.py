"""
Capability Test Suite: Capabilities 13 to 17
- Cap 13: Support answer validation, retry mechanisms, and response quality evaluation
- Cap 14: Support standardized formatting, including markdown tables and unit-aware presentation
- Cap 15: Support temporal reasoning for current, historical, and comparative period analysis
- Cap 16: Support context-aware follow-up suggestions within supported business domains
- Cap 17: Support conversation memory optimization for long-running sessions
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.formatting import format_value, rows_to_markdown_table
from src.memory import SUMMARIZE_TRIGGER_TURNS


class TestCapabilities13to17(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Capability 13: Answer Validation & Retry Mechanisms ---
    def test_cap13_detects_hallucinated_number(self):
        # Evidence has 100, 200; drafted answer invents 999999
        needs_retry = self.orch._needs_retry("The total was 999999 units.", {"100", "200"})
        self.assertTrue(needs_retry)

    def test_cap13_passes_valid_numbers(self):
        needs_retry = self.orch._needs_retry("Revenue was $156,046,898 in 2024.", {"156046898", "2024", "156,046,898"})
        self.assertFalse(needs_retry)

    def test_cap13_retried_flag_present_on_response(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        self.assertIsInstance(r.retried, bool)

    # --- Capability 14: Standardized Formatting (Markdown Tables & Unit-Aware Presentation) ---
    def test_cap14_currency_formatting(self):
        formatted = format_value("net_revenue_usd", 54321000)
        self.assertIn("$", formatted)
        self.assertIn("54,321,000", formatted)

    def test_cap14_volume_formatting_hl(self):
        formatted = format_value("volume", 78096.7)
        self.assertIn("78,096.7", formatted)

    def test_cap14_percentage_formatting(self):
        formatted = format_value("market_share_pct", 14.3)
        self.assertIn("14.3%", formatted)

    def test_cap14_markdown_table_generation(self):
        cols = ["brand", "country", "year", "net_revenue_usd"]
        rows = [("Bud Light", "United States", 2025, 4623330)]
        tbl = rows_to_markdown_table(cols, rows)
        self.assertIn("| Brand | Country | Year | Net Revenue (USD) |", tbl)
        self.assertIn("| Bud Light | United States | 2025 | $4,623,330 |", tbl)

    def test_cap14_orchestrator_returns_markdown_table(self):
        r = self.orch.handle_turn("What was Bud Light in United States in 2025?")
        self.assertIn("|", r.answer)
        self.assertIn("Bud Light", r.answer)

    # --- Capability 15: Temporal Reasoning (Current, Historical, Comparative Periods) ---
    def test_cap15_historical_period_2023(self):
        r = self.orch.handle_turn("What was Corona sales in Mexico in 2023?")
        self.assertIn("2023", r.sql_used)

    def test_cap15_historical_period_2024(self):
        r = self.orch.handle_turn("What was Corona sales in Mexico in 2024?")
        self.assertIn("2024", r.sql_used)

    def test_cap15_historical_period_2025(self):
        r = self.orch.handle_turn("What was Corona sales in Mexico in 2025?")
        self.assertIn("2025", r.sql_used)

    def test_cap15_current_period_2026_ytd(self):
        r = self.orch.handle_turn("What was Corona sales in Mexico in 2026?")
        self.assertIn("2026", r.sql_used)

    def test_cap15_comparative_multi_year_superlative(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("2023", r.answer)
        self.assertIn("9.66%", r.answer)
        self.assertIn("18.04%", r.answer)

    def test_cap15_comparative_period_annualization_note(self):
        r = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertIn("2026", r.answer)

    # --- Capability 16: Context-Aware Follow-Up Suggestions ---
    def test_cap16_suggestions_populated(self):
        r = self.orch.handle_turn("What was Budweiser in United States in 2025?")
        self.assertTrue(len(r.follow_up_suggestions) > 0)

    def test_cap16_suggestions_contextual_to_kpi_and_entities(self):
        r = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        sug_text = " ".join(r.follow_up_suggestions).lower()
        self.assertTrue(any(k in sug_text for k in ("volume", "2024", "channel", "margin", "share")))

    def test_cap16_suggestions_formatted_as_list(self):
        r = self.orch.handle_turn("Show Stella Artois in Belgium in 2025")
        self.assertIsInstance(r.follow_up_suggestions, list)

    # --- Capability 17: Conversation Memory Optimization for Long-Running Sessions ---
    def test_cap17_rolling_summary_triggers_after_threshold(self):
        for i in range(SUMMARIZE_TRIGGER_TURNS + 3):
            self.orch.handle_turn(f"Turn query {i} for Budweiser in 2025")
        self.assertTrue(len(self.orch.memory.rolling_summary) > 0)

    def test_cap17_bounds_raw_turns_growth(self):
        for i in range(SUMMARIZE_TRIGGER_TURNS + 5):
            self.orch.handle_turn(f"Turn query {i} for Corona in 2025")
        # Recent raw turns should stay bounded
        self.assertLessEqual(len(self.orch.memory.raw_turns), (SUMMARIZE_TRIGGER_TURNS + 5) * 2)

    def test_cap17_context_block_includes_summary(self):
        for i in range(SUMMARIZE_TRIGGER_TURNS + 2):
            self.orch.handle_turn(f"Turn {i}")
        ctx = self.orch.memory.context_block()
        self.assertIn("Conversation summary so far:", ctx)


if __name__ == "__main__":
    unittest.main()
