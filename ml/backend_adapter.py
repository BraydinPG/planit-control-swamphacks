"""Importable advisory boundary for Rudra; no routes, scores, or alert mutation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ml.config import MODEL_PATH
from ml.predict import predict_active_event
from ml.schemas import unavailable_result, validate_event_context
from ml.train import load_models


class ActiveEventPredictor:
    """Load a trusted artifact once per backend process. Recreate after provisioning.

    Pin expected_sha256 to a trusted provisioning receipt when deploying. A hash
    verifies file identity, not trust in a pickle received from an unknown source.
    """

    def __init__(self, artifact_path: Path = MODEL_PATH, *, expected_sha256: str | None = None) -> None:
        self._model = None
        self._load_error = None
        self._expansion_models = {}
        self._registry = None
        try:
            from ml.dispatch import read_registry
            self._registry = read_registry()
        except (OSError, ValueError):
            pass
        try:
            self._model = load_models(artifact_path, expected_sha256=expected_sha256)
        except Exception as error:
            self._load_error = f"trained artifact unavailable ({type(error).__name__})"

    def predict(self, event_context: dict[str, Any]) -> dict[str, Any]:
        if isinstance(event_context, dict) and str(event_context.get("event_type", "")).casefold() != "flood":
            from ml.dispatch import predict_expansion
            from ml.predict import _json_safe
            # Let the public boundary handle malformed and inactive inputs first.
            try:
                normalized = validate_event_context(event_context)
            except (ValueError, TypeError):
                return predict_active_event(event_context)
            return _json_safe(predict_expansion(normalized, registry=self._registry, model_cache=self._expansion_models))
        if self._model is None:
            return unavailable_result(event_context, self._load_error or "model unavailable")
        return predict_active_event(event_context, model=self._model)

    def predict_for_site(self, site: dict[str, Any], event_context: dict[str, Any]) -> dict[str, Any]:
        """Associate validated representative-site coordinates without claiming exposure.

        The caller must authorize site access and confirm the active event first.
        This method does not infer activation or geographic event-site overlap.
        """
        if not isinstance(site, dict) or not isinstance(site.get("id"), str) or not site["id"].strip():
            return unavailable_result(event_context, "site.id is required")
        for key, lower, upper in (("lat", -90, 90), ("lon", -180, 180)):
            value = site.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
                return unavailable_result(event_context, f"site.{key} is invalid")
        try:
            validate_event_context(event_context)
        except (TypeError, ValueError) as error:
            return unavailable_result(event_context, str(error))
        if event_context.get("site_id") not in (None, site["id"]):
            return unavailable_result(event_context, "event context is associated with a different site")
        result = self.predict({**event_context, "site_id": site["id"]})
        result["site_association"] = {
            "site_id": site["id"], "lat": float(site["lat"]), "lon": float(site["lon"]),
            "interpretation": "representative_monitored_location;_event_exposure_not_established_by_coordinates",
        }
        return result
