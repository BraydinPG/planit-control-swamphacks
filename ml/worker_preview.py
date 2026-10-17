"""Generate read-only local pages/JSON from the existing replay harness; no server."""

import argparse
import copy
from html import escape
import json
from pathlib import Path
import socket
from unittest.mock import patch

from ml.collect_hazard_sources import FIXTURES
from ml.config import REPORT_DIR
from ml.hazard_rehearsal import (
    DEMO_POLICY,
    _assert_safety,
    check_rehearsal_scope,
    verify_fixtures,
)
from ml.hazard_scenarios import activation, scenarios
from ml.worker.comprehensive import build_comprehensive_outlook
from ml.worker.comprehensive_schema import ComprehensiveOutlook, ComprehensiveRequest
from ml.worker.identity import reconcile_site

OUTPUT = REPORT_DIR / "worker_preview"
EXAMPLES = {
    "flood": (
        "Flood with captured evidence",
        "real_local_rain_and_gauge_without_basin_or_datum",
    ),
    "wind": (
        "High Wind with captured evidence",
        "real_wind_and_forecast_backend_identity",
    ),
    "missing": (
        "Missing evidence / hypothetical outage",
        "missing_credentials_and_failed_source_explicit",
    ),
}
BANNER = "DEVELOPMENT / RESEARCH / REPLAY - not a live worksite view"
CRITICAL = frozenset(
    {
        "downed_lines",
        "energized_floodwater",
        "structural_collapse",
        "chemical_release",
        "wildlife",
        "blocked_egress",
        "road_closure",
    }
)
LIMIT = (
    "All activations are hypothetical. EIA locations are reference power plants, not verified "
    "active jobs. Source freshness is evaluated at the fixed replay time, not today. No local "
    "hazard or injury probability has been validated. Field verification is required. "
    "Deterministic alerts, lightning timers and work authorization remain outside this preview."
)


def catalog():
    verify_fixtures()
    exported = json.loads((FIXTURES / "backend_sites.json").read_text(encoding="utf-8"))
    snapshot = json.loads(
        (FIXTURES / "source_snapshot.json").read_text(encoding="utf-8")
    )
    index = {r["id"]: r for r in exported["records"]}
    ids = exported["batch_site_ids"]
    if len(ids) != 50 or len(set(ids)) != 50:
        raise ValueError("Expected 50 distinct reconciled reference sites")
    sites = [
        reconcile_site(index[sid]["site"], index, snapshot["as_of_utc"]) for sid in ids
    ]
    return sites, index, snapshot


def preview_request(site_id: str, example: str, *, inputs=None, cases=None) -> dict:
    """Reuse a named rehearsal scenario, replacing site-bound provenance explicitly."""
    sites, index, snapshot = inputs if inputs is not None else catalog()
    if site_id not in {site.id for site in sites}:
        raise ValueError("Choose an ID from the 50-site reference catalog")
    if example not in EXAMPLES:
        raise ValueError("Unknown preview example")
    case_index = cases if cases is not None else {c["name"]: c for c in scenarios()}
    request = copy.deepcopy(case_index[EXAMPLES[example][1]]["request"])
    site = reconcile_site(index[site_id]["site"], index, snapshot["as_of_utc"])
    request["site_context"] = site.model_dump(mode="json")
    request["event_context"] = activation(
        request["site_context"],
        snapshot["as_of_utc"],
        request["event_context"]["event_type"],
    )
    if example != "missing":
        # A point-query receipt is valid only for its original site; never copy it from the seed.
        request["alerts"] = snapshot.get("site_alerts", {}).get(site_id, [])
        state = snapshot.get("site_alert_states", {}).get(site_id)
        request["source_states"] = [state] if state else []
    return ComprehensiveRequest.model_validate(request).model_dump(mode="json")


def evaluate_request(request: dict, *, inputs=None, predictor=None) -> dict:
    sites, index, snapshot = inputs if inputs is not None else catalog()
    validated = ComprehensiveRequest.model_validate(request)
    payload = validated.model_dump(mode="json")
    check_rehearsal_scope("supervisor", frozenset(s.id for s in sites), payload)
    reconcile_site(
        payload["site_context"], index, payload["event_context"]["as_of_utc"]
    )
    if payload["event_context"]["as_of_utc"] != snapshot["as_of_utc"]:
        # Pydantic canonicalizes UTC to Z; compare instants rather than raw spelling.
        from ml.schemas import parse_utc

        if parse_utc(payload["event_context"]["as_of_utc"], "asof") != parse_utc(
            snapshot["as_of_utc"], "snapshot"
        ):
            raise ValueError("Preview is tied to the captured replay time")
    result = build_comprehensive_outlook(
        **payload, trust_policy=DEMO_POLICY, predictor=predictor
    )
    return _assert_safety(result).model_dump(mode="json")


