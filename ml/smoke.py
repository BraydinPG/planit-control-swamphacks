"""Offline replay of the public backend adapter using a labeled synthetic fixture."""

import argparse
import json
import statistics
import time
from pathlib import Path

from ml.backend_adapter import ActiveEventPredictor
from ml.config import MODEL_PATH, PACKAGE_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=MODEL_PATH)
    parser.add_argument("--fixture", type=Path, default=PACKAGE_ROOT / "fixtures/active_flood.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    context = json.loads(args.fixture.read_text(encoding="utf-8"))
    start = time.perf_counter()
    predictor = ActiveEventPredictor(args.artifact)
    cold = time.perf_counter() - start
    site = {"id": context["site_id"], "lat": 28.0, "lon": -82.7}
    durations = []
    for _ in range(100):
        start = time.perf_counter()
        result = predictor.predict_for_site(site, context)
        durations.append((time.perf_counter() - start) * 1000)
    report = {
        "status": "SYNTHETIC_ADAPTER_SMOKE_NOT_LIVE_EVENT_OR_ROUTE",
        "input": context, "output": result,
        "latency": {"cold_artifact_load_ms": cold * 1000, "warm_calls": len(durations),
                    "warm_median_ms": statistics.median(durations), "warm_p95_ms": sorted(durations)[94]},
        "missing_artifact_status": ActiveEventPredictor(args.artifact.with_name("intentionally-missing.joblib")).predict(context)["status"],
        "inactive_status": predictor.predict({**context, "event_status": "inactive"})["status"],
    }
    encoded = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
