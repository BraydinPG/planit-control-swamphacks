"""Builds a site's species context from IPaC, the critical habitat service, and crew reports.

Read-only and advisory. Nothing here writes to the database or feeds the score, alerts,
report confirmation, or work clearance.

Freshness, per source (IPaC and critical habitat are cached and labeled separately):

- `observed`: retrieved within `SPECIES_CACHE_HOURS`.
- `stale`: the last refresh failed; the previous result is shown with its retrieval time.
- `unavailable`: nothing usable. Species list is empty and an unknown says why. An empty
  list is never presented as "no species".
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

from app.gemini.species import SpeciesFacts, word_species
from app.ingestion import SiteLike
from app.ingestion.base import FeedError
from app.schemas import (
    CrewReport,
    CriticalHabitatArea,
    DataState,
    EncounterGuidance,
    FieldOfficeContact,
    GeneratedBy,
    HazardNotice,
    MatchBasis,
    NoticeStatus,
    ProtectionStatus,
    ReportCategory,
    ReviewStatus,
    SiteSpeciesContext,
    SpeciesEntry,
    WildlifeReportRef,
)
from app.species import crithab, ipac
from app.species.geometry import square
from app.species.guidance import guidance_for
from app.species.settings import SpeciesSettings, get_species_settings

logger = logging.getLogger(__name__)

JURISDICTION = "U.S. federal (Endangered Species Act)"
RANGE_NOTE = (
    "Listed by IPaC because its known range overlaps the area around this site. Not a sighting."
)
CONDITIONAL_NOTE = (
    "IPaC lists this species for the area with field-office conditions (for example "
    "habitat or season). Possible regional context, not a sighting."
)
COVERAGE_UNKNOWN = (
    "IPaC covers only federally listed species. Species that are not federally listed, "
    "such as the water moccasin, never appear here, so their absence says nothing about "
    "local wildlife."
)
STATE_UNKNOWN = (
    "State protection status (for example Florida FWC listings) is not supplied by IPaC."
)
VINTAGE_UNKNOWN = (
    "IPaC gives no date for its range data. The date shown is when PlanIT Control retrieved it."
)
RETRY_AFTER = timedelta(minutes=5)

Wording = Callable[[list[SpeciesFacts]], dict[str, str] | None]


@dataclass
class _Lookup:
    """One source's cached result for one site."""

    value: object | None = None
    fetched_at: datetime | None = None
    failed_at: datetime | None = None
    error: str | None = None


@dataclass
class _SiteCache:
    ipac: _Lookup = field(default_factory=_Lookup)
    crithab: _Lookup = field(default_factory=_Lookup)