def text(value):
    return escape("unavailable / null" if value is None else str(value), quote=True)


def table(headers, rows):
    return (
        '<div style="overflow-x:auto"><table><thead><tr>'
        + "".join(f"<th scope=col>{text(h)}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{text(v)}</td>" for v in row) + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )


def document(title, body):
    # No scripts, external resources, untrusted HTML, or network-dependent rendering.
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        f"<title>{text(title)}</title><style>"
        "body{font:17px system-ui;line-height:1.55;max-width:1100px;margin:auto;padding:1.2rem}"
        "th,td{border:1px solid #777;padding:.5rem;text-align:left;vertical-align:top;overflow-wrap:anywhere;min-width:6rem}"
        "table{border-collapse:collapse;width:100%;font-size:.9rem}"
        "a{color:#163bb0}a:focus,summary:focus{outline:3px solid #a50}"
        "li{margin:.6rem 0}summary{cursor:pointer;padding:.7rem}"
        "aside{border:3px solid #774900;padding:1rem}section{margin:2.5rem 0}"
        "</style><body>"
        f"<header><h1>{text(title)}</h1><aside><strong>{text(BANNER)}</strong>"
        f"<p>{text(LIMIT)}</p></aside></header><main>{body}</main></body></html>"
    )


def example_html(label, request, response, stem):
    r = ComprehensiveOutlook.model_validate(response)
    event = r.event_outlook
    rows = [
        (
            "State / model / estimator",
            f"{event.status} / {event.model_version} / {event.estimator}",
        ),
        ("Target", event.target),
        (
            "Recorded-event persistence by supported horizon",
            json.dumps(event.ongoing_probability),
        ),
        (
            "Remaining recorded-duration quantiles (hours; never a clearance timer)",
            json.dumps(event.remaining_duration_hours),
        ),
        ("Trend", event.trend),
        ("Model data / fit cutoff", f"{event.data_version} / {event.fit_cutoff_utc}"),
        ("Limitations", " | ".join(event.limitations + r.limitations)),
    ]
    conditions = [
        (
            h.kind,
            c.method,
            c.variable,
            c.value,
            c.unit,
            c.value_basis,
            f"{c.valid_from} → {c.valid_to}",
            c.spatial_match.kind,
            c.evidence_id,
        )
        for h in r.site_hazards
        for c in h.conditions
    ]
    assessments = [
        (
            a.evidence.evidence_id,
            "accepted" if a.accepted else "rejected",
            a.evidence.publisher,
            "synthetic fixture" if a.evidence.is_fixture else "real captured source",
            a.evidence.method,
            a.evidence.value,
            a.evidence.unit,
            a.evidence.observed_at or a.evidence.issued_at,
            a.evidence.available_at,
            a.evidence.ingested_at,
            f"{a.evidence.valid_from} → {a.evidence.valid_to}",
            a.freshness,
            a.spatial_match.kind,
            a.spatial_match.distance_km,
            " | ".join(a.reasons),
            a.evidence.source_version,
            a.evidence.origin_url,
        )
        for a in r.evidence
    ]
    notices = [
        (
            a.alert.event,
            a.accepted,
            "synthetic fixture" if a.alert.is_fixture else "real captured notice",
            a.alert.sent,
            a.alert.updated,
            a.alert.effective,
            a.alert.expires,
            a.alert.available_at,
            a.site_spatial_match,
            " | ".join(a.reasons),
            a.alert.id,
        )
        for a in r.official_notices
    ]
    hazards = [
        (
            h.hazard_id,
            h.status,
            h.evidence_status,
            " | ".join(h.methods),
            h.probability,
            "required",
            h.description,
            " | ".join(h.unknowns),
            " | ".join(h.source_ids),
        )
        for h in r.worksite_hazards
    ]
    critical = [
        (
            h.hazard_id.replace("_", " "),
            h.status,
            "required",
            h.probability,
            h.description,
        )
        for h in r.worksite_hazards
        if h.hazard_id in CRITICAL
    ]
    hazard_headers = (
        "Hazard",
        "Status",
        "Evidence state",
        "Method",
        "Local probability",
        "Field verification",
        "Review question",
        "Unknowns",
        "Source IDs",
    )
    return (
        f'<section id="{stem.rsplit("-", 1)[-1]}"><h2>{text(label)}</h2>'
        f"<p>Hypothetical {text(r.event_type)} activation; historical_replay / simulated=true. "
        f"As of {text(r.as_of_utc)}. Generated {text(r.generated_at_utc)}. "
        f"Contract {text(r.contract_version)}; overall {text(r.status)}.</p>"
        "<details><summary>Replay confirmation provenance</summary>"
        + table(("Field", "Value"), request["event_context"]["confirmation"].items())
        + "</details>"
        f'<p><a href="{stem}-request.json">Canonical request JSON</a> · '
        f'<a href="{stem}-response.json">Canonical response JSON</a></p>'
        "<h3>Unmeasured worker hazards — verify in the field</h3>"
        + table(
            (
                "Hazard",
                "Status",
                "Field verification",
                "Local probability",
                "Review question",
            ),
            critical,
        )
        + "<h3>Layer A — event-duration research</h3>"
        + table(("Field", "Result"), rows)
        + "<h3>Layer B — qualified environmental conditions</h3>"
        + (
            table(
                (
                    "Hazard",
                    "Method",
                    "Variable",
                    "Value",
                    "Unit",
                    "Basis",
                    "Valid window",
                    "Association",
                    "Evidence ID",
                ),
                conditions,
            )
            if conditions
            else "<p>Unavailable: no qualified environmental conditions supplied.</p>"
        )
        + "<h3>Official notices at the replay time</h3>"
        + (
            table(
                (
                    "Event",
                    "Accepted",
                    "Origin",
                    "Sent",
                    "Updated",
                    "Effective",
                    "Expires",
                    "Available",
                    "Site association",
                    "Reasons",
                    "ID",
                ),
                notices,
            )
            if notices
            else "<p>No notices supplied for this replay; this does not establish absence of hazards.</p>"
        )
        + "<h3>Source availability</h3>"
        + table(
            ("Provider", "State at replay", "Attempted", "Last capture", "Reason"),
            [
                (s.provider, s.state, s.attempted, s.last_success_at, s.reason)
                for s in r.source_availability
            ],
        )
        + "<details><summary>All worker hazards and verification questions</summary>"
        + table(hazard_headers, hazards)
        + "</details>"
        + "<details><summary>All supplied evidence: provenance, freshness and rejection reasons</summary>"
        + table(
            (
                "ID",
                "Decision",
                "Publisher",
                "Origin",
                "Method",
                "Value",
                "Unit",
                "Observed / issued",
                "Available",
                "Ingested",
                "Valid window",
                "Freshness at replay",
                "Association",
                "Distance km",
                "Reasons",
                "Revision",
                "Source URL",
            ),
            assessments,
        )
        + "</details><p>"
        + text(r.safety_statement)
        + "</p></section>"
    )


