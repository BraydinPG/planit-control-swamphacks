"""Compose one independent, type-aware advisory per event; never rank site risk."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

from ml.backend_adapter import ActiveEventPredictor
from ml.config import MODEL_PATH
from ml.dispatch import read_registry
from ml.event_outlooks.schema import (
    DurationForecast,
    EventOutlook,
    OfficialAftershockForecast,
    OfficialEventForecast,
    OutlookBatch,
    OutlookRequest,
    RemainingDuration,
    UnavailableForecast,
)
from ml.schemas import parse_utc
from ml.worker.schema import Point
from ml.worker.spatial import distance_km

FLOOD_DEFINITION = "noaa_recorded_flood_interval"
LIMITS = [
    "Recorded event resolution is not worksite clearance. Local damage and exposure remain unverified.",
    "No site hazard probability is validated; no score, alert, lightning timer or work authorization is changed.",
]


@dataclass(frozen=True)
class TrustPolicy:
    """Server-owned allowlists, never copied from an untrusted request or token claim.

    This is evidence admission, not authentication. Authorize site access upstream.
    A label or these source IDs alone cannot establish real confirmation.
    """

    confirmation_sources: frozenset[str] = frozenset()
    association_sources: frozenset[str] = frozenset()
    observation_sources: frozenset[str] = frozenset()
    allow_replay: bool = False


def trusted_predictor() -> ActiveEventPredictor:
    """Require the existing trusted local Flood provisioning receipt before loading."""
    try:
        receipt = json.loads(
            MODEL_PATH.with_suffix(".manifest.json").read_text(encoding="utf-8")
        )
        checksum = receipt["artifact_sha256"]
        if (
            not re.fullmatch(r"[a-f0-9]{64}", checksum)
            or receipt.get("reference_predictions_verified") is not True
        ):
            raise ValueError("Unverified artifact receipt")
    except (OSError, KeyError, ValueError, TypeError):
        # Keep qualified expansion dispatch usable; never deserialize an unreceipted Flood model.
        return ActiveEventPredictor(
            MODEL_PATH.with_name("unprovisioned-event-preview.joblib")
        )
    return ActiveEventPredictor(MODEL_PATH, expected_sha256=checksum)


class EventOutlookAdapter:
    def __init__(
        self,
        *,
        trust_policy: TrustPolicy | None = None,
        predictor=None,
        official_products: Mapping[
            str, OfficialEventForecast | OfficialAftershockForecast
        ]
        | None = None,
    ):
        self.policy = trust_policy or TrustPolicy()
        self.predictor = predictor
        # Revalidate independent immutable copies, so a malformed supplied product fails explicitly.
        self.products = dict(official_products or {})

    def build(self, request: OutlookRequest | dict) -> OutlookBatch:
        request = OutlookRequest.model_validate(request)
        cards = [self._event(request, event) for event in request.events]
        count = sum(card.status == "available" for card in cards)
        status = (
            "not_applicable"
            if not cards or all(c.status == "not_applicable" for c in cards)
            else "available"
            if count == len(cards)
            else "partial"
            if count
            else "unavailable"
        )
        return OutlookBatch(
            site=request.site,
            as_of_utc=request.as_of_utc,
            status=status,
            event_outlooks=cards,
        )

    def _event(self, request, event) -> EventOutlook:
        asof = parse_utc(request.as_of_utc, "asof")
        confirmation = event.confirmation
        replay = confirmation.status == "historical_replay"
        valid_times = [
            o.valid_time_utc
            for o in event.observations
            if parse_utc(o.valid_time_utc, "observed") <= asof
        ]
        base = {
            "event_id": event.event_id,
            "notice_id": event.notice_id,
            "event_name": event.event_name,
            "event_type": event.event_type,
            "confirmation": confirmation,
            "association": event.association,
            "as_of_utc": request.as_of_utc,
            "event_start_utc": event.event_start_utc,
            "last_observation_at_utc": max(
                valid_times, key=lambda t: parse_utc(t, "observed"), default=None
            ),
            "last_forecast_issued_at_utc": None,
            "evidence": event.observations,
            "is_simulated": replay,
            "research_only": True,
        }

        def unavailable(code, reason, *, required=(), not_applicable=False):
            rejected = {**base, "last_observation_at_utc": None}
            return EventOutlook(
                **rejected,
                evidence_status="rejected_for_forecast",
                status="not_applicable" if not_applicable else "unavailable",
                forecast=UnavailableForecast(
                    reason_code=code, reason=reason, required_inputs=list(required)
                ),
                limitations=LIMITS,
            )

        if confirmation.status in {"unconfirmed", "resolved"}:
            return unavailable(
                "no_confirmed_active_event",
                "No qualifying confirmed active event supplied; this says nothing about site safety.",
                not_applicable=True,
            )
        if replay and not self.policy.allow_replay:
            return unavailable(
                "replay_not_enabled",
                "Historical replay requires a caller-owned explicit development policy.",
            )
        if confirmation.basis in {"warning_only", "none"}:
            return unavailable(
                "independent_confirmation_required",
                "A warning or forecast alone does not confirm that a continuous recorded event is active.",
            )
        if confirmation.source_id not in self.policy.confirmation_sources:
            return unavailable(
                "untrusted_confirmation",
                "Confirmation must come from an admitted trusted ingestion/review source.",
            )
        if not replay and confirmation.basis in {
            "historical_record",
            "hypothetical_activation",
        }:
            return unavailable(
                "replay_mislabeled",
                "Historical records and hypothetical activation cannot establish live confirmation.",
            )
        if not confirmation.confirmed_at_utc or not confirmation.available_at_utc:
            return unavailable(
                "confirmation_time_missing",
                "Confirmation and availability timestamps are required.",
            )
        confirmed = parse_utc(confirmation.confirmed_at_utc, "confirmed")
        available = parse_utc(confirmation.available_at_utc, "available")
        if not confirmed <= available <= asof:
            return unavailable(
                "late_confirmation",
                "Confirmation must be available by as-of and cannot precede its confirmation time.",
            )
        if (
            event.event_start_utc
            and parse_utc(event.event_start_utc, "start") > confirmed
        ):
            return unavailable(
                "invalid_event_start",
                "Actual event start must precede confirmation; notice creation is not a substitute.",
            )
        association = event.association
        if (
            association.site_id != request.site.id
            or association.method == "unknown"
            or association.source_id not in self.policy.association_sources
        ):
            return unavailable(
                "site_association_unverified",
                "Event/site identity and a trusted spatial relationship must be independently verified.",
            )
        if not replay and association.method == "reference_replay":
            return unavailable(
                "site_association_unverified",
                "A reference replay relationship cannot qualify a live site.",
            )
        for observation in event.observations:
            valid = parse_utc(observation.valid_time_utc, "observation")
            acquired = parse_utc(observation.available_at_utc, "availability")
            if observation.source_id not in self.policy.observation_sources:
                return unavailable(
                    "untrusted_observation",
                    "Evidence source not admitted by the caller-owned policy.",
                )
            if valid > acquired or acquired > asof:
                return unavailable(
                    "future_or_late_evidence",
                    "Observations must have occurred and been available by as-of.",
                )

        if event.event_type in {
            "Hurricane (Typhoon)",
            "Tropical Storm",
            "Tropical Depression",
            "Earthquake",
        }:
            try:
                return self._official(request, event, base, unavailable)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                return unavailable(
                    "official_product_invalid",
                    "The supplied official product failed validation; no substitute forecast is inferred.",
                )

        try:
            entry = read_registry()["events"].get(event.event_type)
        except (OSError, ValueError, KeyError, TypeError):
            return unavailable(
                "registry_unavailable", "The qualified model registry is unavailable."
            )
        if event.event_type == "Flood":
            definition, horizons = FLOOD_DEFINITION, [6, 12, 24]
        elif (
            entry
            and entry.get("prediction_eligible") is True
            and entry.get("status") == "evaluated_research"
        ):
            definition, horizons = (
                entry["event_definition"],
                entry["supported_horizons_hours"],
            )
        else:
            return unavailable(
                "unsupported_target",
                "No qualified event-specific forecast exists for this target; no other model is substituted.",
                required=(
                    "Target-specific as-of time-series labels, baseline and independent historical evaluation",
                ),
            )
        if event.event_definition != definition:
            return unavailable(
                "target_definition_mismatch",
                "The exact separately evaluated event definition is required.",
                required=(definition,),
            )
        if not event.event_start_utc:
            return unavailable(
                "event_start_missing",
                "Actual event start is required to condition on event age; notice/warning creation time is not used.",
            )
        if not replay:
            if association.method != "site_verified" or not event.observations:
                return unavailable(
                    "local_confirmation_missing",
                    "Duration research requires independently verified site association and current local evidence.",
                )
            if asof - confirmed > timedelta(hours=1) or any(
                asof - parse_utc(o.valid_time_utc, "valid") > timedelta(hours=1)
                for o in event.observations
            ):
                return unavailable(
                    "stale_local_confirmation",
                    "Independent local confirmation must be current within one hour.",
                )
        if self.predictor is None:
            self.predictor = trusted_predictor()
        context = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "event_status": confirmation.status,
            "event_definition": definition,
            "event_start_utc": event.event_start_utc,
            "as_of_utc": request.as_of_utc,
            "site_id": request.site.id,
            "is_simulated": replay,
            "station_id": event.station_id,
            "location": {
                "lat": request.site.lat,
                "lon": request.site.lon,
                "spatial_match_quality": "region_only" if replay else "site_verified",
            },
            "evidence": [
                {
                    "id": o.id,
                    "source": o.source_id,
                    "valid_time_utc": o.valid_time_utc,
                    "available_at_utc": o.available_at_utc,
                }
                for o in event.observations
            ],
        }
        try:
            result = self.predictor.predict_for_site(request.site.model_dump(), context)
            if result["status"] != "ok":
                return unavailable(
                    "model_unavailable",
                    "; ".join(
                        result.get("worker_context", {}).get(
                            "limitations",
                            ["Event-specific artifact or evidence unavailable"],
                        )
                    ),
                )
            outcomes = result["outcomes"]
            probabilities = outcomes["recorded_event_ongoing_probability"]
            if set(probabilities) != {f"{h}h" for h in horizons}:
                raise ValueError("Model horizons contradict the registry")
            duration = outcomes["remaining_duration_hours"]
            forecast = DurationForecast(
                target_definition=definition,
                model_version=result["model_version"],
                estimator=result["estimator"],
                persistence=[
                    {
                        "horizon_hours": h,
                        "recorded_event_ongoing_probability": probabilities[f"{h}h"],
                    }
                    for h in horizons
                ],
                remaining_duration_hours=RemainingDuration(
                    **{k: duration.get(k) for k in ("p10", "median", "p90")}
                ),
                model_card=result["evidence_quality"].get(
                    "model_card", "ml/EVALUATION.md"
                ),
                training_support_at_event_age=result["evidence_quality"].get(
                    "support_at_current_event_age"
                ),
            )
        except Exception as error:  # noqa: BLE001 - isolate model/serialization failures per card
            # Fail one card, preserve other events. Do not expose paths or exception text.
            return unavailable(
                "prediction_failed",
                f"Event-specific prediction unavailable ({type(error).__name__}); other event cards remain independent.",
            )
        return EventOutlook(
            **base,
            evidence_status="accepted_for_research",
            status="available",
            forecast=forecast,
            limitations=[
                *LIMITS,
                "Historical research, not operational validation. Previously inspected 2025 data is not a fresh holdout.",
                "Duration intervals can be poorly calibrated even when persistence passes its research gate; unidentified quantiles remain null.",
                "Reference inventory coordinates do not establish historical worksite conditions.",
                *result.get("worker_context", {}).get("limitations", []),
            ],
        )

    def _official(self, request, event, base, unavailable):
        product = self.products.get(event.official_product_id)
        quake = event.event_type == "Earthquake"
        expected_type = OfficialAftershockForecast if quake else OfficialEventForecast
        if not isinstance(product, expected_type):
            return unavailable(
                "official_forecast_missing",
                "No matching published USGS OAF product."
                if quake
                else "No qualifying current issued NHC forecast; retrospective HURDAT is not a substitute.",
            )
        product = expected_type.model_validate(product.model_dump(mode="json"))
        expected_id = product.mainshock.event_id if quake else product.cyclone_id
        if event.event_id != expected_id:
            return unavailable(
                "official_event_mismatch",
                "Issued product and confirmed event identities differ.",
            )
        if not quake:
            phase_type = {
                "HURRICANE": "Hurricane (Typhoon)",
                "TROPICAL STORM": "Tropical Storm",
                "TROPICAL DEPRESSION": "Tropical Depression",
            }.get(product.initial_position.phase)
            if phase_type != event.event_type:
                return unavailable(
                    "official_event_type_mismatch",
                    "Event type must match the issued advisory's current cyclone phase.",
                )
        if quake and event.event_start_utc != product.mainshock.time_utc:
            return unavailable(
                "mainshock_time_mismatch",
                "Confirmed event time must match the published mainshock origin.",
            )
        asof = parse_utc(request.as_of_utc, "asof")
        source = product.source
        base["last_forecast_issued_at_utc"] = (
            source.issued_at_utc
            if parse_utc(source.issued_at_utc, "issued") <= asof
            else None
        )
        if parse_utc(source.issued_at_utc, "issued") > asof:
            return unavailable(
                "future_issued_forecast",
                "The official forecast was issued after the requested as-of.",
            )
        sources = [source, product.mainshock_source] if quake else [source]
        for record in sources:
            if parse_utc(record.issued_at_utc, "issued") > asof:
                return unavailable(
                    "late_source_revision",
                    "The associated official source revision postdates as-of.",
                )
            if not base["is_simulated"] and (
                record.vintage != "contemporaneous_capture"
                or not record.available_at_utc
                or parse_utc(record.available_at_utc, "available") > asof
                or parse_utc(record.retrieved_at_utc, "retrieved") > asof
            ):
                return unavailable(
                    "historical_availability_unverified",
                    "An archive capture does not prove operational availability at the historical as-of; use explicit replay.",
                )
        expires = product.expires_at_utc if quake else product.next_advisory_at_utc
        if asof >= parse_utc(expires, "expires"):
            return unavailable(
                "official_forecast_stale",
                "The official forecast expired or its next advisory was due; no current product is substituted.",
            )
        if quake:
            if (
                distance_km(
                    Point(lat=request.site.lat, lon=request.site.lon),
                    Point(lat=product.region.lat, lon=product.region.lon),
                )
                > product.region.radius_km
            ):
                return unavailable(
                    "outside_aftershock_region",
                    "The reference site is outside the provider's sequence region; no site probability is inferred.",
                )
            # Completed provider windows are not reinterpreted as forecasts from now.
            product = product.model_copy(
                update={
                    "windows": [
                        w for w in product.windows if parse_utc(w.end_utc, "end") > asof
                    ]
                }
            )
            if not product.windows:
                return unavailable(
                    "official_forecast_stale",
                    "No unexpired provider forecast windows remain.",
                )
        base["research_only"] = False
        return EventOutlook(
            **base,
            evidence_status="issued_provider_product",
            status="available",
            forecast=product,
            limitations=[
                *LIMITS,
                "Issued provider forecast, not a locally validated ML prediction. Archive retrieval does not prove historical operational availability.",
                "Aftershock probabilities describe the entire provider sequence region and exact original windows, never a point-site probability or earthquake end time."
                if quake
                else "Forecast positions and maximum sustained winds are cyclone-scale; center distance does not yield local wind, inundation, event end or clearance.",
                "Hypothetical activation / reference-site display; not a verified worker-site incident."
                if base["is_simulated"]
                else "Site conditions require separate observations and qualified inspection.",
            ],
        )
