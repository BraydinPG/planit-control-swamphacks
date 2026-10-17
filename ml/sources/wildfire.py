"""Historical NIFC perimeter investigation and FIRMS detection-only normalization."""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode

from ml.config import RAW_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached

HISTORY_LAYER = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/InterAgencyFirePerimeterHistory_All_Years_View/FeatureServer/0"


def normalize_firms_csv(path: Path, *, collection_version: str) -> list[dict]:
    """A detection is not a fire incident, perimeter, or containment measurement."""
    result = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            timestamp = datetime.strptime(row["acq_date"] + " " + row["acq_time"].zfill(4), "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
            lat, lon = float(row["latitude"]), float(row["longitude"])
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("FIRMS coordinates out of range")
            result.append({"lat": lat, "lon": lon, "valid_time_utc": timestamp.isoformat().replace("+00:00", "Z"),
                           "satellite": row.get("satellite"), "confidence_label": row.get("confidence"),
                           "collection_version": collection_version, "source_kind": "satellite_thermal_detection",
                           "incident_id": None, "containment": None,
                           "limitation": "Detection absence/disappearance is not containment or extinguishment."})
    return result


def investigate() -> dict:
    cache = RAW_DATA_DIR / "wildfire"
    report = {"status": "OFFICIAL_SOURCE_INVESTIGATION_NOT_MODEL_VALIDATION", "sources": [],
              "prediction_eligible": False, "production_eligibility": False}
    metadata, receipt = fetch_cached(HISTORY_LAYER + "?f=json", cache, filename="nifc_history_metadata.json", max_bytes=2_000_000)
    layer = json.loads(metadata.read_text(encoding="utf-8"))
    if "error" in layer:
        raise ValueError("NIFC historical layer returned an error")
    report["sources"].append(receipt)
    fields = {field["name"] for field in layer["fields"]}
    report["available_fields"] = sorted(fields)
    report["containment_field_present"] = any("contain" in field.lower() for field in fields)
    for name, where in (("all_history", "1=1"), ("requested_2021_2025", "FIRE_YEAR_INT >= 2021 AND FIRE_YEAR_INT <= 2025")):
        url = HISTORY_LAYER + "/query?" + urlencode({"f": "json", "where": where, "returnCountOnly": "true"})
        path, source = fetch_cached(url, cache, filename="nifc_" + name + "_count.json", max_bytes=100_000)
        payload = json.loads(path.read_text(encoding="utf-8"))
        report[name + "_perimeter_record_count"] = payload.get("count")
        report["sources"].append(source)
    selected = [key for key in ("IRWINID", "UNQE_FIRE_ID", "FIRE_YEAR_INT", "DATE_CUR", "GIS_ACRES", "INCIDENT", "FEATURE_CA") if key in fields]
    url = HISTORY_LAYER + "/query?" + urlencode({"f": "json", "where": "1=1", "outFields": ",".join(selected),
        "returnGeometry": "false", "resultRecordCount": 200, "orderByFields": "FIRE_YEAR_INT DESC"})
    sample, source = fetch_cached(url, cache, filename="nifc_history_sample.json", max_bytes=2_000_000)
    payload = json.loads(sample.read_text(encoding="utf-8"))
    rows = [feature["attributes"] for feature in payload.get("features", [])]
    ids = {row.get("IRWINID") or row.get("UNQE_FIRE_ID") for row in rows} - {None, ""}
    report.update({"downloaded_perimeter_sample_records": len(rows), "sample_distinct_incident_ids": len(ids),
                   "sample_years": sorted({row["FIRE_YEAR_INT"] for row in rows if row.get("FIRE_YEAR_INT")}),
                   "sample_is_not_complete_incident_history": True})
    report["sources"].append(source)
    url = HISTORY_LAYER + "/query?" + urlencode({"f": "json", "where": "FIRE_YEAR_INT >= 2021 AND FIRE_YEAR_INT <= 2025",
        "outFields": ",".join(selected), "returnGeometry": "false", "resultRecordCount": 200,
        "orderByFields": "FIRE_YEAR_INT DESC"})
    dated_sample, dated_source = fetch_cached(url, cache, filename="nifc_2021_2025_sample.json", max_bytes=2_000_000)
    dated = json.loads(dated_sample.read_text(encoding="utf-8"))
    dated_rows = [feature["attributes"] for feature in dated.get("features", [])]
    dated_ids = {row.get("IRWINID") or row.get("UNQE_FIRE_ID") for row in dated_rows} - {None, ""}
    report["requested_period_sample"] = {"records": len(dated_rows), "distinct_incident_ids": len(dated_ids),
        "years": sorted({row["FIRE_YEAR_INT"] for row in dated_rows}),
        "exceeded_transfer_limit": dated.get("exceededTransferLimit", False)}
    report["sources"].append(dated_source)
    report["limitations"] = ["Historical perimeters are mapped footprints, not timestamped containment outcomes.",
                             "A final perimeter or modification date does not reconstruct an as-of growth/containment trajectory.",
                             "The legacy interagency history layer is distinct from current WFIGS annual/perimeter feeds.",
                             "NASA FIRMS historical standard-product downloads require Earthdata archive access; no credentials were requested or fabricated.",
                             "FIRMS detection normalization is implemented and fixture-tested; no historical FIRMS detections were downloaded in this run.",
                             "No wildfire model is trained or exposed; neither hotspot disappearance nor perimeter finalization is containment."]
    output = REPORT_DIR / "multidisaster/wildfire_sources.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[wildfire] {len(rows)} sampled perimeter records / {len(ids)} incident IDs; no containment model", flush=True)
    return report


if __name__ == "__main__":
    investigate()