def terminal_summary(label, response):
    r = ComprehensiveOutlook.model_validate(response)
    accepted = [a for a in r.evidence if a.accepted]
    return "\n".join(
        [
            f"{label}: {r.site.name} ({r.site.id})",
            f"  REPLAY {r.event_type}; as-of {r.as_of_utc}; contract {r.contract_version}",
            f"  Layer A: {r.event_outlook.status}; model {r.event_outlook.model_version}",
            f"  Regional recorded-event persistence: {json.dumps(r.event_outlook.ongoing_probability)}",
            f"  Layer B: {len(accepted)} accepted / {len(r.evidence) - len(accepted)} rejected evidence; "
            f"{sum(a.accepted for a in r.official_notices)} qualified notices at replay time",
            "  Accepted methods: "
            + (
                ", ".join(sorted({a.evidence.method for a in accepted}))
                or "unavailable"
            ),
            "  Field verification required: "
            + "; ".join(
                f"{h.hazard_id}={h.status}"
                for h in r.worksite_hazards
                if h.hazard_id in CRITICAL
            ),
            "  Local hazard probabilities: null. No work authorization or alert control.",
        ]
    )


def generate(
    output: Path = OUTPUT, *, site_id=None, require_models=False, predictor=None
):
    inputs = catalog()
    sites, _, snapshot = inputs
    if site_id is not None:
        if site_id not in {s.id for s in sites}:
            raise ValueError("Choose an ID from the 50-site reference catalog")
        sites = [s for s in sites if s.id == site_id]
    cases = {c["name"]: c for c in scenarios()}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    navigation, site_results, summaries = [], [], []
    with (
        patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("Preview attempted network access"),
        ),
        patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("Preview attempted network access"),
        ),
    ):
        for ordinal, site in enumerate(sites, start=1):
            page = f"site-{ordinal:03d}"
            navigation.append(
                f'<li><a href="{page}.html">{text(site.name)} — {text(site.id)}</a></li>'
            )
            sections, counts = [], {}
            for key, (label, _) in EXAMPLES.items():
                request = preview_request(site.id, key, inputs=inputs, cases=cases)
                response = evaluate_request(request, inputs=inputs, predictor=predictor)
                if (
                    require_models
                    and key != "missing"
                    and response["event_outlook"]["status"] != "supported_research"
                ):
                    raise ValueError(
                        "Pinned duration model unavailable; see ml/WORKER_PREVIEW.md provisioning"
                    )
                stem = f"{page}-{key}"
                for suffix, payload in (("request", request), ("response", response)):
                    (output / f"{stem}-{suffix}.json").write_text(
                        json.dumps(payload, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8",
                    )
                sections.append(example_html(label, request, response, stem))
                counts[key] = {
                    "event_status": response["event_outlook"]["status"],
                    "accepted_evidence": sum(
                        a["accepted"] for a in response["evidence"]
                    ),
                    "accepted_notices": sum(
                        a["accepted"] for a in response["official_notices"]
                    ),
                }
                if (ordinal == 1 and key in ("flood", "missing")) or (
                    ordinal == min(2, len(sites)) and key == "wind"
                ):
                    summaries.append(terminal_summary(label, response))
            body = (
                '<p><a href="index.html">Choose reference site</a> · '
                '<a href="#flood">Flood</a> · <a href="#wind">High Wind</a> · <a href="#missing">Missing evidence</a></p>'
                f"<p>{text(site.name)} · {text(site.id)} · lat {site.lat}, lon {site.lon}. "
                f"EIA reference revision {text(site.source_version)}.</p>"
                + "".join(sections)
            )
            (output / f"{page}.html").write_text(
                document(site.name, body), encoding="utf-8"
            )
            site_results.append(
                {"site_id": site.id, "page": page + ".html", "examples": counts}
            )
    for name, schema in (
        ("request", ComprehensiveRequest),
        ("response", ComprehensiveOutlook),
    ):
        (output / f"{name}.schema.json").write_text(
            json.dumps(schema.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )
    report = {
        "task_id": "T087",
        "contract_version": "2.1.0",
        "as_of_utc": snapshot["as_of_utc"],
        "sites": site_results,
        "validated_outputs": len(sites) * len(EXAMPLES),
        "sites_with_captured_environmental_evidence": sum(
            s["examples"]["flood"]["accepted_evidence"] > 0 for s in site_results
        ),
        "sites_with_captured_notices": sum(
            s["examples"]["flood"]["accepted_notices"] > 0 for s in site_results
        ),
        "is_actual_incident": False,
        "local_probability_validated": False,
    }
    (output / "acceptance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    body = (
        f"<p>Fixed source snapshot: {text(snapshot['as_of_utc'])}. {len(sites)} reference sites; "
        f"{report['validated_outputs']} validated responses. "
        f"{report['sites_with_captured_environmental_evidence']} sites with qualified captured environmental evidence; "
        f"{report['sites_with_captured_notices']} with qualified notices. Other sites have explicit evidence gaps.</p>"
        '<nav aria-label="Reference sites"><h2>Choose a reference site</h2><ul>'
        + "".join(navigation)
        + "</ul></nav>"
        '<p><a href="acceptance.json">Acceptance counts</a> · <a href="request.schema.json">Request schema</a> · '
        '<a href="response.schema.json">Response schema</a></p>'
    )
    (output / "index.html").write_text(
        document("FORESITE worker-outlook developer preview", body), encoding="utf-8"
    )
    (output / "preview.txt").write_text(
        BANNER + "\n" + LIMIT + "\n\n" + "\n\n".join(summaries) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--site-id",
        help="One exact ID from the reconciled 50-site catalog (default: all)",
    )
    parser.add_argument("--require-models", action="store_true")
    args = parser.parse_args()
    try:
        report = generate(
            args.output, site_id=args.site_id, require_models=args.require_models
        )
    except ValueError as exc:
        parser.exit(2, f"Preview unavailable: {exc}\n")
    print((args.output / "preview.txt").read_text(encoding="utf-8"))
    print(
        f"PASS: {report['validated_outputs']} validated outputs / {len(report['sites'])} reference sites"
    )
    print(f"Open: {(args.output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
