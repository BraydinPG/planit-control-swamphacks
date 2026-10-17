"""T050A: one advisory card per confirmed event, from Cache's multi-event adapter.

`ml/event_outlooks` (PR #39) decides what can be forecast; this module only supplies
server-trusted inputs and maps its cards to the canonical `EventOutlookCard`.

Inputs come from data the route already authorized and loaded: supervisor-confirmed
notices covering the site, confirmed crew reports, and the site's stored readings.

- Confirmation: a supervisor-confirmed notice. A potential notice or a warning alone is
  never an active event.
- Event type: flood notices need an NWS product naming the category. "Flash Flood" and
  "Flood" are separate targets with separate models; a crew "flooding" report alone does
  not say which, so its card is unavailable. Hurricane/tropical and earthquake notices go
  to the issued NHC/USGS forecast path. Other hazards get an "unsupported" card.
- Event start: only trusted `event_start` evidence (`context.trusted_event_start`).
- Site association: verified when the notice's source report/reading belongs to this site;
  otherwise regional context, which the adapter refuses for duration research.
- Local evidence: confirmed present crew reports of the same hazard at this site.
- Official products: supplied server-side by `official_products`; none is collected live
  yet, so those cards say the issued forecast is missing.

Cards never change the score, alerts, the lightning timer, or work authorization. A
failure in the ML package or one event yields unavailable cards; the site route answers.
"""

import logging
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pydantic import ValidationError

from app.ingestion import SiteLike
from app.outlook.context import is_confirmed, is_simulated, trusted_event_start
from app.schemas import (
    CrewReport,
    EventOutlookCard,
    HazardNotice,
    HazardType,
    NoticeSource,
    Observation,
    ReviewStatus,
)

logger = logging.getLogger(__name__)

FLOOD_DEFINITION = "noaa_recorded_flood_interval"
# Server-owned evidence sources admitted by the adapter's TrustPolicy. They name backend
# pathways, never values taken from a request.
CONFIRMATION_SOURCE = "supervisor-confirmed-notice"
ASSOCIATION_SOURCE = "backend-site-link"
REPORT_SOURCE = "confirmed-crew-report"
LIMITS = [
    "Advisory only: no score, alert, lightning timer or work authorization is changed.",
    "Recorded event resolution is not worksite clearance. Local damage and exposure "
    "remain unverified.",
]
UNIDENTIFIED_FLOOD = "Flooding (category not identified)"
_ID = re.compile(r"[^A-Za-z0-9:_.-]")


def event_inputs(
    site: SiteLike,
    notices: list[HazardNotice],
    reports: list[CrewReport],
    observations: list[Observation],
    now: datetime,
) -> list[dict[str, Any]]:
    """Adapter `EventInput` dicts for each confirmed notice covering the site."""
    readings = {o.id: o for o in observations if o.id}
    events, seen = [], set()
    for notice in notices:
        if not is_confirmed(notice, now):
            continue
        replay = is_simulated(notice)
        source = readings.get(notice.source_ref) if notice.source == NoticeSource.FEED else None
        report = next((r for r in reports if r.id == notice.source_ref), None)
        event_type, official_id = _classify(notice, source, observations)
        event_id = _identifier(official_id or notice.id)
        if event_id in seen:  # one card per event; a second notice of it adds nothing
            continue
        seen.add(event_id)
        on_site = (source is not None and source.site_id == site.id) or (
            report is not None and report.site_id == site.id
        )
        start = trusted_event_start(notice)
        events.append(
            {
                "event_id": event_id,
                "notice_id": _identifier(notice.id),
                "event_name": f"{notice.hazard_label} (notice {notice.id})"[:200],
                "event_type": event_type,
                "confirmation": {
                    "status": "historical_replay" if replay else "confirmed_active",
                    "basis": "hypothetical_activation" if replay else "confirmed_worksite_report",
                    "source_id": CONFIRMATION_SOURCE,
                    "confirmed_at_utc": _utc(notice.confirmed_at),
                    "available_at_utc": _utc(notice.confirmed_at),
                },
                "association": {
                    "site_id": site.id,
                    "method": "reference_replay"
                    if replay
                    else "site_verified"
                    if on_site
                    else "regional_context",
                    "source_id": ASSOCIATION_SOURCE,
                    "description": (
                        "Simulated demo activation at this site; not a real incident."
                        if replay
                        else "The notice's source report or reading is recorded at this site."
                        if on_site
                        else "Notice radius covers the site; its source is not at this site."
                    ),
                },
                "event_start_utc": _utc(start) if start else None,
                "event_definition": FLOOD_DEFINITION if event_type == "Flood" else None,
                "observations": _local_evidence(notice, reports, site, now),
                "official_product_id": official_id,
            }
        )
    return events


