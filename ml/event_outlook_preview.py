"""One-command offline multi-event pages + canonical JSON. Starts no server."""

import argparse
import json
from pathlib import Path

from ml.config import REPORT_DIR
from ml.event_outlooks.examples import evaluate_examples, examples
from ml.event_outlooks.schema import (
    DurationForecast,
    OfficialAftershockForecast,
    OfficialEventForecast,
    OutlookBatch,
    OutlookRequest,
)
from ml.worker_preview import document, table, text


def card_html(card):
    forecast = card.forecast
    rows = [
        ("Event / notice", f"{card.event_id} / {card.notice_id or 'none'}"),
        ("Status / forecast method", f"{card.status} / {forecast.kind}"),
        (
            "Activation",
            f"{card.confirmation.status} / {card.confirmation.basis} / source {card.confirmation.source_id}",
        ),
        (
            "Actual event start / as-of UTC",
            f"{card.event_start_utc or 'unknown; not inferred'} / {card.as_of_utc}",
        ),
        (
            "Last observation / forecast issue UTC",
            f"{card.last_observation_at_utc or 'unavailable'} / {card.last_forecast_issued_at_utc or 'unavailable'}",
        ),
        (
            "Site relationship",
            f"{card.association.method}: {card.association.description}",
        ),
        ("Local hazard probability", "null — no independently validated site model"),
    ]
    detail = ""
    if isinstance(forecast, DurationForecast):
        q = forecast.remaining_duration_hours
        rows += [
            (
                "Model / estimator / target",
                f"{forecast.model_version} / {forecast.estimator} / {forecast.target_definition}",
            ),
            (
                "Remaining recorded duration (hours)",
                f"p10 {q.p10}; median {q.median}; p90 {q.p90}. Null means unidentified, not zero.",
            ),
            ("Evaluation", forecast.model_card),
        ]
        detail = table(
            [
                "Hours after as-of",
                "Recorded event still ongoing (conditional research probability)",
            ],
            [
                (p.horizon_hours, p.recorded_event_ongoing_probability)
                for p in forecast.persistence
            ],
        )
    elif isinstance(forecast, OfficialEventForecast):
        rows += [
            (
                "Provider / storm",
                f"{forecast.provider_version} / {forecast.storm_name}",
            ),
            (
                "Source / capture SHA256",
                f"{forecast.source.url} / {forecast.source.sha256}",
            ),
            (
                "Retrieved / next advisory UTC",
                f"{forecast.source.retrieved_at_utc} / {forecast.next_advisory_at_utc}",
            ),
            (
                "Duration / site wind",
                "unavailable — cyclone positions and maximum winds are regional, not a local forecast",
            ),
        ]
        detail = table(
            [
                "Forecast valid UTC",
                "Center lat / lon",
                "Max sustained wind (kt)",
                "Gust (kt)",
                "Provider phase",
            ],
            [
                (
                    p.valid_at_utc,
                    f"{p.lat}, {p.lon}",
                    p.max_sustained_wind_kt,
                    p.gust_kt,
                    p.phase,
                )
                for p in forecast.forecast_points
            ],
        )
    elif isinstance(forecast, OfficialAftershockForecast):
        m = forecast.mainshock
        rows += [
            (
                "Mainshock",
                f"{m.event_id}; M{m.magnitude}; {m.time_utc}; {m.lat}, {m.lon}",
            ),
            ("Provider", forecast.provider_version),
            (
                "Region",
                f"Circle {forecast.region.radius_km} km around {forecast.region.lat}, {forecast.region.lon}; probabilities for the entire sequence region",
            ),
            (
                "Source / capture SHA256",
                f"{forecast.source.url} / {forecast.source.sha256}",
            ),
            (
                "Retrieved / product expiration UTC",
                f"{forecast.source.retrieved_at_utc} / {forecast.expires_at_utc}",
            ),
            (
                "Earthquake remaining duration",
                "null — not an earthquake end-time prediction",
            ),
        ]
        detail = table(
            [
                "Original provider window UTC",
                "Magnitude at least",
                "P(at least one) in entire region",
                "95% expected count range",
            ],
            [
                (
                    f"{w.start_utc} to {w.end_utc} ({w.label})",
                    b.magnitude_at_least,
                    b.probability_at_least_one,
                    f"{b.count_p95_minimum}–{b.count_p95_maximum}",
                )
                for w in forecast.windows
                for b in w.bins
            ],
        )
    else:
        rows += [
            ("Why unavailable", f"{forecast.reason_code}: {forecast.reason}"),
            ("Needed", "; ".join(forecast.required_inputs) or "See reason"),
        ]
    return (
        f'<article data-event-id="{text(card.event_id)}"><h3>{text(card.event_name)}</h3>'
        + table(["Field", "Value"], rows)
        + detail
        + "<details><summary>Evidence references and limitations</summary><pre>"
        + text(json.dumps([e.model_dump(mode="json") for e in card.evidence], indent=2))
        + "</pre><ul>"
        + "".join(f"<li>{text(line)}</li>" for line in card.limitations)
        + "</ul></details></article>"
    )


