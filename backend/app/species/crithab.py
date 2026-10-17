"""USFWS critical habitat map service adapter (ArcGIS FeatureServer, public, no key).

Layer 0 is final critical habitat, layer 2 proposed. Features carry the species name,
`entity_id` (the same id as IPaC's `Population$Sid[...]`), Federal Register citation and
publication date. Boundaries are simplified by the service and clipped here to the map
window, so the overlay stays small. A boundary the simplification erased is kept as an
area with `geometry=None` and a note, never dropped.
"""

from datetime import date
from typing import Any

import httpx

from app.ingestion.base import FeedError
from app.ingestion.json_client import DEFAULT_USER_AGENT
from app.schemas import CriticalHabitatArea
from app.species.geometry import Box, clip_to_box

SOURCE = "USFWS Critical Habitat map service"
LAYERS = {0: "Final", 2: "Proposed"}
FIELDS = "OBJECTID,comname,sciname,entity_id,status,listing_status,fedreg,pubdate"
# Roughly 50 m. Enough detail for a site-scale map without megabyte payloads.
MAX_ALLOWABLE_OFFSET = "0.0005"


class CritHabClient:
    def __init__(
        self,
        service_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = service_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def areas(self, window: Box) -> list[CriticalHabitatArea]:
        """Final and proposed critical habitat intersecting the window. Raises FeedError."""
        west, south, east, north = window
        params = {
            "geometry": f"{west},{south},{east},{north}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": FIELDS,
            "returnGeometry": "true",
            "outSR": "4326",
            "maxAllowableOffset": MAX_ALLOWABLE_OFFSET,
            "geometryPrecision": "5",
            "f": "geojson",
        }
        areas: list[CriticalHabitatArea] = []
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            for layer in LAYERS:
                url = f"{self._url}/{layer}/query"
                try:
                    response = client.get(url, params=params, headers=_HEADERS)
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPError as exc:
                    raise FeedError(
                        f"Critical habitat request failed: {type(exc).__name__}"
                    ) from exc
                except ValueError as exc:
                    raise FeedError("Critical habitat service returned invalid JSON") from exc
                areas.extend(parse_features(payload, layer, window, self._url))
        return areas


_HEADERS = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/geo+json"}


def parse_features(
    payload: Any, layer: int, window: Box, service_url: str
) -> list[CriticalHabitatArea]:
    # ArcGIS reports query errors as HTTP 200 with an "error" object.
    if not isinstance(payload, dict) or "error" in payload:
        raise FeedError("Critical habitat service returned an error")
    features = payload.get("features")
    if not isinstance(features, list):
        raise FeedError("Critical habitat response has no features list")
    areas = []
    for feature in features:
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue
        geometry = clip_to_box(feature.get("geometry"), window)
        object_id = props.get("OBJECTID")
        areas.append(
            CriticalHabitatArea(
                id=f"crithab:{LAYERS[layer].lower()}:{object_id}",
                common_name=_text(props.get("comname")),
                scientific_name=_text(props.get("sciname")),
                status=_text(props.get("status")) or LAYERS[layer],
                listing_status=_text(props.get("listing_status")),
                federal_register=_text(props.get("fedreg")),
                published=_date(props.get("pubdate")),
                source=SOURCE,
                source_url=f"{service_url}/{layer}",
                geometry=geometry,
                geometry_note=None
                if geometry
                else "Boundary not drawn: too small or irregular at this map scale.",
            )
        )
    return areas


def _date(value: Any) -> date | None:
    """`pubdate` is YYYYMMDD text. Anything else is unknown, not guessed."""
    text = _text(value)
    if not text or len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    # The service fills unmapped attributes with this placeholder.
    if not value or value.lower().startswith("please check"):
        return None
    return value
