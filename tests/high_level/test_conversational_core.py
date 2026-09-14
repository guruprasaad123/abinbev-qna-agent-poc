"""
High-Level Test Suite: 01. Conversational Core
Covers Attributes 1, 2, 3, 4, 8, 17:
- Single-turn and multi-turn interactions
- Greetings, capability intro, out-of-scope handling
- Intent validation before data retrieval
- Clarification for ambiguous requests
- Context preservation across turns
- Memory optimization and rolling summarization
"""
import unittest
from src.orchestrator import Orchestrator
from src.llm_client import MockLLMClient
from src.memory import SUMMARIZE_TRIGGER_TURNS


class TestConversationalCore(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator(llm_router=MockLLMClient(), llm_worker=MockLLMClient())

    # --- Attribute 2: Greeting Handling ---
    def test_01_greeting_simple_hello(self):
        r = self.orch.handle_turn("Hello")
        self.assertEqual(r.intent, "greeting")
        self.assertEqual(len(r.sub_agents_used), 0)
        self.assertIn("AB InBev", r.answer)

    def test_02_greeting_hi_there(self):
        r = self.orch.handle_turn("Hi there!")
        self.assertEqual(r.intent, "greeting")
        self.assertFalse(r.sql_used)

    def test_03_greeting_good_morning(self):
        r = self.orch.handle_turn("Good morning assistant")
        self.assertEqual(r.intent, "greeting")

    def test_04_greeting_hey(self):
        r = self.orch.handle_turn("Hey")
        self.assertEqual(r.intent, "greeting")

    # --- Attribute 2: Capability Intro ---
    def test_05_capability_what_can_you_do(self):
        r = self.orch.handle_turn("What can you do?")
        self.assertEqual(r.intent, "capability_intro")
        self.assertIn("Budweiser", r.answer)
        self.assertIn("BEES", r.answer)
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_06_capability_help(self):
        r = self.orch.handle_turn("What can you help me with?")
        self.assertEqual(r.intent, "capability_intro")

    def test_07_capability_show_commands(self):
        r = self.orch.handle_turn("Show your capabilities and features")
        self.assertEqual(r.intent, "capability_intro")

    # --- Attribute 2 & 3: Out-of-Scope Handling & Intent Validation ---
    def test_08_out_of_scope_weather(self):
        r = self.orch.handle_turn("What is the weather in London today?")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertEqual(len(r.sub_agents_used), 0)
        self.assertIn("outside what i can help with", r.answer.lower())

    def test_09_out_of_scope_sports(self):
        r = self.orch.handle_turn("Who won the 2022 FIFA World Cup?")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_10_out_of_scope_coding_unrelated(self):
        r = self.orch.handle_turn("Write a quicksort algorithm in C++")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_11_out_of_scope_cooking(self):
        r = self.orch.handle_turn("How do I bake a chocolate cake?")
        self.assertEqual(r.intent, "out_of_scope")
        self.assertFalse(r.sql_used)

    def test_12_out_of_scope_politics(self):
        r = self.orch.handle_turn("Tell me about the political situation in Europe")
        self.assertEqual(r.intent, "out_of_scope")

    # --- Attribute 4: Clarification for Ambiguous Queries ---
    def test_13_clarification_ambiguous_sales(self):
        r = self.orch.handle_turn("Tell me about sales")
        self.assertEqual(r.intent, "clarification_needed")
        self.assertIn("which brand", r.answer.lower())
        self.assertEqual(len(r.sub_agents_used), 0)

    def test_14_clarification_vague_performance(self):
        r = self.orch.handle_turn("How is beer doing?")
        self.assertEqual(r.intent, "clarification_needed")

    def test_15_clarification_incomplete_data(self):
        r = self.orch.handle_turn("Give me data please")
        self.assertEqual(r.intent, "clarification_needed")

    # --- Attribute 1 & 3: Single-Turn Data Retrieval with Intent Validation ---
    def test_16_single_turn_brand_revenue(self):
        r = self.orch.handle_turn("What was Corona revenue in the United States in 2025?")
        self.assertEqual(r.intent, "data_query")
        self.assertIn("structured", r.sub_agents_used)
        self.assertTrue(r.sql_used)
        self.assertIn("Corona", r.answer)

    def test_17_single_turn_volume_lookup(self):
        r = self.orch.handle_turn("What was Stella Artois volume in United Kingdom in 2024?")
        self.assertEqual(r.intent, "data_query")
        self.assertIn("structured", r.sub_agents_used)
        self.assertIn("hL", r.answer)

    def test_18_single_turn_market_share(self):
        r = self.orch.handle_turn("What was Michelob ULTRA market share in United States in 2025?")
        self.assertEqual(r.intent, "data_query")
        self.assertIn("%", r.answer)

    def test_19_single_turn_channel_breakdown(self):
        r = self.orch.handle_turn("Show Bud Light sales by channel in United States in 2025")
        self.assertEqual(r.intent, "data_query")
        self.assertIn("channel", r.sql_used.lower())

    # --- Attribute 1, 5, 8: Multi-Turn Conversation & Filter Persistence ---
    def test_20_multi_turn_brand_to_country_followup(self):
        # Turn 1: Establish brand and country
        r1 = self.orch.handle_turn("What was Budweiser revenue in the United States in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "United States")

        # Turn 2: Follow up with no brand specified -> inherits Budweiser
        r2 = self.orch.handle_turn("What about in 2024?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")
        self.assertIn("2024", r2.sql_used)

    def test_21_multi_turn_metric_shift(self):
        self.orch.handle_turn("What was Corona net revenue in Mexico in 2025?")
        # Follow up asking for volume without repeating entity or country
        r2 = self.orch.handle_turn("What was the volume for that same period?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Corona")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Mexico")

    def test_22_multi_turn_channel_filter_carryover(self):
        self.orch.handle_turn("How much Bud Light sold through BEES in United States in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("channel"), "BEES & E-commerce")
        # Follow-up for next year maintains channel
        self.orch.handle_turn("What about in 2024?")
        self.assertEqual(self.orch.memory.active_filters.get("channel"), "BEES & E-commerce")

    def test_23_multi_turn_override_brand(self):
        self.orch.handle_turn("What was Budweiser revenue in United States in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Budweiser")
        # Explicit override to Stella Artois
        self.orch.handle_turn("Now show me Stella Artois in the same market")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Stella Artois")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "United States")

    def test_24_multi_turn_override_country(self):
        self.orch.handle_turn("What was Corona revenue in Mexico in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Mexico")
        # Override country to Brazil
        self.orch.handle_turn("What about in Brazil?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Corona")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Brazil")

    def test_25_multi_turn_three_step_drilldown(self):
        self.orch.handle_turn("Show Bud Light in United States in 2025")
        self.orch.handle_turn("Now look at 2024")
        r3 = self.orch.handle_turn("And what was the market share in that year?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Bud Light")
        self.assertIn("structured", r3.sub_agents_used)

    # --- Attribute 8: Context Preservation in Memory State ---
    def test_26_memory_tracks_turn_history(self):
        self.orch.handle_turn("Hello")
        self.orch.handle_turn("What was Corona in Mexico in 2025?")
        # 2 turns * 2 (user + assistant) = 4 raw entries
        self.assertEqual(len(self.orch.memory.raw_turns), 4)
        self.assertEqual(self.orch.memory.raw_turns[0]["content"], "Hello")
        self.assertEqual(self.orch.memory.raw_turns[0]["role"], "user")

    def test_27_memory_context_block_formatting(self):
        self.orch.handle_turn("What was Budweiser in United States in 2025?")
        ctx = self.orch.memory.context_block()
        self.assertIn("Active context", ctx)
        self.assertIn("Budweiser", ctx)
        self.assertIn("United States", ctx)

    def test_28_memory_resets_on_clear(self):
        self.orch.handle_turn("What was Budweiser in United States in 2025?")
        self.orch.memory.clear_filters()
        self.orch.memory.raw_turns = []
        self.assertEqual(len(self.orch.memory.raw_turns), 0)
        self.assertEqual(len(self.orch.memory.active_filters), 0)

    # --- Attribute 17: Long-Running Session Memory Optimization ---
    def test_29_rolling_summary_triggers_past_threshold(self):
        # Execute more turns than SUMMARIZE_TRIGGER_TURNS (default 14)
        for i in range(SUMMARIZE_TRIGGER_TURNS + 4):
            self.orch.handle_turn(f"What was Budweiser in United States in 2025? (iteration {i})")
        # Rolling summary should be populated
        self.assertTrue(len(self.orch.memory.rolling_summary) > 0)

    def test_30_rolling_summary_preserves_salient_entities(self):
        self.orch.handle_turn("What was Budweiser in United States in 2025?")
        for i in range(SUMMARIZE_TRIGGER_TURNS + 2):
            self.orch.handle_turn(f"Follow up iteration {i}")
        ctx = self.orch.memory.context_block()
        self.assertIn("Conversation summary so far:", ctx)

    def test_31_enterprise_query_clears_stale_entity_filters(self):
        # Turn 1 sets local filters for Bud Light in United States
        self.orch.handle_turn("What was Bud Light in United States in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Bud Light")
        # Turn 2 asks company-wide question -> should clear brand filter from context
        r2 = self.orch.handle_turn("in year did the AB inBev performed poor comparatively")
        self.assertNotIn("brand='Bud Light'", r2.sql_used)
        self.assertIn("GROUP BY year", r2.sql_used)

    def test_32_follow_up_suggestions_surfaced(self):
        r = self.orch.handle_turn("What was Corona in Mexico in 2025?")
        self.assertIsInstance(r.follow_up_suggestions, list)
        self.assertTrue(len(r.follow_up_suggestions) > 0)


if __name__ == "__main__":
    unittest.main()
