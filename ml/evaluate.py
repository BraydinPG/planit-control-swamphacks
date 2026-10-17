"""Calibration and proper scoring rules for binary event-persistence forecasts."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Iterable


def brier_score(probabilities: Iterable[float], outcomes: Iterable[bool]) -> float | None:
    probability_list, outcome_list = list(probabilities), list(outcomes)
    if len(probability_list) != len(outcome_list):
        raise ValueError("probabilities and outcomes must have identical lengths")
    pairs = list(zip(probability_list, outcome_list))
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


def episode_bootstrap_mean(values: Iterable[float], episode_ids: Iterable[str], *,
                           replicates: int = 500, seed: int = 42) -> dict[str, float | int] | None:
    """Resample whole episodes, retaining snapshot-weighted means.

    Preaggregate each episode once. This uses the same seeded choice sequence as
    the original flattened bootstrap without rebuilding all pairs per replicate.
    """
    value_list, group_list = list(values), list(episode_ids)
    if len(value_list) != len(group_list) or any(not math.isfinite(value) for value in value_list):
        raise ValueError("finite values and episode IDs must have identical lengths")
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, episode_id in zip(value_list, group_list):
        grouped[str(episode_id)].append(float(value))
    if len(grouped) < 10 or replicates < 1:
        return None
    group_values = [(sum(group), len(group)) for group in grouped.values()]
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sample = [rng.choice(group_values) for _ in group_values]
        estimates.append(sum(total for total, _ in sample) / sum(count for _, count in sample))
    estimates.sort()
    return {
        "episode_count": len(group_values),
        "replicates": len(estimates),
        "lower_95": estimates[int(0.025 * (len(estimates) - 1))],
        "upper_95": estimates[int(0.975 * (len(estimates) - 1))],
    }


def episode_bootstrap_brier(probabilities: Iterable[float], outcomes: Iterable[bool],
                             episode_ids: Iterable[str], *, replicates: int = 500,
                             seed: int = 42) -> dict[str, float | int] | None:
    probability_list, outcome_list = list(probabilities), list(outcomes)
    brier_score(probability_list, outcome_list)  # Validate once, outside resampling.
    return episode_bootstrap_mean(
        [(p - int(y)) ** 2 for p, y in zip(probability_list, outcome_list)], episode_ids,
        replicates=replicates, seed=seed,
    )


def duration_metrics(remaining: list[float], quantiles: list[dict[float, float | None]],
                     episode_ids: list[str]) -> dict[str, object]:
    """Report identifiable predictions only; do not zero-fill censored tails."""
    if not len(remaining) == len(quantiles) == len(episode_ids):
        raise ValueError("duration predictions, labels, and groups must have identical lengths")
    errors, error_groups, coverage, coverage_groups = [], [], [], []
    for actual, predicted, group in zip(remaining, quantiles, episode_ids):
        if predicted[0.5] is not None:
            errors.append(abs(predicted[0.5] - actual))
            error_groups.append(group)
        if predicted[0.1] is not None and predicted[0.9] is not None:
            coverage.append(float(predicted[0.1] <= actual <= predicted[0.9]))
            coverage_groups.append(group)
    return {
        "snapshot_count": len(remaining), "episode_count": len(set(episode_ids)),
        "median_remaining_time_mae_hours": sum(errors) / len(errors) if errors else None,
        "median_prediction_count": len(errors),
        "median_mae_episode_bootstrap_95": episode_bootstrap_mean(errors, error_groups),
        "p10_p90_interval_coverage": sum(coverage) / len(coverage) if coverage else None,
        "interval_prediction_count": len(coverage),
        "unidentifiable_interval_count": len(remaining) - len(coverage),
        "coverage_episode_bootstrap_95": episode_bootstrap_mean(coverage, coverage_groups),
        "coverage_interpretation": "conditional on both quantiles identifiable before modeling horizon",
    }


def binary_metrics(probabilities: Iterable[float], outcomes: Iterable[bool],
                   episode_ids: Iterable[str], *, bins: int = 10) -> dict[str, object]:
    probability_list = list(probabilities)
    outcome_list = list(outcomes)
    group_list = list(episode_ids)
    if not len(probability_list) == len(outcome_list) == len(group_list):
        raise ValueError("probabilities, outcomes, and episode IDs must have identical lengths")
    return {
        "snapshot_count": len(probability_list),
        "episode_count": len(set(group_list)),
        "brier_score": brier_score(probability_list, outcome_list),
        "reliability": reliability_table(probability_list, outcome_list, bins),
        "episode_bootstrap_brier_95": episode_bootstrap_brier(
            probability_list, outcome_list, group_list
        ),
    }