def generate(output: Path, *, require_models=False):
    cases, products = examples()
    results = evaluate_examples(cases, products)
    output.mkdir(parents=True, exist_ok=True)
    sections = []
    counts = {}
    available_models = []
    for case, result in zip(cases, results, strict=True):
        response = OutlookBatch.model_validate(result["response"])
        name = result["name"]  # Fixed internal names, not an externally supplied path.
        for suffix, payload in (
            ("request", case["request"]),
            ("response", response.model_dump(mode="json")),
        ):
            (output / f"{name}.{suffix}.json").write_text(
                json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
        counts[name] = {
            "status": response.status,
            "events": len(response.event_outlooks),
            "available": sum(c.status == "available" for c in response.event_outlooks),
        }
        if (
            len(response.event_outlooks) == 1
            and isinstance(response.event_outlooks[0].forecast, DurationForecast)
            and not case.get("artifact_failure")
        ):
            available_models.append(response.event_outlooks[0].event_type)
        sections.append(
            f'<section id="{text(name)}"><h2>{text(name)}</h2><p>{text(response.site.name)} '
            f"({text(response.site.id)}) — real EIA reference location; not a verified active job. "
            f"Batch: {text(response.status)}. As-of: {text(response.as_of_utc)}.</p>"
            f'<p><a href="{name}.request.json">Canonical request</a> · <a href="{name}.response.json">Validated response</a></p>'
            + (
                "".join(card_html(card) for card in response.event_outlooks)
                or "<p>No confirmed event; no conditional forecast. Site safety remains unknown.</p>"
            )
            + "<ul>"
            + "".join(
                f"<li>{text(line)}</li>"
                for line in response.unverified_worksite_hazards
            )
            + "</ul></section>"
        )
    summary = {
        "contract_version": "ml-event-outlooks-1.0.0",
        "cases": counts,
        "qualified_models_used": sorted(available_models),
        "official_product_examples": [p.kind for p in products.values()],
        "network_requests_during_preview": 0,
        "production_eligibility": False,
        "site_hazard_probabilities_validated": False,
    }
    for name, model in (("request", OutlookRequest), ("response", OutlookBatch)):
        (output / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
        )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    nav = (
        "<nav aria-label='Examples'><ul>"
        + "".join(
            f'<li><a href="#{text(c["name"])}">{text(c["name"])}</a></li>'
            for c in cases
        )
        + "</ul></nav>"
    )
    (output / "index.html").write_text(
        document(
            "PlanIT Control — multi-event outlook preview", nav + "".join(sections)
        ),
        encoding="utf-8",
    )
    expected = {
        "Flood",
        "Flash Flood",
        "High Wind",
        "Heavy Rain",
        "Winter Storm",
        "Heat Index Exceedance",
    }
    if require_models and set(available_models) != expected:
        raise RuntimeError(
            "Preview saved with typed unavailable cards. Six trusted artifacts are required by --require-models; see ml/EVENT_OUTLOOKS.md."
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=REPORT_DIR / "event_outlook_preview"
    )
    parser.add_argument("--require-models", action="store_true")
    args = parser.parse_args()
    summary = generate(args.output, require_models=args.require_models)
    print(json.dumps(summary, indent=2))
    print(f"Open {(args.output / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
