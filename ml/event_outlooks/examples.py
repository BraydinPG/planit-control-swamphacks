"""Fixed offline inputs. Real product records, explicitly hypothetical activation."""

import copy
import hashlib
import json
from pathlib import Path

from ml.backend_adapter import ActiveEventPredictor
from ml.config import PACKAGE_ROOT
from ml.event_outlooks.official import parse_nhc, parse_oaf
from ml.event_outlooks.schema import OutlookRequest
from ml.event_outlooks.service import FLOOD_DEFINITION, EventOutlookAdapter, TrustPolicy
from ml.worker_preview import catalog

FIXTURES = PACKAGE_ROOT / "fixtures/event_outlooks"
REPLAY_POLICY = TrustPolicy(
    confirmation_sources=frozenset({"demo-activation"}),
    association_sources=frozenset({"demo-reference-association"}),
    observation_sources=frozenset({"demo-continuous-observation"}),
    allow_replay=True,
)


def verify_sources():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if Path(name).name != name or ".." in name:
            raise ValueError("Invalid fixture basename")
        body = (FIXTURES / name).read_bytes()
        if (
            len(body) != expected["bytes"]
            or hashlib.sha256(body).hexdigest() != expected["sha256"]
        ):
            raise ValueError("Official fixture checksum mismatch")


def official_products():
    verify_sources()

    def receipt(name):
        return json.loads(
            (FIXTURES / (name + ".receipt.json")).read_text(encoding="utf-8")
        )

    return {
        "helene-015": parse_nhc(
            (FIXTURES / "helene-fst-015.txt").read_bytes(),
            receipt("helene-fst-015.txt"),
        ),
        "ridgecrest-oaf": parse_oaf(
            (FIXTURES / "ridgecrest-oaf.json").read_bytes(),
            receipt("ridgecrest-oaf.json"),
            (FIXTURES / "ridgecrest-detail.json").read_bytes(),
            receipt("ridgecrest-detail.json"),
        ),
    }


def activation(
    site,
    event_type,
    *,
    asof="2024-09-27T05:00:00Z",
    start="2024-09-27T03:00:00Z",
    event_id=None,
    definition=None,
):
    return {
        "event_id": event_id or "replay-" + event_type.lower().replace(" ", "-"),
        "event_name": f"Hypothetical {event_type} activation",
        "event_type": event_type,
        "event_start_utc": start,
        "event_definition": definition
        or (
            FLOOD_DEFINITION
            if event_type == "Flood"
            else "noaa_positive_continuous_recorded_interval"
        ),
        "confirmation": {
            "status": "historical_replay",
            "basis": "hypothetical_activation",
            "source_id": "demo-activation",
            "confirmed_at_utc": asof,
            "available_at_utc": asof,
        },
        "association": {
            "site_id": site["id"],
            "method": "reference_replay",
            "source_id": "demo-reference-association",
            "description": "Hypothetical activation at a real current EIA reference location; no actual work order or historical incident linkage asserted.",
        },
        "observations": [],
    }


def examples():
    products = official_products()
    sites, _, _ = catalog()
    reference = next(s for s in sites if s.id == "eia860m-FL-59611")
    site = {k: getattr(reference, k) for k in ("id", "name", "lat", "lon", "source")}
    site["inventory_vintage"] = (
        "2026-08; reference inventory, not historical work order"
    )
    asof = "2024-09-27T05:00:00Z"
    cases = []

    def add(name, events, *, current_site=None, current_asof=asof, **extra):
        request = OutlookRequest.model_validate(
            {"site": current_site or site, "as_of_utc": current_asof, "events": events}
        )
        cases.append(
            {"name": name, "request": request.model_dump(mode="json"), **extra}
        )

    for event_type in (
        "Flood",
        "Flash Flood",
        "High Wind",
        "Heavy Rain",
        "Winter Storm",
    ):
        add(event_type.lower().replace(" ", "-"), [activation(site, event_type)])
    heat = activation(
        site,
        "Heat Index Exceedance",
        definition="observed_station_hourly_heat_index_at_or_above_90f",
    )
    heat["station_id"] = "722020-12839"
    heat["association"]["description"] = (
        "Three-station target replay (Miami 722020-12839), not measured conditions at this EIA site or validated station-to-site transfer."
    )
    add("heat-station-replay", [heat])
    storm = activation(site, "Hurricane (Typhoon)", event_id="AL092024", start=None)
    storm.update(
        event_name="Helene advisory 15 / hypothetical reference-site display",
        official_product_id="helene-015",
        event_definition=None,
    )
    add("nhc-helene-issued", [storm])
    quake_site = json.loads(
        (FIXTURES / "ridgecrest-reference-site.json").read_text(encoding="utf-8")
    )["site"]
    oaf = products["ridgecrest-oaf"]
    quake_asof = "2026-09-03T04:00:00Z"
    quake = activation(
        quake_site,
        "Earthquake",
        event_id=oaf.mainshock.event_id,
        start=oaf.mainshock.time_utc,
        asof=quake_asof,
    )
    quake.update(
        event_name="Ridgecrest official sequence forecast / regional replay",
        official_product_id="ridgecrest-oaf",
        event_definition=None,
    )
    quake["association"]["description"] = (
        "Source-backed EIA reference point inside the published 60 km OAF circle; regional probabilities apply to the sequence, never this point. No work order/impact asserted."
    )
    add(
        "usgs-aftershock-issued",
        [quake],
        current_site=quake_site,
        current_asof=quake_asof,
    )
    add("wildfire-unsupported", [activation(site, "Wildfire")])
    add("missing-model", [activation(site, "Flood")], artifact_failure="missing")
    add("corrupt-model", [activation(site, "Flood")], artifact_failure="corrupt")
    add("no-confirmed-event", [])
    pending = activation(site, "Flash Flood")
    pending["confirmation"].update(status="unconfirmed", basis="warning_only")
    add("warning-only-unconfirmed", [pending])
    add(
        "multiple-events",
        [
            activation(site, "Flood"),
            activation(site, "Flash Flood"),
            activation(site, "High Wind"),
            activation(site, "Wildfire"),
        ],
    )
    missing_storm = copy.deepcopy(storm)
    missing_storm["official_product_id"] = None
    add("nhc-product-unavailable", [missing_storm])
    missing_quake = copy.deepcopy(quake)
    missing_quake["official_product_id"] = None
    add(
        "usgs-product-unavailable",
        [missing_quake],
        current_site=quake_site,
        current_asof=quake_asof,
    )
    return cases, products


def evaluate_examples(cases, products, *, predictor=None):
    """Real reused models by default; inject only for deterministic unit tests."""
    import tempfile

    adapter = EventOutlookAdapter(
        trust_policy=REPLAY_POLICY, predictor=predictor, official_products=products
    )
    outputs = []
    for case in cases:
        if case.get("artifact_failure"):
            # Exercise actual loader failures in an isolated directory; preserve real models.
            with tempfile.TemporaryDirectory(
                prefix="planit-missing-model-"
            ) as directory:
                path = Path(directory) / "active_event.joblib"
                if case["artifact_failure"] == "corrupt":
                    path.write_bytes(b"not a trusted pickle")
                broken = ActiveEventPredictor(path, expected_sha256="0" * 64)
                response = EventOutlookAdapter(
                    trust_policy=REPLAY_POLICY, predictor=broken
                ).build(case["request"])
        else:
            response = adapter.build(case["request"])
        outputs.append(
            {"name": case["name"], "response": response.model_dump(mode="json")}
        )
    return outputs
