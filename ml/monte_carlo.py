"""Offline-only conditional outcome sampling; never imported by production inference."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any, Sequence

from ml.config import MODEL_PATH, REPORT_DIR
from ml.schemas import validate_event_context
from ml.train import SurvivalModels, load_models, logistic_hourly_hazard


def _quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = math.ceil(quantile * len(ordered)) - 1
    return ordered[min(max(rank, 0), len(ordered) - 1)]


def _draw_duration(hazards: Sequence[float], rng: random.Random) -> int | None:
    """Return first ending hour or None for unresolved tail; an ended event never restarts."""
    for hour, hazard in enumerate(hazards, start=1):
        if not 0 <= hazard <= 1 or not math.isfinite(hazard):
            raise ValueError("hazards must be finite values in [0, 1]")
        if rng.random() < hazard:
            return hour
    return None


def simulate_hazards(hazards: Sequence[float], *, trials: int = 5000, seed: int = 42,
                     horizons: tuple[int, ...] = (6, 12, 24)) -> dict[str, Any]:
    """Compare offline Monte Carlo proportions with analytical survival probabilities."""
    if trials < 1:
        raise ValueError("trials must be positive")
    if not hazards:
        raise ValueError("at least one hourly hazard is required")
    if any(horizon < 1 or horizon > len(hazards) for horizon in horizons):
        raise ValueError("requested horizons must be covered by the hazard sequence")
    rng = random.Random(seed)
    durations = [_draw_duration(hazards, rng) for _ in range(trials)]
    analytical: dict[str, float] = {}
    simulated: dict[str, float] = {}
    for horizon in horizons:
        survival = math.prod(1.0 - hazard for hazard in hazards[:horizon])
        analytical[f"{horizon}h"] = survival
        simulated[f"{horizon}h"] = sum(duration is None or duration > horizon for duration in durations) / trials
    finite_durations = [float(duration) for duration in durations if duration is not None]
    unresolved_count = sum(duration is None for duration in durations)
    return {
        "trials": trials,
        "seed": seed,
        "analytical_ongoing_probability": analytical,
        "simulated_ongoing_proportion": simulated,
        "absolute_probability_error": {
            horizon: abs(simulated[horizon] - analytical[horizon]) for horizon in analytical
        },
        "remaining_duration_hours": {
            "p10": _quantile(finite_durations, 0.10),
            "median": _quantile(finite_durations, 0.50),
            "p90": _quantile(finite_durations, 0.90) if len(finite_durations) / trials >= 0.90 else None,
            "unresolved_beyond_simulation_horizon_count": unresolved_count,
            "unresolved_beyond_simulation_horizon_probability": unresolved_count / trials,
        },
        "raw_trajectories_included": False,
        "validation_note": "Simulation checks arithmetic and model-implied sampling only; it is not independent historical validation.",
    }


def simulate_model(models: SurvivalModels, *, elapsed_hours: float, start_month: int,
                   trials: int = 5000, seed: int = 42) -> dict[str, Any]:
    remaining = models.max_followup_hours - elapsed_hours
    if remaining < 24:
        raise ValueError("model support does not cover requested horizons from this event age")
    steps = math.floor(remaining)
    hazards = [logistic_hourly_hazard(models, elapsed_hours + step, start_month) for step in range(steps)]
    result = simulate_hazards(hazards, trials=trials, seed=seed)
    result["model_version"] = models.model_version
    result["scope"] = "offline_internal_only"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-fixture", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_DIR / "monte_carlo_summary.json")
    parser.add_argument("--trials", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    context = json.loads(args.event_fixture.read_text(encoding="utf-8"))
    normalized = validate_event_context(context)
    models = load_models(args.model_path)
    event_start = normalized["_event_start_datetime"]
    if event_start is None:
        raise SystemExit("Fixture requires event_start_utc for conditional simulation.")
    elapsed = (normalized["_as_of_datetime"] - event_start).total_seconds() / 3600
    report = simulate_model(models, elapsed_hours=elapsed, start_month=event_start.month,
                            trials=args.trials, seed=args.seed)
    report.update({"event_id": context["event_id"], "event_type": context["event_type"],
                   "as_of_utc": normalized["as_of_utc"], "is_simulated": bool(context.get("is_simulated", False))})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
