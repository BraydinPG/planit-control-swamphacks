"""Calibration and proper scoring rules for binary event-persistence forecasts."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Iterable


def brier_score(probabilities: Iterable[float], outcomes: Iterable[bool]) -> float | None:
    pairs = list(zip(probabilities, outcomes))
    if not pairs:
        return None
    if any(not math.isfinite(probability) or not 0 <= probability <= 1 for probability, _ in pairs):
        raise ValueError("probabilities must be finite values in [0, 1]")
    return sum((probability - int(outcome)) ** 2 for probability, outcome in pairs) / len(pairs)


def reliability_table(probabilities: Iterable[float], outcomes: Iterable[bool], bins: int = 10
                      ) -> list[dict[str, float | int]]:
    if bins < 1:
        raise ValueError("bins must be positive")
    grouped: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    for probability, outcome in zip(probabilities, outcomes):
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("probabilities must be finite values in [0, 1]")
        bucket = min(int(probability * bins), bins - 1)
        grouped[bucket].append((probability, bool(outcome)))
    return [
        {
            "bin_lower": bucket / bins,
            "bin_upper": (bucket + 1) / bins,
            "mean_predicted": sum(probability for probability, _ in values) / len(values),
            "observed_frequency": sum(outcome for _, outcome in values) / len(values),
            "count": len(values),
        }
        for bucket, values in sorted(grouped.items())
    ]


def episode_bootstrap_brier(probabilities: Iterable[float], outcomes: Iterable[bool],
                             episode_ids: Iterable[str], *, replicates: int = 500,
                             seed: int = 42) -> dict[str, float | int] | None:
    """Bootstrap episode means rather than treating correlated snapshots as independent."""
    grouped: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for probability, outcome, episode_id in zip(probabilities, outcomes, episode_ids):
        grouped[str(episode_id)].append((float(probability), bool(outcome)))
    if len(grouped) < 10 or replicates < 1:
        return None
    group_values = [values for values in grouped.values()]
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sample = [rng.choice(group_values) for _ in group_values]
        all_pairs = [pair for values in sample for pair in values]
        estimate = brier_score([pair[0] for pair in all_pairs], [pair[1] for pair in all_pairs])
        if estimate is not None:
            estimates.append(estimate)
    estimates.sort()
    return {
        "episode_count": len(group_values),
        "replicates": len(estimates),
        "lower_95": estimates[int(0.025 * (len(estimates) - 1))],
        "upper_95": estimates[int(0.975 * (len(estimates) - 1))],
    }


def binary_metrics(probabilities: Iterable[float], outcomes: Iterable[bool],
                   episode_ids: Iterable[str], *, bins: int = 10) -> dict[str, object]:
    probability_list = list(probabilities)
    outcome_list = list(outcomes)
    group_list = list(episode_ids)
    return {
        "snapshot_count": len(probability_list),
        "episode_count": len(set(group_list)),
        "brier_score": brier_score(probability_list, outcome_list),
        "reliability": reliability_table(probability_list, outcome_list, bins),
        "episode_bootstrap_brier_95": episode_bootstrap_brier(
            probability_list, outcome_list, group_list
        ),
    }
