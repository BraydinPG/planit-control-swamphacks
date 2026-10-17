"""NHC post-analysis tracks and an archived-advisory availability probe."""

from collections import Counter
from datetime import datetime, timezone
import json
import html
from pathlib import Path
import re

from ml.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached

HURDAT_URL = "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt"
TROPICAL_STATES = {"TD", "TS", "HU", "SD", "SS"}


def _coordinate(text: str, latitude: bool) -> float:
    allowed = "NS" if latitude else "EW"
    if not text or text[-1] not in allowed:
        raise ValueError("HURDAT hemisphere is invalid")
    value = float(text[:-1]) * (-1 if text[-1] in "SW" else 1)
    if not -(90 if latitude else 180) <= value <= (90 if latitude else 180):
        raise ValueError("HURDAT coordinate out of range")
    return value


def parse_hurdat(path: Path) -> tuple[list[dict], dict]:
    storms, counts = [], Counter()
    current, expected = None, 0
    for line in path.read_text(encoding="ascii").splitlines():
        fields = [part.strip() for part in line.split(",")]
        if re.fullmatch(r"AL\d{6}", fields[0]):
            if current is not None and len(current["points"]) != expected:
                raise ValueError("HURDAT storm point count differs from header")
            current = {"storm_id": fields[0], "name": fields[1], "year": int(fields[0][-4:]), "basin": "AL", "points": []}
            expected = int(fields[2])
            storms.append(current)
            continue
        if current is None or len(fields) < 8:
            raise ValueError("HURDAT row outside valid storm/header schema")
        timestamp = datetime.strptime(fields[0] + fields[1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        wind, pressure = int(fields[6]), int(fields[7])
        if wind != -99 and not 0 <= wind <= 250:
            raise ValueError("Invalid HURDAT maximum wind")
        if pressure != -999 and not 800 <= pressure <= 1100:
            raise ValueError("Invalid HURDAT pressure")
        point = {"storm_id": current["storm_id"], "valid_time_utc": timestamp.isoformat().replace("+00:00", "Z"),
                 "status": fields[3], "lat": _coordinate(fields[4], True), "lon": _coordinate(fields[5], False),
                 "max_wind_kt": None if wind == -99 else wind, "min_pressure_hpa": None if pressure == -999 else pressure,
                 "record_identifier": fields[2], "data_state": "retrospective_best_track"}
        if current["points"] and point["valid_time_utc"] <= current["points"][-1]["valid_time_utc"]:
            raise ValueError("Nonchronological HURDAT track")
        current["points"].append(point)
        counts["track_points"] += 1
        counts["missing_pressure"] += pressure == -999
        counts["missing_wind"] += wind == -99
    if current is None or len(current["points"]) != expected:
        raise ValueError("Incomplete final HURDAT storm")
    return storms, {**dict(counts), "storms": len(storms)}


def lifecycle_events(storms: list[dict], first_year: int = 2000) -> tuple[list[dict], dict]:
    events, counts = [], Counter()
    for storm in storms:
        if storm["year"] < first_year:
            continue
        points = storm["points"]
        active = [index for index, point in enumerate(points) if point["status"] in TROPICAL_STATES]
        if not active:
            counts["no_tropical_phase"] += 1
            continue
        first, last = active[0], active[-1]
        if last + 1 == len(points):
            counts["unknown_lifecycle_end_excluded"] += 1
            continue
        # The first non-tropical record after the final tropical record supplies
        # a sampled transition label. Track disappearance alone is not an end.
        start, end = points[first]["valid_time_utc"], points[last+1]["valid_time_utc"]
        if start >= end:
            counts["invalid_interval"] += 1
            continue
        events.append({"event_id": storm["storm_id"], "episode_id": storm["storm_id"],
                       "event_type": "Tropical Cyclone", "original_event_type": points[first]["status"],
                       "start_utc": start, "end_utc": end, "source_year": storm["year"],
                       "region": "North Atlantic basin; storm-scale, not a site footprint",
                       "begin_lat": points[first]["lat"], "begin_lon": points[first]["lon"],
                       "label_quality": "post_analysis_last_tropical_to_nontropical_sampled_transition",
                       "geometry_quality": "storm_center_not_site_exposure", "source": "NHC_HURDAT2"})
    return events, dict(counts)


def acquire() -> dict:
    cache = RAW_DATA_DIR / "nhc"
    pinned_report = REPORT_DIR / "multidisaster/hurdat_coverage.json"
    pinned_hash = json.loads(pinned_report.read_text(encoding="utf-8"))["source_receipt"]["sha256"] if pinned_report.exists() else None
    path, receipt = fetch_cached(HURDAT_URL, cache, filename=HURDAT_URL.rsplit("/", 1)[-1], expected_sha256=pinned_hash, max_bytes=12_000_000)
    storms, quality = parse_hurdat(path)
    events, label_quality = lifecycle_events(storms)
    selected = [storm for storm in storms if storm["year"] >= 2000]
    report = {"source": "NHC Atlantic HURDAT2 post-analysis best tracks", "source_receipt": receipt,
              "full_archive": quality, "modeled_period": "2000-2025",
              "selected_storms": len(selected), "selected_track_points": sum(len(storm["points"]) for storm in selected),
              "selected_missing_wind": sum(p["max_wind_kt"] is None for s in selected for p in s["points"]),
              "selected_missing_pressure": sum(p["min_pressure_hpa"] is None for s in selected for p in s["points"]),
              "storms_by_year": dict(sorted(Counter(storm["year"] for storm in selected).items())),
              "complete_lifecycle_intervals": len(events), "label_quality": label_quality,
              "basin": "North Atlantic only; no Pacific typhoon generalization",
              "historical_asof_availability_verified": False,
              "operational_evaluation_eligible": False,
              "limitations": ["HURDAT2 is post-storm analysis, not an operational advisory issued at the historical as-of time.",
                              "Wind is cyclone maximum sustained wind, not local site wind.",
                              "Unknown terminal phase is censored/excluded, never inferred from a disappearing track.",
                              "A sampled non-tropical transition is not dissipation, absence of hazards, or work clearance."]}
    # Examine a real issued-advisory archive without treating it as training data.
    try:
        index, index_receipt = fetch_cached("https://www.nhc.noaa.gov/archive/2024/HELENE.shtml", cache,
                                            filename="helene_2024_advisory_index.html", max_bytes=2_000_000)
        names = sorted(set(re.findall(r"/archive/2024/al09/al092024\.public\.\d+\.shtml", index.read_text(encoding="utf-8"))))
        advisories = []
        for name in names[:2]:
            page, item = fetch_cached("https://www.nhc.noaa.gov" + name, cache,
                                      filename=name.rsplit("/", 1)[-1], max_bytes=500_000)
            body = re.search(r"<pre[^>]*>(.*?)</pre>", page.read_text(encoding="utf-8"), re.S | re.I)
            if not body:
                raise ValueError("NHC advisory text product missing")
            text = html.unescape(re.sub(r"<[^>]+>", " ", body[1]))
            advisories.append({**item, "issued_time_text_excerpt": " ".join(text.split())[0:900]})
        report["operational_advisory_probe"] = {"index_receipt": index_receipt, "advisories_examined": advisories,
            "usable_storms_for_training": 0, "status": "availability_demonstrated_not_a_training_or_validation_cohort"}
    except Exception as error:
        report["operational_advisory_probe"] = {"status": "unavailable", "reason": type(error).__name__, "usable_storms_for_training": 0}
    output = PROCESSED_DATA_DIR / "multidisaster"
    output.mkdir(parents=True, exist_ok=True)
    (output / "hurdat_storms.json").write_text(json.dumps(selected, allow_nan=False), encoding="utf-8")
    (output / "hurdat_lifecycle_events.json").write_text(json.dumps(events, allow_nan=False), encoding="utf-8")
    report_path = REPORT_DIR / "multidisaster/hurdat_coverage.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[hurdat] {len(selected)} storms / {report['selected_track_points']} points; {len(events)} complete sampled lifecycle intervals", flush=True)
    return report


if __name__ == "__main__":
    acquire()
