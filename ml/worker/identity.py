"""Reconcile against a pinned export of the actual backend EIA selection, no DB writes."""

from datetime import datetime, timezone
import re

from ml.schemas import parse_utc
from ml.worker.schema import Point, SiteContext
from ml.worker.spatial import distance_km


def reconcile_site(candidate: dict, authoritative: dict[str, dict], as_of_utc: str) -> SiteContext:
    site = SiteContext.model_validate(candidate)
    if not re.fullmatch(r"eia860m-[A-Z]{2}-[1-9][0-9]*", site.id):
        raise ValueError("Expected the backend EIA identifier, not a research-ID string join")
    if site.id not in authoritative:
        raise ValueError("Site not in the pinned authoritative backend selection")
    record = authoritative[site.id]
    if site.id != f"eia860m-{record['state']}-{record['plant_id']}":
        raise ValueError("State/plant association mismatch")
    source_site = SiteContext.model_validate(record["site"])
    if site.source_version != source_site.source_version or site.name != source_site.name:
        raise ValueError("Site source revision or plant identity mismatch")
    if distance_km(site, Point(lat=source_site.lat, lon=source_site.lon)) > 0.1:
        raise ValueError("Site coordinates disagree with the source by over 100m")
    if site.is_fixture or site.site_type != "representative_monitored_site":
        raise ValueError("Authoritative EIA export must remain a real representative plant")
    now = parse_utc(as_of_utc, "as_of")
    source_time = parse_utc(record["source_available_at"], "source availability")
    period = datetime.fromisoformat(record["source_period_start"]).replace(tzinfo=timezone.utc)
    if source_time > now or period > now or (now - period).days > 366:
        raise ValueError("Site revision unavailable as-of or too old for this research export")
    return site
