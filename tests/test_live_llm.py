"""
Live LLM Execution Tests.

Tests the actual LLM provider integration configured via .env (Token Harbor, OpenAI, Anthropic).
If no live key is present, these tests are cleanly skipped so that CI/offline environments don't fail.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Ensure .env is loaded
from src.llm_client import get_llm_client, GLOBAL_USAGE, OpenAILLMClient, AnthropicLLMClient
from src.orchestrator import Orchestrator


def _has_live_credentials() -> bool:
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider == "mock":
        return False
    th_key = os.getenv("TOKEN_HARBOR_API_KEY") or os.getenv("api_key")
    if th_key and (th_key.startswith("thk_") or th_key.startswith("hk_")):
        return True
    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        return True
    return False


@unittest.skipUnless(_has_live_credentials(), "Live LLM API credentials not configured in .env")
class TestLiveLLMExecution(unittest.TestCase):

    def setUp(self):
        GLOBAL_USAGE.reset()
        self.orch = Orchestrator()

    def test_01_live_client_connectivity(self):
        """Verify that the active live client connects and generates text."""
        client = get_llm_client("router")
        self.assertNotEqual(client.model_name, "mock", "Expected a live client, got MockLLMClient")
        resp = client.generate(
            system="You are a helpful assistant. Be concise.",
            user="Reply with the exact word: CONNECTED",
            caller="test_live_client_connectivity"
        )
        self.assertIn("CONNECTED", resp)
        self.assertGreater(GLOBAL_USAGE.summary()["calls"], 0)

    def test_02_live_structured_data_query(self):
        """Verify end-to-end single-turn query against SQLite fact database."""
        resp = self.orch.handle_turn("What was Corona net revenue in Mexico in 2025?")
        self.assertEqual(resp.intent, "data_query")
        self.assertIn("structured", resp.sub_agents_used)
        self.assertTrue(len(resp.answer) > 0)
        # Verify that either the formatted dollar figure or Corona appears in answer
        self.assertTrue("Corona" in resp.answer or "11,209,048" in resp.answer)

    def test_03_live_hybrid_query_with_citations(self):
        """Verify hybrid query combining structured DB + unstructured docs with [DOC-xxx] citations."""
        resp = self.orch.handle_turn("What is AB InBev's strategy for Corona Cero and what was its volume in 2025?")
        self.assertEqual(resp.intent, "data_query")
        self.assertIn("unstructured", resp.sub_agents_used)
        self.assertTrue(len(resp.answer) > 0)
        self.assertIn("DOC-", resp.answer, "Expected inline document citation [DOC-xxx] in hybrid answer")

    def test_04_live_multiturn_memory_filter_persistence(self):
        """Verify that multi-turn context carries brand and country filters forward."""
        # Turn 1
        r1 = self.orch.handle_turn("What was Corona net revenue in Mexico in 2025?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Corona")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Mexico")

        # Turn 2: Elliptical follow-up
        r2 = self.orch.handle_turn("What about in 2024?")
        self.assertEqual(self.orch.memory.active_filters.get("brand"), "Corona")
        self.assertEqual(self.orch.memory.active_filters.get("country"), "Mexico")
        self.assertEqual(self.orch.memory.active_filters.get("period"), "2024")
        self.assertTrue(len(r2.answer) > 0)


if __name__ == "__main__":
    unittest.main()
