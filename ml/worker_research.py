"""Offline selected-duration MC consistency and site-evidence policy sensitivity."""

import json
import math

from ml.config import MODEL_PATH, REPORT_DIR
from ml.demo_worker_outlook import scenarios
from ml.dispatch import load_entry_model, read_registry
from ml.monte_carlo import simulate_model
from ml.provision import check_reference
from ml.schemas import parse_utc
from ml.train import load_models
from ml.worker.combined import build_worker_outlook


def run():
    receipt = json.loads(MODEL_PATH.with_suffix(".manifest.json").read_text())
    flood = load_models(MODEL_PATH, expected_sha256=receipt["artifact_sha256"])
    check_reference(flood, json.loads((REPORT_DIR.parent / "model_reference.json").read_text()))
    registry = read_registry()
    result = {
        "scope": "offline_internal_only",
        "new_learned_site_targets": 0,
        "new_historical_model_backtests": 0,
        "flood_reference_verified": True,
        "monte_carlo": {},
        "evidence_sensitivity": {},
        "limitations": [
            "Monte Carlo checks model-implied arithmetic, not real-world predictive accuracy.",
            "Existing 2025 historical evaluations were already inspected and were neither retuned nor rerun here.",
            "Site evidence checks concern units/time/association, without invented Brier or injury metrics.",
            "No joint wind/rain/flood probability or independent-factor multiplication is calculated.",
        ],
    }
    for case in scenarios()[:2]:
        event = case["event_context"]
        model = (
            flood
            if event["event_type"] == "Flood"
            else load_entry_model(registry["events"][event["event_type"]])
        )
        estimator = (
            "kaplan_meier"
            if event["event_type"] == "Flood"
            else registry["events"][event["event_type"]]["selected_estimator"]
        )
        elapsed = (
            parse_utc(event["as_of_utc"], "asof") - parse_utc(event["event_start_utc"], "start")
        ).total_seconds() / 3600
        simulation = simulate_model(
            model,
            elapsed_hours=elapsed,
            start_month=parse_utc(event["event_start_utc"], "start").month,
            estimator=estimator,
            trials=20000,
            seed=42,
        )
        outlook = build_worker_outlook(event, case["site_context"], case["evidence"])
        for horizon, probability in simulation["analytical_ongoing_probability"].items():
            if not math.isclose(
                probability, outlook["event_outlook"]["ongoing_probability"][horizon], abs_tol=1e-10
            ):
                raise ValueError("Combined Layer A differs from selected analytical distribution")
            tolerance = max(
                5 * math.sqrt(probability * (1 - probability) / simulation["trials"]),
                1 / simulation["trials"],
            )
            if simulation["absolute_probability_error"][horizon] > tolerance:
                raise ValueError("MC consistency outside predeclared five-standard-error tolerance")
        result["monte_carlo"][event["event_type"]] = simulation
        sensitivity = []
        for radius in (5, 25, 50):
            for age in (1, 2):
                varied = build_worker_outlook(
                    event,
                    case["site_context"],
                    case["evidence"],
                    maximum_station_km=radius,
                    observation_max_age_hours=age,
                )
                sensitivity.append(
                    {
                        "station_context_limit_km": radius,
                        "observation_max_age_hours": age,
                        "accepted_evidence": sum(item["accepted"] for item in varied["evidence"]),
                        "operational_evaluation_eligible": varied[
                            "operational_evaluation_eligible"
                        ],
                    }
                )
                if any(h["probability"] is not None for h in varied["site_hazards"]):
                    raise ValueError("Site probability invented during sensitivity analysis")
        result["evidence_sensitivity"][event["event_type"]] = sensitivity
    path = REPORT_DIR / "worker_outlook/offline_research.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(
        "[research] Flood reference, two selected-distribution MC checks and 12 evidence-policy sensitivity cases passed; no joint risk model",
        flush=True,
    )
    return result


if __name__ == "__main__":
    run()
