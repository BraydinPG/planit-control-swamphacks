"""One-pass inventory of requested NOAA types, including unusable point records."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import time

from ml.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, REPORT_DIR
from ml.event_types import NOAA_EVENT_TYPES
from ml.events import normalize_noaa_row
from ml.provision import ensure_archive, file_sha256

CATALOG_PATH = PROCESSED_DATA_DIR / "multidisaster" / "noaa_events.jsonl.gz"


def inventory(paths: list[Path], *, output: Path = REPORT_DIR / "multidisaster" / "coverage.json",
              catalog_path: Path = CATALOG_PATH) -> dict:
    started = time.perf_counter()
    stats = {name: {"source_rows": 0, "years": Counter(), "states": Counter(), "episodes": set(),
                    "valid_episodes": set(), "valid_positive_intervals": 0, "zero_duration": 0,
                    "unknown_end": 0, "invalid": 0, "duplicates": 0, "missing_coordinates": 0,
                    "positive_durations": []} for name in NOAA_EVENT_TYPES}
    seen = set()
    total = 0
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    archives = []
    with catalog_path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as catalog:
        for index, path in enumerate(paths, 1):
            print(f"[coverage] archive {index}/{len(paths)} {path.name}", flush=True)
            match = re.search(r"_d(\d{4})_", path.name)
            year = int(match[1]) if match else None
            archives.append({"file": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)})
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    total += 1
                    name = (row.get("EVENT_TYPE") or "").strip()
                    if name not in stats:
                        continue
                    item = stats[name]
                    item["source_rows"] += 1
                    item["years"][str(year)] += 1
                    item["states"][row.get("STATE") or "UNKNOWN"] += 1
                    item["episodes"].add(row.get("EPISODE_ID") or row.get("EVENT_ID"))
                    event_id = row.get("EVENT_ID")
                    if event_id in seen:
                        item["duplicates"] += 1
                        continue
                    seen.add(event_id)
                    try:
                        event = normalize_noaa_row(row, year, allow_zero_duration=True)
                    except ValueError:
                        item["invalid"] += 1
                        continue
                    event["original_event_type"] = name
                    event["event_category"] = NOAA_EVENT_TYPES[name].category
                    item["missing_coordinates"] += event["geometry_quality"] == "zone_only"
                    duration = event["duration_hours"]
                    if duration is None:
                        item["unknown_end"] += 1
                    elif duration == 0:
                        item["zero_duration"] += 1
                    else:
                        item["valid_positive_intervals"] += 1
                        item["positive_durations"].append(duration)
                        item["valid_episodes"].add(event["episode_id"])
                    catalog.write(json.dumps(event, allow_nan=False) + "\n")
    categories = {}
    for name, item in stats.items():
        durations = sorted(item.pop("positive_durations"))
        quantiles = {key: durations[min(len(durations) - 1, int(q * (len(durations) - 1)))] if durations else None
                     for key, q in (("p10", .1), ("median", .5), ("p90", .9))}
        categories[name] = {
            **{key: value for key, value in item.items() if key not in ("episodes", "valid_episodes")},
            "category": NOAA_EVENT_TYPES[name].category,
            "episode_count": len(item["episodes"]), "positive_interval_episode_count": len(item["valid_episodes"]),
            "positive_duration_quantiles_hours": quantiles,
            "positive_under_1h_count": sum(value < 1 for value in durations),
            "positive_over_168h_count": sum(value > 168 for value in durations),
            "state_region_count": len(item["states"]),
            "interval_model_candidate": NOAA_EVENT_TYPES[name].candidate,
            "label_limitation": NOAA_EVENT_TYPES[name].limitation,
            "historical_asof_availability_verified": False,
            "status": "inventory_only_see_registry_for_model_status",
        }
    archive_set_sha256 = hashlib.sha256(json.dumps(archives, sort_keys=True).encode()).hexdigest()
    report = {"status": "REAL_NOAA_CATEGORY_INVENTORY_NOT_MODEL_VALIDATION", "source_rows_total": total,
              "archives": archives, "catalog_sha256": file_sha256(catalog_path),
              "archive_set_sha256": archive_set_sha256,
              "categories": categories, "elapsed_seconds": time.perf_counter() - started,
              "independence_note": "NOAA episode counts are reporting groups, not a verified count of independent meteorological disasters.",
              "production_eligibility": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[coverage] {total:,} rows; report {output}; {report['elapsed_seconds']:.2f}s", flush=True)
    return report


def load_catalog(path: Path = CATALOG_PATH, event_type: str | None = None) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    # Carry connected bounds across all inventoried types, including point rows,
    # before selecting a model's type. These bounds are split metadata, not features.
    bounds = {}
    for row in rows:
        start, end = row["start_utc"], row.get("end_utc") or row["start_utc"]
        previous = bounds.get(row["episode_id"], (start, end))
        bounds[row["episode_id"]] = (min(previous[0], start), max(previous[1], end))
    return [{**row, "episode_start_utc": bounds[row["episode_id"]][0],
             "episode_end_utc": bounds[row["episode_id"]][1]}
            for row in rows if event_type is None or row["event_type"] == event_type]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output", type=Path, default=REPORT_DIR / "multidisaster/coverage.json")
    args = parser.parse_args()
    manifest = json.loads((REPORT_DIR / "source_manifest.json").read_text(encoding="utf-8"))
    paths = [ensure_archive(entry, args.input_dir) for entry in manifest["archives"]]
    inventory(paths, output=args.output)


if __name__ == "__main__":
    main()