def _classify(
    notice: HazardNotice, source: Observation | None, observations: list[Observation]
) -> tuple[str, str | None]:
    """(adapter event type, official product/event id or None)."""
    label = notice.hazard_label.casefold()
    if "flood" in label:
        # The notice's own NWS source decides first, so a separate site-wide warning of
        # the other kind cannot relabel it. Site readings only fill in when it names none.
        own = [str(source.value) if source else ""]
        own += [e.label for e in notice.evidence if "nws" in e.label.casefold()]
        site = [
            str(o.value)
            for o in observations
            if o.hazard_type == HazardType.FLOOD_ALERT and isinstance(o.value, str)
        ]
        for texts in (own, site):
            text = " ".join(texts).casefold()
            if "flash flood" in text:
                return "Flash Flood", None
            if "flood" in text:
                return "Flood", None
        return UNIDENTIFIED_FLOOD, None
    if "hurricane" in label or "tropical" in label:
        storm = source.source_ref if source and source.hazard_type == HazardType.HURRICANE else None
        return "Hurricane (Typhoon)", storm
    if "earthquake" in label:
        quake = (
            source.source_ref if source and source.hazard_type == HazardType.EARTHQUAKE else None
        )
        return "Earthquake", quake
    return notice.hazard_label.strip().capitalize() or "Unknown hazard", None


def _local_evidence(
    notice: HazardNotice, reports: list[CrewReport], site: SiteLike, now: datetime
) -> list[dict[str, Any]]:
    """Confirmed present reports of the same hazard at this site, available by now."""
    flood = "flood" in notice.hazard_label.casefold()
    evidence = []
    for r in reports:
        same = flood and r.category == "flooding" or r.id == notice.source_ref
        if (
            same
            and r.site_id == site.id
            and r.hazard_present
            and r.review_status == ReviewStatus.CONFIRMED
            and r.reviewed_at is not None
            and r.created_at <= r.reviewed_at <= now
        ):
            evidence.append(
                {
                    "id": _identifier(r.id),
                    "source_id": REPORT_SOURCE,
                    "valid_time_utc": _utc(r.created_at),
                    "available_at_utc": _utc(r.reviewed_at),
                }
            )
    return evidence


Builder = Callable[[dict[str, Any], Any], list[dict[str, Any]]]


class EventOutlooksService:
    """One adapter per process, created on first use. Never raises into the route."""

    def __init__(
        self,
        builder: Builder | None = None,
        official_products: Mapping[str, Any] | None = None,
        archived_examples: bool = True,
    ) -> None:
        self._builder = builder
        self._products = dict(official_products or {})
        self._archived = archived_examples
        self._error: str | None = None
        self._loaded = builder is not None
        self._lock = Lock()

    def cards(
        self, site: SiteLike, inputs: list[dict[str, Any]], now: datetime, *, demo: bool = False
    ) -> list[EventOutlookCard]:
        """Cards for `inputs`, plus labeled archived examples on demo sites."""
        builder = self._get_builder()
        unidentified = [e for e in inputs if e["event_type"] == UNIDENTIFIED_FLOOD]
        inputs = [e for e in inputs if e["event_type"] != UNIDENTIFIED_FLOOD]
        request = {
            "site": _reference_site(site),
            "as_of_utc": _utc(now),
            "events": inputs,
        }
        if builder is None:
            cards = [_unavailable(site, e, now, "ml_unavailable", self._error) for e in inputs]
        elif inputs:
            cards = self._run(builder, site, request, inputs, now, "current")
        else:
            cards = []
        cards += [
            _unavailable(
                site,
                e,
                now,
                "flood_category_unidentified",
                "no NWS product identifies whether this is a Flood or a Flash Flood, and "
                "the two use different models. A crew report alone cannot choose one",
            )
            for e in unidentified
        ]
        if demo and self._archived and builder is not None:
            cards += self._examples(site)
        return cards

    def _run(self, builder, site, request, inputs, now, presentation) -> list[EventOutlookCard]:
        try:
            raw = builder(request, self._products)
        except ValidationError:
            # A malformed event input; fall back to one card per event.
            return [
                _unavailable(site, e, now, "invalid_event_input", "Event input failed validation.")
                for e in inputs
            ]
        except Exception as exc:  # the advisory must never break the site route
            logger.warning("Event outlooks failed: %s", type(exc).__name__)
            return [
                _unavailable(site, e, now, "prediction_failed", f"{type(exc).__name__}")
                for e in inputs
            ]
        return [_card(site, item, presentation) for item in raw]

    def _examples(self, site: SiteLike) -> list[EventOutlookCard]:
        """PR #39's archived NHC/USGS products, evaluated at this site as labeled examples."""
        try:
            from ml.event_outlooks.examples import REPLAY_POLICY, activation, official_products
            from ml.event_outlooks.service import EventOutlookAdapter
        except Exception as exc:
            logger.info("Archived outlook examples unavailable: %s", type(exc).__name__)
            return []
        try:
            products = official_products()
            reference = _reference_site(site)
            storm = activation(reference, "Hurricane (Typhoon)", event_id="AL092024", start=None)
            storm |= {
                "event_name": "Hurricane Helene, NHC advisory 15 (archived 2024 example)",
                "official_product_id": "helene-015",
                "event_definition": None,
            }
            oaf = products["ridgecrest-oaf"]
            quake_asof = "2026-09-03T04:00:00Z"
            quake = activation(
                reference,
                "Earthquake",
                event_id=oaf.mainshock.event_id,
                start=oaf.mainshock.time_utc,
                asof=quake_asof,
            )
            quake |= {
                "event_name": "Ridgecrest M7.1 USGS aftershock forecast (archived example)",
                "official_product_id": "ridgecrest-oaf",
                "event_definition": None,
            }
            adapter = EventOutlookAdapter(trust_policy=REPLAY_POLICY, official_products=products)
            cards = []
            for event, asof in ((storm, "2024-09-27T05:00:00Z"), (quake, quake_asof)):
                batch = adapter.build({"site": reference, "as_of_utc": asof, "events": [event]})
                for item in batch.model_dump(mode="json")["event_outlooks"]:
                    item["limitations"] = [
                        "Historical example from an archived official product. It is not a "
                        "current prediction for this site.",
                        *item["limitations"],
                    ]
                    cards.append(_card(site, item, "historical_example"))
            return cards
        except Exception as exc:
            logger.warning("Archived outlook examples failed: %s", type(exc).__name__)
            return []

    def _get_builder(self) -> Builder | None:
        with self._lock:
            if not self._loaded:
                self._builder, self._error = _load_builder()
                self._loaded = True
            return self._builder


