"""USFWS IPaC Location API adapter (https://ipac.ecosphere.fws.gov/location/api).

`POST /resources` takes a polygon footprint and returns the federally listed (ESA)
populations whose *range* intersects it, critical habitat flags, and the responsible
FWS field office. Reviewed 2026-10-17 against API version 1.2.0:

- No API key yet (IPaC says one will eventually be required). No documented rate limit.
- Coverage: ESA-listed, proposed, candidate, and similarity-of-appearance populations
  only. A species that is not federally listed (e.g. the water moccasin) never appears,
  so absence here says nothing about whether an animal lives near the site.
- No per-record vintage. The only "as of" is when we retrieved it.
- Range means "should be considered for this location", not an observation.

Every failure raises `FeedError` so the caller shows unavailable, never "no species".
"""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.ingestion.base import FeedError
from app.ingestion.json_client import DEFAULT_USER_AGENT
from app.species.geometry import Box, box_polygon

SOURCE = "USFWS IPaC Location API"
DOCS_URL = "https://ipac.ecosphere.fws.gov/location/api"


@dataclass(frozen=True)
class IpacPopulation:
    sid: str
    common_name: str | None
    scientific_name: str | None
    group: str | None
    status: str | None
    status_code: str | None
    status_description: str | None
    profile_url: str | None
    critical_habitat_here: bool | None
    conditional: bool


@dataclass(frozen=True)
class IpacOffice:
    name: str
    phone: str | None
    email: str | None


@dataclass(frozen=True)
class IpacResult:
    api_version: str | None
    location_description: str | None
    populations: list[IpacPopulation]
    offices: list[IpacOffice]
    notification: str | None = None
    unknowns: list[str] = field(default_factory=list)


class IpacClient:
    def __init__(
        self,
        url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._transport = transport

    def resources(self, footprint: Box) -> IpacResult:
        body = {
            "location.footprint": json.dumps(box_polygon(footprint)),
            "locationFormat": "GeoJSON",
            # Migratory birds, wetlands, refuges etc. are out of scope and slow the call.
            "includeOtherFwsResources": False,
            "includeCrithabGeometry": False,
            "timeout": 5,
        }
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.post(self._url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise FeedError("IPaC request timed out") from exc
        except httpx.HTTPError as exc:
            raise FeedError(f"IPaC request failed: {type(exc).__name__}") from exc
        if response.status_code == 429:
            raise FeedError("IPaC rate limit reached (HTTP 429)")
        if response.status_code != 200:
            raise FeedError(f"IPaC returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise FeedError("IPaC returned invalid JSON") from exc
        return parse_resources(payload)


def parse_resources(payload: Any) -> IpacResult:
    """Parse a `/resources` response. Missing fields stay None; a bad shape raises."""
    resources = payload.get("resources") if isinstance(payload, dict) else None
    if not isinstance(resources, dict):
        raise FeedError("IPaC response has no resources object")
    by_sid = resources.get("populationsBySid")
    if not isinstance(by_sid, dict):
        raise FeedError("IPaC response has no populationsBySid map")
    unknowns: list[str] = []
    populations = []
    for sid, item in by_sid.items():
        population = item.get("population") if isinstance(item, dict) else None
        if not isinstance(population, dict):
            unknowns.append(f"IPaC record {sid} had no population details and was skipped.")
            continue
        crithab = item.get("crithabInFootprint")
        populations.append(
            IpacPopulation(
                sid=str(sid),
                common_name=_text(population.get("optionalCommonName")),
                scientific_name=_text(population.get("optionalScientificName")),
                group=_text(population.get("groupName")),
                status=_text(population.get("listingStatusName")),
                status_code=_text(population.get("listingStatusCode")),
                status_description=_text(population.get("optionalListingStatusDescription")),
                profile_url=_text(population.get("speciesProfileUrl")),
                critical_habitat_here=crithab if isinstance(crithab, bool) else None,
                conditional=item.get("conditional") is True,
            )
        )
    offices = [
        IpacOffice(
            name=name,
            phone=_text(office.get("formattedPhone")),
            email=_text(office.get("officeEmailAddress")),
        )
        for office in resources.get("fieldOffices") or []
        if isinstance(office, dict) and (name := _text(office.get("officeName")))
    ]
    location = resources.get("location")
    description = _text(location.get("description")) if isinstance(location, dict) else None
    return IpacResult(
        api_version=_text(resources.get("apiVersion")),
        location_description=" ".join(description.split()) if description else None,
        populations=sorted(populations, key=lambda p: p.common_name or p.scientific_name or ""),
        offices=offices,
        notification=_text(resources.get("notification")),
        unknowns=unknowns,
    )


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
