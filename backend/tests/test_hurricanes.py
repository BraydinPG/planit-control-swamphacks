"""T045B: NHC active storms and NWS tropical alerts."""

from datetime import UTC, datetime

from app.ingestion.hurricanes import NHC_SOURCE, NO_NWS_ALERTS, NWS_SOURCE, HurricaneFeed
from app.schemas import DataState, HazardType
from tests.feed_fakes import NHC_URL, FakeFeeds, cache, storm, storms
from tests.nws_fakes import NOW, FakeNws, Site, alerts


def feed(nhc: FakeFeeds, nws: FakeNws, radius: float = 300) -> HurricaneFeed:
    return HurricaneFeed(
        nhc.client(),
        nws.client(),
        cache(NHC_SOURCE, HazardType.HURRICANE),
        cache(NWS_SOURCE, HazardType.HURRICANE),
        NHC_URL,
        radius,
    )


def by_source(observations, source):
    return [o for o in observations if o.source == source]


def test_fixture_storm_produces_an_observation_with_source_and_time() -> None:
    nhc = FakeFeeds({NHC_URL: storms(storm("Example", 120), storm("Faraway", 1500))})
    nws = FakeNws({"/alerts/active": alerts()})
    observations = feed(nhc, nws).fetch([Site()], NOW)

    [obs] = by_source(observations, "NHC")
    assert obs.hazard_type == HazardType.HURRICANE
    assert obs.observed_at == datetime(2026, 10, 17, 15, 0, tzinfo=UTC)
    assert obs.value == 80.0 and obs.unit == "kt"
    assert obs.label == "Hurricane Example, 80 kt, 120 mi SE of site"
    assert obs.data_state is DataState.OBSERVED
    assert obs.fetched_at == NOW

    [none] = by_source(observations, "NWS")
    assert none.label == NO_NWS_ALERTS and none.value is None


def test_nws_tropical_warnings_become_observations() -> None:
    nhc = FakeFeeds({NHC_URL: storms()})
    nws = FakeNws({"/alerts/active": alerts("Hurricane Warning", "Flood Watch")})
    observations = feed(nhc, nws).fetch([Site()], NOW)

    [warning] = by_source(observations, "NWS")
    assert warning.value == "Hurricane Warning"
    assert warning.valid_at is not None
    requests = [r for r in nws.requests if r.url.path == "/alerts/active"]
    assert len(requests) == 1 and requests[0].url.params["point"] == "25.7600,-80.4900"
    assert "event" not in requests[0].url.params  # Shared payload, filtered locally.
    [none] = by_source(observations, "NHC")
    assert none.value is None and none.label == "No active NHC storms within 300 mi"


def test_failed_nhc_fetch_is_unavailable_and_keeps_nws_current() -> None:
    nhc = FakeFeeds({NHC_URL: storms(storm("Example", 120))})
    nhc.fail = True
    nws = FakeNws({"/alerts/active": alerts("Tropical Storm Watch")})
    observations = feed(nhc, nws).fetch([Site()], NOW)

    [unavailable] = by_source(observations, "NHC")
    assert unavailable.data_state is DataState.UNAVAILABLE
    assert unavailable.value is None
    [watch] = by_source(observations, "NWS")
    assert watch.data_state is DataState.OBSERVED


def test_malformed_nhc_payload_is_unavailable() -> None:
    nhc = FakeFeeds({NHC_URL: {"storms": []}})
    observations = feed(nhc, FakeNws({"/alerts/active": alerts()})).fetch([Site()], NOW)
    [obs] = by_source(observations, "NHC")
    assert obs.data_state is DataState.UNAVAILABLE


def test_nhc_is_fetched_once_for_all_sites() -> None:
    nhc = FakeFeeds({NHC_URL: storms(storm("Example", 120))})
    sites = [Site(), Site(id="site-two", lat=25.80, lon=-80.40)]
    nws = FakeNws(
        {
            "/alerts/active": alerts(),
        }
    )
    observations = feed(nhc, nws).fetch(sites, NOW)
    assert len(nhc.requests) == 1
    assert {o.site_id for o in by_source(observations, "NHC")} == {"site-demo", "site-two"}


def test_storm_with_missing_intensity_is_not_reported_as_zero() -> None:
    nhc = FakeFeeds({NHC_URL: storms(storm("Example", 50, knots=None))})
    observations = feed(nhc, FakeNws({"/alerts/active": alerts()})).fetch([Site()], NOW)
    [obs] = by_source(observations, "NHC")
    assert obs.value is None and obs.unit is None
    assert obs.label == "Hurricane Example, 50 mi SE of site"
