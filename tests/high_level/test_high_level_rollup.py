"""
Offline, zero-cost tests for the High-Level Tier's rollup/aggregation logic
(tests/high_level/clusters.py, rollup.py). Unlike tests/live/, this makes
NO LLM calls -- it only reads whatever tests/live/reports/cap*.json already
exist (possibly none, on a fresh checkout) and checks the aggregation is
internally consistent. Named test_*.py deliberately: this belongs in the
normal, fast `python3 -m unittest discover -s tests` run.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.high_level.clusters import CLUSTERS, cluster_for_capability
from tests.high_level.rollup import build_rollup


class TestClusterMapping(unittest.TestCase):
    def test_covers_all_25_capabilities_exactly_once(self):
        numbers = sorted(n for c in CLUSTERS.values() for n in c["capability_numbers"])
        self.assertEqual(numbers, list(range(1, 26)))

    def test_exactly_six_clusters(self):
        self.assertEqual(len(CLUSTERS), 6)

    def test_every_cluster_has_a_title_and_description(self):
        for slug, cluster in CLUSTERS.items():
            self.assertTrue(cluster["title"], f"{slug} missing a title")
            self.assertTrue(cluster["description"], f"{slug} missing a description")

    def test_cluster_for_capability_matches_the_table(self):
        for slug, cluster in CLUSTERS.items():
            for number in cluster["capability_numbers"]:
                self.assertEqual(cluster_for_capability(number), slug)

    def test_cluster_for_unknown_capability_raises(self):
        with self.assertRaises(KeyError):
            cluster_for_capability(999)


class TestRollup(unittest.TestCase):
    def setUp(self):
        self.rollup = build_rollup()

    def test_rollup_has_exactly_six_clusters(self):
        self.assertEqual(set(self.rollup.keys()), set(CLUSTERS.keys()))

    def test_passed_never_exceeds_total_per_cluster(self):
        for slug, entry in self.rollup.items():
            self.assertLessEqual(entry["passed"], entry["total_cases"], slug)

    def test_grand_total_never_exceeds_185(self):
        grand_total = sum(entry["total_cases"] for entry in self.rollup.values())
        self.assertLessEqual(grand_total, 185)

    def test_not_run_capabilities_are_valid_capability_numbers(self):
        for entry in self.rollup.values():
            for number in entry["not_run"]:
                self.assertTrue(1 <= number <= 25)

    def test_cost_and_latency_are_non_negative(self):
        for entry in self.rollup.values():
            self.assertGreaterEqual(entry["total_cost_usd"], 0.0)
            self.assertGreaterEqual(entry["total_latency_s"], 0.0)


if __name__ == "__main__":
    unittest.main()
