"""T045C: USGS earthquake summary feed."""

from datetime import timedelta

from app.ingestion.earthquakes import SOURCE, EarthquakeFeed
from app.schemas import DataState, HazardType
from tests.feed_fakes import QUAKE_URL, FakeFeeds, cache, quake, quakes
from tests.nws_fakes import NOW, Site


def feed(fake: FakeFeeds) -> EarthquakeFeed:
    return EarthquakeFeed(fake.client(), cache(SOURCE, HazardType.EARTHQUAKE), QUAKE_URL, 100)


def test_fixture_event_produces_an_observation() -> None:
    fake = FakeFeeds({QUAKE_URL: quakes(quake("us7000demo", 18))})
    [obs] = feed(fake).fetch([Site()], NOW)

    assert obs.hazard_type == HazardType.EARTHQUAKE
    assert obs.source == "USGS"
    assert obs.value == 4.6 and obs.unit == "mww"
    assert obs.observed_at == NOW - timedelta(minutes=30)
    assert obs.label == "M4.6 - 12 km SW of Example, FL, 18 mi S of site"
    assert obs.source_ref.endswith("us7000demo")
    assert obs.data_state is DataState.OBSERVED
    assert (obs.lat, obs.lon) != (Site().lat, Site().lon)


def test_far_events_and_non_earthquakes_are_skipped() -> None:
    fake = FakeFeeds({QUAKE_URL: quakes(quake("far", 400), quake("blast", 5, kind="quarry blast"))})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.value is None
    assert obs.label == "No earthquakes within 100 mi (USGS All Earthquakes, Past Day)"
    assert obs.data_state is DataState.OBSERVED


def test_failed_fetch_is_unavailable_not_no_earthquake() -> None:
    fake = FakeFeeds({QUAKE_URL: quakes(quake("us7000demo", 18))})
    fake.fail = True
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    assert not obs.label.startswith("No earthquakes")


def test_malformed_payload_is_unavailable() -> None:
    [obs] = feed(FakeFeeds({QUAKE_URL: {"type": "FeatureCollection"}})).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE


def test_missing_magnitude_is_not_reported_as_zero() -> None:
    fake = FakeFeeds({QUAKE_URL: quakes(quake("nomag", 10, mag=None))})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.value is None and obs.unit is None
    assert obs.label.startswith("Earthquake - ")


def test_feed_is_fetched_once_for_all_sites() -> None:
    fake = FakeFeeds({QUAKE_URL: quakes(quake("us7000demo", 18))})
    sites = [Site(), Site(id="site-two", lat=25.80, lon=-80.40)]
    observations = feed(fake).fetch(sites, NOW)
    assert len(fake.requests) == 1
    assert {o.site_id for o in observations} == {"site-demo", "site-two"}