class SpeciesContextService:
    def __init__(
        self,
        settings: SpeciesSettings,
        ipac_client: ipac.IpacClient,
        crithab_client: crithab.CritHabClient,
        wording: Wording = word_species,
    ) -> None:
        self._settings = settings
        self._ipac = ipac_client
        self._crithab = crithab_client
        self._wording = wording
        self._cache: dict[str, _SiteCache] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: SpeciesSettings) -> "SpeciesContextService":
        timeout = settings.species_timeout_seconds
        return cls(
            settings,
            ipac.IpacClient(settings.ipac_resources_url, timeout),
            crithab.CritHabClient(settings.crithab_service_url, timeout),
        )

    def context(
        self,
        site: SiteLike,
        now: datetime,
        reports: list[CrewReport] = (),
        notices: list[HazardNotice] = (),
    ) -> SiteSpeciesContext:
        with self._lock:
            cache = self._cache.setdefault(site.id, _SiteCache())
        half = self._settings.species_footprint_half_km
        footprint = square(site.lat, site.lon, half)
        window = square(site.lat, site.lon, self._settings.crithab_window_half_km)

        species_state = self._refresh(
            cache.ipac, now, lambda: self._build_species(self._ipac.resources(footprint), now)
        )
        habitat_state = self._refresh(cache.crithab, now, lambda: self._crithab.areas(window))

        built: _Species | None = (
            cache.ipac.value if species_state != DataState.UNAVAILABLE else None
        )
        areas: list[CriticalHabitatArea] = (
            cache.crithab.value if habitat_state != DataState.UNAVAILABLE else []
        )
        unknowns = [COVERAGE_UNKNOWN, STATE_UNKNOWN, VINTAGE_UNKNOWN]
        unknowns += _state_unknowns("IPaC species lookup", species_state, cache.ipac)
        unknowns += _state_unknowns("Critical habitat map", habitat_state, cache.crithab)
        if built:
            unknowns += built.unknowns
        return SiteSpeciesContext(
            site_id=site.id,
            source=ipac.SOURCE,
            source_url=ipac.DOCS_URL,
            api_version=built.api_version if built else None,
            data_state=species_state,
            simulated=False,
            fetched_at=cache.ipac.fetched_at if built else None,
            footprint_description=(
                f"About {2 * half:g} km square centered on the site"
                + (f" ({built.location})" if built and built.location else "")
            ),
            location_description=built.location if built else None,
            field_office=built.office if built else None,
            species=built.entries if built else [],
            critical_habitat=areas,
            critical_habitat_state=habitat_state,
            critical_habitat_source=crithab.SOURCE,
            wildlife_reports=wildlife_reports(reports, notices),
            generated_by=built.generated_by if built else GeneratedBy.FALLBACK,
            unknowns=unknowns,
        )

    def _refresh(self, lookup: _Lookup, now: datetime, fetch: Callable[[], object]) -> DataState:
        """Refresh one source when due. Returns its data state for this response."""
        fresh = lookup.fetched_at is not None and now - lookup.fetched_at < self._settings.cache_for
        backing_off = lookup.failed_at is not None and now - lookup.failed_at < RETRY_AFTER
        if not fresh and not backing_off:
            try:
                lookup.value = fetch()
                lookup.fetched_at, lookup.failed_at, lookup.error = now, None, None
                return DataState.OBSERVED
            except FeedError as exc:
                lookup.failed_at, lookup.error = now, str(exc)
                logger.warning("Species source refresh failed: %s", exc)
            except Exception as exc:  # malformed data must not break the site view
                lookup.failed_at, lookup.error = now, "unexpected response"
                logger.exception("Species source refresh failed: %s", type(exc).__name__)
        if lookup.fetched_at is None or now - lookup.fetched_at >= self._settings.unavailable_after:
            return DataState.UNAVAILABLE
        if fresh:
            return DataState.OBSERVED
        return DataState.STALE

    def _build_species(self, result: ipac.IpacResult, now: datetime) -> "_Species":
        source = f"{ipac.SOURCE} {result.api_version}" if result.api_version else ipac.SOURCE
        entries = [_entry(p, source, now) for p in result.populations]
        wording = self._wording([_facts(e) for e in entries]) or {}
        for i, entry in enumerate(entries):
            if entry.id in wording:
                entries[i] = entry.model_copy(
                    update={"summary": wording[entry.id], "summary_by": GeneratedBy.GEMINI}
                )
        office = result.offices[0] if result.offices else None
        unknowns = list(result.unknowns)
        if result.notification:
            unknowns.append(f"IPaC notice: {result.notification}")
        return _Species(
            api_version=result.api_version,
            location=result.location_description,
            office=FieldOfficeContact(name=office.name, phone=office.phone, email=office.email)
            if office
            else None,
            entries=sorted(entries, key=_order),
            generated_by=GeneratedBy.GEMINI if wording else GeneratedBy.FALLBACK,
            unknowns=unknowns,
        )


@dataclass(frozen=True)
class _Species:
    api_version: str | None
    location: str | None
    office: FieldOfficeContact | None
    entries: list[SpeciesEntry]
    generated_by: GeneratedBy
    unknowns: list[str]


