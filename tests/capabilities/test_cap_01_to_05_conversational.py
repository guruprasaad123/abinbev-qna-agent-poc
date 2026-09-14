"""
Capability Test Suite: Capabilities 01 to 05
- Cap 01: Support single-turn and multi-turn conversational interactions
- Cap 02: Support greeting, capability introduction, and out-of-scope request handling
- Cap 03: Support intent validation before data retrieval
- Cap 04: Support clarification for ambiguous or incomplete user requests
- Cap 05: Support contextual follow-up questions by maintaining conversation history
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient


class TestCapabilities01to05(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Capability 1: Single-turn and Multi-turn Interactions ---
    def test_cap01_single_turn_lookup(self):
        r = self.orch.handle_turn("What was Corona volume in Mexico in 2025?")
        self.assertEqual(r.intent, "data_query")
        self.assertIn("structured", r.sub_agents_used)
        self.assertTrue(r.sql_used)

    def test_cap01_multi_turn_three_step_dialog(self):
        r1 = self.orch.handle_turn("What was Budweiser revenue in US in 2025?")
        r2 = self.orch.handle_turn("What about 2024?")
        r3 = self.orch.handle_turn("What about volume in that year?")
        self.assertEqual(len(self.orch.memory.raw_turns), 6)
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")

    def test_cap01_multi_turn_brand_switch(self):
        self.orch.handle_turn("What was Budweiser in US in 2025?")
        r2 = self.orch.handle_turn("Now look at Michelob ULTRA")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Michelob ULTRA")

    def test_cap01_multi_turn_market_switch(self):
        self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.orch.handle_turn("How did it do in Canada?")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Canada")

    def test_cap01_multi_turn_preserves_temporal_dimension(self):
        self.orch.handle_turn("What was Budweiser in US in 2024?")
        self.orch.handle_turn("What was the volume?")
        self.assertIn("2024", self.orch.memory.active_filters.get("period", ""))

    # --- Capability 2: Greeting, Capability Intro, Out-of-Scope ---
    def test_cap02_greeting_hello(self):
        r = self.orch.handle_turn("Hello")
        self.assertEqual(r.intent, "greeting")
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_cap02_greeting_good_morning(self):
        r = self.orch.handle_turn("Good morning!")
        self.assertEqual(r.intent, "greeting")

    def test_cap02_capability_intro_features(self):
        r = self.orch.handle_turn("What can you do?")
        self.assertEqual(r.intent, "capability_intro")
        self.assertIn("Anheuser-Busch InBev", r.answer)

    def test_cap02_capability_intro_purpose(self):
        r = self.orch.handle_turn("What is your purpose?")
        self.assertEqual(r.intent, "capability_intro")

    def test_cap02_out_of_scope_weather(self):
        r = self.orch.handle_turn("What is the weather today?")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_cap02_out_of_scope_recipe(self):
        r = self.orch.handle_turn("Give me a recipe for chocolate cookies")
        self.assertEqual(r.intent, "out_of_scope")

    def test_cap02_out_of_scope_stock(self):
        r = self.orch.handle_turn("What is the stock price of Apple?")
        self.assertEqual(r.intent, "out_of_scope")

    # --- Capability 3: Intent Validation Before Retrieval ---
    def test_cap03_no_sql_on_greeting(self):
        r = self.orch.handle_turn("Hi there")
        self.assertFalse(r.sql_used)
        self.assertEqual(len(r.citations), 0)

    def test_cap03_no_sql_on_capability_intro(self):
        r = self.orch.handle_turn("Show capabilities")
        self.assertFalse(r.sql_used)

    def test_cap03_no_sql_on_out_of_scope(self):
        r = self.orch.handle_turn("Who is the president?")
        self.assertFalse(r.sql_used)

    def test_cap03_retrieval_only_for_data_queries(self):
        r = self.orch.handle_turn("What was Stella Artois net revenue in UK in 2025?")
        self.assertEqual(r.intent, "data_query")
        self.assertTrue(r.sql_used)

    def test_cap03_intent_validation_comparison(self):
        r = self.orch.handle_turn("Compare Budweiser and Corona in US in 2025")
        self.assertEqual(r.intent, "comparison")
        self.assertIn("structured", r.sub_agents_used)

    # --- Capability 4: Clarification for Ambiguous Queries ---
    def test_cap04_clarification_performance_alone(self):
        r = self.orch.handle_turn("Can you tell me about the performance?")
        self.assertEqual(r.intent, "clarification_needed")
        self.assertTrue(len(r.answer) > 0)
        self.assertIn("clarify", r.answer.lower())

    def test_cap04_clarification_give_me_data(self):
        r = self.orch.handle_turn("Give me data please")
        self.assertEqual(r.intent, "clarification_needed")

    def test_cap04_clarification_how_is_beer_doing(self):
        r = self.orch.handle_turn("How is beer doing?")
        self.assertEqual(r.intent, "clarification_needed")

    def test_cap04_clarification_does_not_trigger_sql(self):
        r = self.orch.handle_turn("Can you tell me about the performance?")
        self.assertFalse(r.sql_used)
        self.assertEqual(len(r.sub_agents_used), 0)

    # --- Capability 5: Contextual Follow-Up via Conversation History ---
    def test_cap05_followup_inherits_brand_and_country(self):
        self.orch.handle_turn("What was Budweiser revenue in United States in 2025?")
        r2 = self.orch.handle_turn("What about in 2024?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "United States")
        self.assertIn("2024", r2.sql_used)

    def test_cap05_followup_swaps_metric(self):
        self.orch.handle_turn("What was Corona volume in Mexico in 2025?")
        r2 = self.orch.handle_turn("And what was the revenue?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Corona")
        self.assertIn("net_revenue_usd", r2.sql_used)

    def test_cap05_followup_maintains_context_block(self):
        self.orch.handle_turn("What was Stella Artois in Belgium in 2025?")
        ctx = self.orch.memory.context_block()
        self.assertIn("Stella Artois", ctx)
        self.assertIn("Belgium", ctx)


if __name__ == "__main__":
    unittest.main()
