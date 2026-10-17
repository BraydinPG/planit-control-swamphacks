from __future__ import annotations

import unittest

from ml.evaluate import brier_score, binary_metrics, episode_bootstrap_brier, reliability_table


class EvaluationTests(unittest.TestCase):
    def test_brier_score_known_values(self) -> None:
        self.assertAlmostEqual(brier_score([0.2, 0.8], [False, True]), 0.04)

    def test_empty_metric_is_undefined_not_zero(self) -> None:
        self.assertIsNone(brier_score([], []))
        metrics = binary_metrics([], [], [])
        self.assertIsNone(metrics["brier_score"])
        self.assertEqual(metrics["snapshot_count"], 0)

    def test_reliability_table_counts_and_calibration(self) -> None:
        table = reliability_table([0.1, 0.2, 0.85], [False, True, True], bins=2)
        self.assertEqual(table[0]["count"], 2)
        self.assertAlmostEqual(table[0]["observed_frequency"], 0.5)
        self.assertEqual(table[1]["count"], 1)

    def test_episode_bootstrap_is_seeded_and_grouped(self) -> None:
        probabilities = [0.1, 0.9] * 10
        outcomes = [False, True] * 10
        groups = [f"episode-{index // 2}" for index in range(20)]
        first = episode_bootstrap_brier(probabilities, outcomes, groups, replicates=100, seed=7)
        second = episode_bootstrap_brier(probabilities, outcomes, groups, replicates=100, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["episode_count"], 10)

    def test_invalid_probability_rejected(self) -> None:
        with self.assertRaises(ValueError):
            brier_score([1.1], [True])


if __name__ == "__main__":
    unittest.main()