def _entry(p: ipac.IpacPopulation, source: str, now: datetime) -> SpeciesEntry:
    protection_id = f"ipac:{p.sid}"
    protection = ProtectionStatus(
        jurisdiction=JURISDICTION,
        status=p.status,
        status_code=p.status_code,
        description=p.status_description,
        critical_habitat_here=p.critical_habitat_here,
        source=source,
        source_url=p.profile_url,
        as_of=now,
        evidence_id=protection_id,
    )
    guide = guidance_for(p.scientific_name)
    encounter = (
        EncounterGuidance(
            hazard=guide.hazard,
            actions=list(guide.actions),
            contact=guide.contact,
            source=guide.source,
            source_url=guide.source_url,
            review_status=guide.review_status,
            reviewed_by=guide.reviewed_by,
            evidence_id=guide.evidence_id,
        )
        if guide
        else None
    )
    evidence = [protection_id] + ([encounter.evidence_id] if encounter else [])
    entry = SpeciesEntry(
        id=protection_id,
        common_name=p.common_name,
        scientific_name=p.scientific_name,
        group=p.group,
        match_basis=MatchBasis.POSSIBLE_REGIONAL_CONTEXT
        if p.conditional
        else MatchBasis.REGIONAL_RANGE,
        match_note=CONDITIONAL_NOTE if p.conditional else RANGE_NOTE,
        protection=protection,
        encounter=encounter,
        summary="",
        summary_by=GeneratedBy.FALLBACK,
        evidence_ids=evidence,
    )
    return entry.model_copy(update={"summary": template_summary(entry)})


def template_summary(entry: SpeciesEntry) -> str:
    """Deterministic wording used whenever Gemini is unavailable or ungrounded."""
    name = entry.common_name or entry.scientific_name or "Unnamed species"
    status = entry.protection.status if entry.protection and entry.protection.status else None
    text = (
        f"{name}: federal status {status}." if status else f"{name}: federal status not supplied."
    )
    text += " Known range, not a sighting."
    if entry.encounter:
        text += " See encounter guidance."
    return text


def _facts(entry: SpeciesEntry) -> SpeciesFacts:
    enc = entry.encounter
    return SpeciesFacts(
        species_id=entry.id,
        common_name=entry.common_name,
        scientific_name=entry.scientific_name,
        group=entry.group,
        listing_status=entry.protection.status if entry.protection else None,
        match_note=entry.match_note,
        hazard=enc.hazard if enc else None,
        actions=tuple(enc.actions) if enc else (),
        contact=enc.contact if enc else None,
        evidence_ids=tuple(entry.evidence_ids),
    )


def _order(entry: SpeciesEntry) -> tuple:
    """Species with encounter guidance first, then other animals, then plants."""
    plant = "plant" in (entry.group or "").lower() or "fern" in (entry.group or "").lower()
    return (entry.encounter is None, plant, entry.common_name or entry.scientific_name or "")


def _state_unknowns(label: str, state: DataState, lookup: _Lookup) -> list[str]:
    if state == DataState.UNAVAILABLE:
        reason = f" ({lookup.error})" if lookup.error else ""
        return [f"{label} is unavailable{reason}. This does not mean nothing is there."]
    if state == DataState.STALE:
        return [
            f"{label} could not be refreshed ({lookup.error}); showing data retrieved "
            f"{lookup.fetched_at:%Y-%m-%d %H:%M} UTC."
        ]
    return []


def wildlife_reports(
    reports: list[CrewReport], notices: list[HazardNotice]
) -> list[WildlifeReportRef]:
    """Crew wildlife reports at the site, with their human review state.

    A report counts as confirmed only through review or a supervisor-confirmed notice.
    """
    confirmed_notices = {n.id for n in notices if n.status == NoticeStatus.CONFIRMED}
    refs = []
    for r in reports:
        if r.category != ReportCategory.WILDLIFE:
            continue
        if r.review_status == ReviewStatus.REJECTED:
            confirmation = "rejected"
        elif r.review_status == ReviewStatus.CONFIRMED or (r.notice_id in confirmed_notices):
            confirmation = "confirmed"
        else:
            confirmation = "pending"
        refs.append(
            WildlifeReportRef(
                report_id=r.id,
                reported_at=r.created_at,
                hazard_present=r.hazard_present,
                confirmation=confirmation,
                match_basis=MatchBasis.CONFIRMED_REPORT
                if confirmation == "confirmed" and r.hazard_present
                else MatchBasis.UNKNOWN,
                note=r.note,
            )
        )
    return refs


@lru_cache
def get_species_service() -> SpeciesContextService:
    """FastAPI dependency. One service per process so its cache is shared."""
    return SpeciesContextService.from_settings(get_species_settings())
