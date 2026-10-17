"""Rebuild separate expansion artifacts from pinned sources, without reusing test labels."""

import argparse
import json
import math
import time
from pathlib import Path

from threadpoolctl import threadpool_limits

from ml.config import ARTIFACT_DIR, PACKAGE_ROOT, PROCESSED_DATA_DIR, RAW_DATA_DIR, REPORT_DIR
from ml.coverage import CATALOG_PATH, inventory, load_catalog
from ml.dispatch import read_registry
from ml.multidisaster import purged_expansion_split
from ml.predict import predict_active_event
from ml.provision import ensure_archive, file_sha256
from ml.sources.archive_cache import fetch_cached
from ml.sources.stations import STATION_IDS, parse_station, threshold_episodes
from ml.train import fit_models, load_models, save_models


def ensure_station_sources(*, download: bool = False) -> list[dict]:
    coverage = json.loads((REPORT_DIR / "multidisaster/station_coverage.json").read_text(encoding="utf-8"))
    # Use reviewed selected-station metadata, avoiding a mutable global metadata URL.
    receipts = [item for item in coverage["sources"] if item["file"].endswith(".gz")]
    all_events = []
    for station_id in STATION_IDS:
        rows = []
        for item in receipts:
            if not item["file"].startswith(station_id + "-"):
                continue
            cache = RAW_DATA_DIR / "stations"
            if not (cache / item["file"]).exists() and not download:
                raise FileNotFoundError("Pinned station file missing; use --download")
            path, _ = fetch_cached(item["url"], cache, filename=item["file"], expected_sha256=item["sha256"], max_bytes=2_000_000)
            part, _ = parse_station(path, station_id)
            rows.extend(part)
        events, _ = threshold_episodes(rows, coverage["stations"][station_id])
        all_events.extend(events)
    if len(all_events) != coverage["event_records"]:
        raise ValueError("Station episode inventory differs from pinned reference")
    return all_events


def provision(*, download: bool = False, output_dir: Path = ARTIFACT_DIR / "multidisaster") -> dict:
    started = time.perf_counter()
    manifest = json.loads((REPORT_DIR / "source_manifest.json").read_text(encoding="utf-8"))
    paths = [ensure_archive(item, RAW_DATA_DIR, download=download) for item in manifest["archives"]]
    # Recreate a normalized catalog from pinned archives; no new source discovery.
    if not CATALOG_PATH.exists():
        inventory(paths, output=PROCESSED_DATA_DIR / "multidisaster/coverage_rebuilt.json")
    else:
        expected = json.loads((REPORT_DIR / "multidisaster/coverage.json").read_text(encoding="utf-8"))["catalog_sha256"]
        # A regenerated gzip can differ only in its header; verify semantic rows
        # below via fixed cohort counts and reference predictions as well.
        if file_sha256(CATALOG_PATH) != expected:
            print("[provision] normalized gzip differs; rebuilding from verified raw archives", flush=True)
            inventory(paths, output=PROCESSED_DATA_DIR / "multidisaster/coverage_rebuilt.json")
    noaa = load_catalog()
    heat = ensure_station_sources(download=download)
    registry = read_registry()
    results = {}
    with threadpool_limits(limits=1):
        for name, entry in registry["events"].items():
            if "artifact" not in entry:
                continue
            card = json.loads((REPORT_DIR / "multidisaster" / (Path(entry["artifact"]).stem + ".json")).read_text(encoding="utf-8"))
            output = output_dir / Path(entry["artifact"]).name
            if output.exists():
                # Existing artifacts are never silently overwritten.
                model = load_models(output, expected_sha256=entry["artifact_sha256"], expected_event_type=name)
                status = "existing_checksum_verified"
            else:
                rows = heat if name == "Heat Index Exceedance" else [r for r in noaa if r["event_type"] == name and r.get("duration_hours") and r["duration_hours"] > 0]
                splits = purged_expansion_split(rows)
                for split in ("train", "validation", "test", "excluded"):
                    actual = (len(splits[split]), len({r["episode_id"] for r in splits[split]}))
                    expected = (card["split"][split]["event_records"], card["split"][split]["episode_groups"])
                    if actual != expected:
                        raise ValueError(f"{name}: reproduced cohort differs in {split}")
                print(f"[provision] fitting {name} through 2024 only; no backtest", flush=True)
                model = fit_models(splits["train"] + splits["validation"], event_type=name, source_scope=entry["target"])
                save_models(model, output)
                status = "rebuilt"
            if entry["prediction_eligible"]:
                prediction = predict_active_event(card["example_context"], model=model)
                if prediction["status"] != "ok":
                    raise ValueError(f"{name}: reference prediction unavailable")
                for horizon, expected in card["reference_ongoing_probability"].items():
                    if not math.isclose(prediction["outcomes"]["recorded_event_ongoing_probability"][horizon], expected, rel_tol=0, abs_tol=1e-10):
                        raise ValueError(f"{name}: reference prediction changed")
            checksum = file_sha256(output)
            if checksum != entry["artifact_sha256"]:
                raise ValueError(f"{name}: binary identity differs; preserve artifact and review numerical environment before deployment")
            results[name] = {"status": status, "sha256": checksum, "reference_verified": entry["prediction_eligible"]}
    receipt = {"status": "verified", "models": results, "backtests_rerun": False,
               "elapsed_seconds": time.perf_counter()-started, "production_eligibility": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "provisioning_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR / "multidisaster")
    args = parser.parse_args()
    print(json.dumps(provision(download=args.download, output_dir=args.output_dir), indent=2))


if __name__ == "__main__":
    main()