def _load_builder() -> tuple[Builder | None, str | None]:
    try:
        from ml.dispatch import read_registry
        from ml.event_outlooks.service import (
            EventOutlookAdapter,
            TrustPolicy,
            trusted_predictor,
        )
    except Exception as exc:  # missing package, sklearn, or a blocked native library
        return None, f"ML package not importable ({type(exc).__name__})"
    policy = TrustPolicy(
        confirmation_sources=frozenset({CONFIRMATION_SOURCE}),
        association_sources=frozenset({ASSOCIATION_SOURCE}),
        observation_sources=frozenset({REPORT_SOURCE}),
        # Replay applies only to notices the server stored as simulated (the T069 demo).
        allow_replay=True,
    )
    predictor = trusted_predictor()

    def build(request: dict[str, Any], products: Mapping[str, Any]) -> list[dict[str, Any]]:
        registry = read_registry()["events"]
        for event in request["events"]:
            entry = registry.get(event["event_type"]) or {}
            if event["event_definition"] is None and entry.get("event_definition"):
                event["event_definition"] = entry["event_definition"]
        adapter = EventOutlookAdapter(
            trust_policy=policy, predictor=predictor, official_products=products
        )
        return adapter.build(request).model_dump(mode="json")["event_outlooks"]

    return build, None


def _card(site: SiteLike, item: dict[str, Any], presentation: str) -> EventOutlookCard:
    if presentation == "current" and item.get("is_simulated"):
        presentation = "replay"
    return EventOutlookCard.model_validate(
        {
            **item,
            "site_id": site.id,
            "presentation": presentation,
            "limitations": [*item.get("limitations", []), *LIMITS],
        }
    )


def _unavailable(
    site: SiteLike, event: dict[str, Any], now: datetime, code: str, reason: str | None
) -> EventOutlookCard:
    simulated = event["confirmation"]["status"] == "historical_replay"
    return EventOutlookCard.model_validate(
        {
            "event_id": event["event_id"],
            "site_id": site.id,
            "notice_id": event.get("notice_id"),
            "event_name": event["event_name"],
            "event_type": event["event_type"],
            "presentation": "replay" if simulated else "current",
            "confirmation": event["confirmation"],
            "association": event["association"],
            "as_of_utc": now,
            "event_start_utc": event.get("event_start_utc"),
            "evidence_status": "rejected_for_forecast",
            "status": "unavailable",
            "forecast": {
                "kind": "unavailable",
                "reason_code": code,
                "reason": f"Prediction unavailable: {reason or 'the ML service is unavailable'}.",
            },
            "evidence": [],
            "limitations": LIMITS,
            "is_simulated": simulated,
            "research_only": True,
        }
    )


def _reference_site(site: SiteLike) -> dict[str, Any]:
    return {
        "id": _identifier(site.id),
        "name": (getattr(site, "name", None) or site.id)[:200],
        "lat": site.lat,
        "lon": site.lon,
        "source": (getattr(site, "source", None) or "PlanIT Control site record")[:300],
        "inventory_vintage": "PlanIT Control site record",
    }


def _identifier(value: str) -> str:
    cleaned = _ID.sub("-", value).strip("-.") or "event"
    return cleaned if cleaned[0].isalnum() else f"e{cleaned}"[:160]


def _utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


_service: EventOutlooksService | None = None


def get_event_outlooks_service() -> EventOutlooksService:
    """FastAPI dependency. One adapter (and model) per process."""
    global _service
    if _service is None:
        _service = EventOutlooksService()
    return _service
