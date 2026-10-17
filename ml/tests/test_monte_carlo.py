from __future__ import annotations

import unittest

from ml.monte_carlo import simulate_hazards


class MonteCarloTests(unittest.TestCase):
    def test_seeded_reproducibility_and_analytic_agreement(self) -> None:
        hazards = [0.05] * 24
        first = simulate_hazards(hazards, trials=20000, seed=42)
        second = simulate_hazards(hazards, trials=20000, seed=42)
        self.assertEqual(first, second)
        for horizon in ("6h", "12h", "24h"):
            self.assertLess(first["absolute_probability_error"][horizon], 0.015)

    def test_unresolved_tail_and_no_trajectories(self) -> None:
        result = simulate_hazards([0.0] * 24, trials=50, seed=7)
        self.assertEqual(result["remaining_duration_hours"]["unresolved_beyond_simulation_horizon_count"], 50)
        self.assertTrue(result["raw_trajectories_included"] is False)
        self.assertEqual(result["simulated_ongoing_proportion"]["24h"], 1.0)

    def test_ended_event_does_not_restart(self) -> None:
        result = simulate_hazards([1.0] + [0.0] * 23, trials=100, seed=2)
        self.assertEqual(result["simulated_ongoing_proportion"]["6h"], 0.0)
        self.assertEqual(result["simulated_ongoing_proportion"]["24h"], 0.0)
        self.assertEqual(result["remaining_duration_hours"]["median"], 1.0)

    def test_unresolved_tail_stays_in_quantile_denominator(self) -> None:
        result = simulate_hazards([0.2] + [0.0] * 23, trials=2000, seed=42)
        duration = result["remaining_duration_hours"]
        self.assertEqual(duration["p10"], 1.0)
        self.assertIsNone(duration["median"])
        self.assertIsNone(duration["p90"])

    def test_rejects_hazard_values_outside_probability_bounds(self) -> None:
        with self.assertRaises(ValueError):
            simulate_hazards([0.1, 1.2], trials=10)


if __name__ == "__main__":
    unittest.main()
