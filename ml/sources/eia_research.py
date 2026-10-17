"""Read official EIA-860M workbook into representative research locations, no DB writes."""

from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from ml.config import RAW_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached
from ml.worker.schema import Point, SiteContext
from ml.worker.spatial import distance_km

EIA_URL = "https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def parse_workbook(path: Path, source_version: str) -> tuple[list[dict], dict]:
    counts = Counter()
    with zipfile.ZipFile(path) as archive:
        for name in ("xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"):
            if archive.getinfo(name).file_size > 80_000_000:
                raise ValueError("EIA worksheet exceeds bounded XML size")
        shared = [
            "".join(item.itertext())
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)
        ]
        rows = ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//s:row", NS)
    header, plants, conflicts = None, {}, set()
    for row in rows:
        values = {}
        for cell in row.findall("s:c", NS):
            column = "".join(c for c in cell.attrib["r"] if c.isalpha())
            value = cell.findtext("s:v", "", NS)
            values[column] = shared[int(value)] if cell.get("t") == "s" else value
        if header is None:
            if {"Plant ID", "Latitude", "Longitude"}.issubset(set(values.values())):
                header = {value: column for column, value in values.items()}
            continue
        counts["generator_rows"] += 1
        try:
            plant_id = str(int(values[header["Plant ID"]]))
            lat, lon = float(values[header["Latitude"]]), float(values[header["Longitude"]])
            Point(lat=lat, lon=lon)
            if lat == lon == 0:
                raise ValueError("missing coordinates")
            plant = SiteContext(
                id="eia-" + plant_id,
                name=values[header["Plant Name"]],
                lat=lat,
                lon=lon,
                site_type="representative_monitored_site",
                source="EIA-860M August 2026 operating generator inventory",
                source_version=source_version,
                is_fixture=False,
            ).model_dump()
            plant["state"] = values[header["Plant State"]]
        except (KeyError, ValueError):
            counts["invalid_or_missing_location_rows"] += 1
            continue
        if plant_id in plants:
            counts["repeated_generator_location_rows"] += 1
            if (
                distance_km(
                    Point(lat=lat, lon=lon),
                    Point(lat=plants[plant_id]["lat"], lon=plants[plant_id]["lon"]),
                )
                > 0.1
            ):
                conflicts.add(plant_id)
        else:
            plants[plant_id] = plant
    if header is None:
        raise ValueError("EIA coordinate/header schema not found")
    result = [
        site
        for key, site in sorted(plants.items(), key=lambda item: int(item[0]))
        if key not in conflicts
    ]
    return result, {
        **dict(counts),
        "coordinate_conflict_plants_excluded": len(conflicts),
        "validated_unique_plant_locations": len(result),
        "states": dict(Counter(p["state"] for p in result)),
    }


def acquire() -> dict:
    output = REPORT_DIR / "worker_outlook/eia_coverage.json"
    expected = (
        json.loads(output.read_text())["source_receipt"]["sha256"] if output.exists() else None
    )
    path, receipt = fetch_cached(
        EIA_URL,
        RAW_DATA_DIR / "worker",
        filename="august_generator2026.xlsx",
        expected_sha256=expected,
        max_bytes=20_000_000,
    )
    plants, counts = parse_workbook(path, receipt["sha256"])
    # Two geographically contrasting locations, chosen by proximity only, not hazard labels.
    selected = []
    for target in (Point(lat=27.9756, lon=-82.5333), Point(lat=33.4342, lon=-112.0116)):
        selected.append(
            min(
                plants,
                key=lambda site: distance_km(target, Point(lat=site["lat"], lon=site["lon"])),
            )
        )
    for state in sorted({p["state"] for p in plants}):
        candidate = next(
            p for p in plants if p["state"] == state and p["id"] not in {s["id"] for s in selected}
        )
        if len(selected) < 50:
            selected.append(candidate)
    if len(selected) < 50:
        raise ValueError("Insufficient unique representative locations")
    fixtures = Path(__file__).resolve().parents[1] / "fixtures/worker_outlook"
    fixtures.mkdir(parents=True, exist_ok=True)
    selected = [{k: v for k, v in site.items() if k != "state"} for site in selected]
    (fixtures / "representative_sites.json").write_text(
        json.dumps(selected, indent=2), encoding="utf-8"
    )
    report = {
        "source_receipt": receipt,
        **counts,
        "selected_research_locations": len(selected),
        "period": "August 2026",
        "backend_database_imported": False,
        "interpretation": "Real public representative plant coordinates; not verified active worksites or current hazard exposure.",
        "selection": "Two targets nearest Tampa/Phoenix airport coordinates, then deterministic state diversity; no outcome selection.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"[EIA] {counts['generator_rows']} generator rows -> {len(plants)} validated plant locations; 50 research fixtures",
        flush=True,
    )
    return report


if __name__ == "__main__":
    acquire()
