"""Real artifact/reference smoke checks and small serial inference/Monte Carlo benchmarks."""

import json
from pathlib import Path
import statistics
import time

from ml.backend_adapter import ActiveEventPredictor
from ml.config import MODEL_PATH, REPORT_DIR
from ml.dispatch import load_entry_model, read_registry
from ml.monte_carlo import simulate_model
from ml.provision import check_reference
from ml.train import load_models


def run() -> dict:
    check_reference(load_models(MODEL_PATH), json.loads((REPORT_DIR.parent / "model_reference.json").read_text(encoding="utf-8")))
    registry = read_registry()
    predictor = ActiveEventPredictor()
    examples, timings, simulations = {}, {}, {}
    for name, entry in registry["events"].items():
        if not entry.get("prediction_eligible") or "artifact" not in entry:
            continue
        card_path = REPORT_DIR / "multidisaster" / (Path(entry["artifact"]).stem + ".json")
        card = json.loads(card_path.read_text(encoding="utf-8"))
        context = card["example_context"]
        start = time.perf_counter()
        result = predictor.predict(context)
        cold_ms = (time.perf_counter()-start)*1000
        if result["status"] != "ok":
            raise RuntimeError(f"{name} reference unavailable: {result['worker_context']}")
        examples[name] = {"context": context, "prediction": result}
        if "reference_ongoing_probability" not in card:
            card["reference_ongoing_probability"] = result["outcomes"]["recorded_event_ongoing_probability"]
            card_path.write_text(json.dumps(card, indent=2, allow_nan=False), encoding="utf-8")
        elif card["reference_ongoing_probability"] != result["outcomes"]["recorded_event_ongoing_probability"]:
            raise ValueError(f"{name} reference changed")
        calls = []
        for _ in range(200):
            start = time.perf_counter()
            again = predictor.predict(context)
            calls.append((time.perf_counter()-start)*1000)
            if again["outcomes"] != result["outcomes"]:
                raise ValueError("inference is not deterministic")
        timings[name] = {"first_call_ms": cold_ms, "warm_calls": len(calls),
                         "warm_median_ms": statistics.median(calls), "warm_p95_ms": sorted(calls)[189]}
        model = load_entry_model(entry)
        from ml.schemas import validate_event_context
        parsed = validate_event_context(context)
        elapsed = (parsed["_as_of_datetime"]-parsed["_event_start_datetime"]).total_seconds()/3600
        simulations[name] = simulate_model(model, elapsed_hours=elapsed, start_month=parsed["_event_start_datetime"].month,
                                          estimator=entry["selected_estimator"], horizons=tuple(entry["supported_horizons_hours"]),
                                          trials=20000, seed=42)
        simulations[name]["historical_evaluation_reference"] = "ml/reports/multidisaster/" + card_path.name
        simulations[name]["historical_duration_metrics"] = card["test"][entry["selected_estimator"]]["duration"]
        simulations[name]["historical_example_observed_remaining_hours"] = card.get("example_observed_remaining_hours")
        median = simulations[name]["remaining_duration_hours"]["median"]
        observed = card.get("example_observed_remaining_hours")
        simulations[name]["single_replay_median_absolute_error_hours"] = abs(median-observed) if median is not None and observed is not None else None
    report = {"status": "REAL_ARTIFACT_SMOKE_CHECKS_PASSED", "flood_reference_verified": True,
              "one_worker": True, "inference": timings, "monte_carlo": simulations,
              "parallelism_decision": "No multiprocessing introduced; existing 1-worker benchmark and short serial timings do not justify it.",
              "note": "Monte Carlo checks arithmetic, separate historical metrics assess predictive error; neither establishes worksite safety."}
    for name, payload in (("examples.json", examples), ("runtime_checks.json", report)):
        (REPORT_DIR / "multidisaster" / name).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "inference": timings}, indent=2), flush=True)
    return report


if __name__ == "__main__":
    run()
