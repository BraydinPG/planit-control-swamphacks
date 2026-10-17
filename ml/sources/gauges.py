"""Bounded USGS historical water-level feasibility probe; no Flood model change."""

import json
from urllib.parse import urlencode

from ml.config import RAW_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached


def investigate() -> dict:
    query = {"f": "json", "monitoring_location_id": "USGS-02303000", "parameter_code": "00065",
             "datetime": "2024-10-08T00:00:00Z/2024-10-09T00:00:00Z", "limit": 1000}
    url = "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?" + urlencode(query)
    report = {"source": "USGS Water Data OGC continuous observations", "prediction_eligible": False,
              "station": "USGS-02303000", "parameter_code": "00065", "target": "gage height",
              "limitations": ["Feasibility sample only; no trained gauge-to-event or gauge-to-worksite matching.",
                              "Gage datum and locally documented flood stage are required before threshold labels.",
                              "Revised approved observations are not guaranteed to be the originally issued values.",
                              "The existing Flood model and its features remain unchanged."]}
    try:
        path, receipt = fetch_cached(url, RAW_DATA_DIR / "gauges", filename="usgs_02303000_height_20241008.json", max_bytes=4_000_000)
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = [row["properties"] for row in payload.get("features", [])]
        if "features" not in payload:
            raise ValueError("USGS response is not a feature collection")
        approvals = [r.get("approval_status") for r in rows if r.get("approval_status")]
        report.update({"status": "ingestion_only", "source_receipt": receipt, "records": len(rows),
                       "first_time": min((r["time"] for r in rows), default=None),
                       "last_time": max((r["time"] for r in rows), default=None),
                       "units": sorted({r.get("unit_of_measure", "unknown") for r in rows}),
                       "approval_states": sorted({s for value in approvals for s in (value if isinstance(value, list) else [value])})})
    except Exception as error:
        report.update({"status": "source_unavailable", "records": 0, "reason": type(error).__name__})
    output = REPORT_DIR / "multidisaster/gauge_sources.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[gauges] {report['status']}: {report['records']} historical measurements; no new flood target", flush=True)
    return report


if __name__ == "__main__":
    investigate()
