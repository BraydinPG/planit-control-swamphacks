"""Wraps Cache's `ActiveEventPredictor` (`ml/backend_adapter.py`) for the site detail route.

- One predictor per process, created on first use. It uses the provisioning receipt's
  SHA-256 when present (`ml/INTEGRATION.md`, "Import and lifecycle").
- If the `ml` package or its dependencies can't be imported, the artifact is missing, or
  any call fails, the result is `status="unavailable"` with the reason. The route still
  answers, and scores and alerts are untouched.
- `ml` is imported from the repository root. Run the backend with the repo root on
  `PYTHONPATH` and the ML requirements installed to enable it (`ml/QUICKSTART.md`).
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pydantic import ValidationError

from app.schemas import EventOutlook, SiteSummary

logger = logging.getLogger(__name__)

Predictor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class EventOutlookService:
    def __init__(self, predictor: Predictor | None = None) -> None:
        self._predictor = predictor
        self._load_error: str | None = None
        self._loaded = predictor is not None
        self._lock = Lock()

    def outlook(self, site: SiteSummary, event_context: dict[str, Any]) -> EventOutlook:
        predictor = self._get_predictor()
        if predictor is None:
            return unavailable(event_context, self._load_error or "model unavailable")
        site_dict = {"id": site.id, "lat": site.lat, "lon": site.lon}
        try:
            return to_outlook(predictor(site_dict, event_context))
        except Exception as exc:  # the advisory must never break the site route
            logger.warning("Event outlook failed: %s", type(exc).__name__)
            return unavailable(event_context, f"outlook failed ({type(exc).__name__})")

    def _get_predictor(self) -> Predictor | None:
        with self._lock:
            if not self._loaded:
                self._predictor, self._load_error = _load_predictor()
                self._loaded = True
            return self._predictor


def to_outlook(result: dict[str, Any]) -> EventOutlook:
    """Map Cache's strict-JSON result to the compact field. Bad output becomes unavailable."""
    outcomes = result.get("outcomes") or {}
    duration = outcomes.get("remaining_duration_hours") or {}
    limitations = (result.get("worker_context") or {}).get("limitations") or []
    try:
        return EventOutlook(
            status=result.get("status"),
            event_id=result.get("event_id"),
            event_type=result.get("event_type"),
            as_of_utc=result.get("as_of_utc"),
            generated_at_utc=result.get("generated_at_utc") or datetime.now(UTC),
            ongoing_probability=outcomes.get("recorded_event_ongoing_probability") or {},
            remaining_hours_p10=duration.get("p10"),
            remaining_hours_median=duration.get("median"),
            remaining_hours_p90=duration.get("p90"),
            trend=outcomes.get("trend") or "unknown",
            model_version=result.get("model_version") or "unavailable",
            is_simulated=bool(result.get("is_simulated")),
            limitations=[str(item) for item in limitations],
        )
    except ValidationError as exc:
        return unavailable(result, f"outlook output failed validation ({exc.error_count()})")


def unavailable(context: dict[str, Any], reason: str) -> EventOutlook:
    return EventOutlook(
        status="unavailable",
        event_id=context.get("event_id"),
        event_type=context.get("event_type"),
        as_of_utc=context.get("as_of_utc"),
        generated_at_utc=datetime.now(UTC),
        model_version="unavailable",
        is_simulated=bool(context.get("is_simulated")),
        limitations=[reason],
    )


def _load_predictor() -> tuple[Predictor | None, str | None]:
    try:
        from ml.backend_adapter import ActiveEventPredictor
        from ml.config import MODEL_PATH
    except Exception as exc:  # missing package, sklearn, or a blocked native library
        return None, f"ML package not importable ({type(exc).__name__})"
    expected = None
    receipt = MODEL_PATH.with_suffix(".manifest.json")
    if receipt.exists():
        try:
            expected = json.loads(receipt.read_text(encoding="utf-8")).get("artifact_sha256")
        except (OSError, ValueError):
            return None, "model provisioning receipt unreadable"
    predictor = ActiveEventPredictor(MODEL_PATH, expected_sha256=expected)
    return predictor.predict_for_site, None


_service: EventOutlookService | None = None


def get_event_outlook_service() -> EventOutlookService:
    """FastAPI dependency. One service, and so one predictor, per process."""
    global _service
    if _service is None:
        _service = EventOutlookService()
    return _service
