"""T044: per-feed caching with stale and unavailable states."""

from datetime import timedelta

import pytest

from app.ingestion.cache import FeedCache
from app.ingestion.nws_alerts import NwsFloodAlertFeed
from app.ingestion.nws_weather import NwsWeatherFeed
from app.schemas import DataState, HazardType
from tests.nws_fakes import NOW, STALE_AFTER, UNAVAILABLE_AFTER, FakeNws, Site, cache


def weather_feed(fake: FakeNws) -> NwsWeatherFeed:
    return NwsWeatherFeed(fake.client(), cache(HazardType.WEATHER), forecast_hours=1)


def states(observations) -> set[DataState]:
    return {o.data_state for o in observations}


def test_failed_refresh_returns_last_readings_marked_stale() -> None:
    fake = FakeNws()
    weather = weather_feed(fake)
    first = weather.fetch([Site()], NOW)
    assert DataState.STALE not in states(first)

    fake.fail = True
    later = weather.fetch([Site()], NOW + timedelta(minutes=5))
    assert states(later) == {DataState.STALE}
    assert [o.id for o in later] == [o.id for o in first]
    assert all(o.fetched_at == NOW for o in later)


def test_failed_refresh_after_unavailable_window_is_unavailable() -> None:
    fake = FakeNws()
    weather = weather_feed(fake)
    weather.fetch([Site()], NOW)
    fake.fail = True
    [obs] = weather.fetch([Site()], NOW + UNAVAILABLE_AFTER + timedelta(minutes=1))
    assert obs.data_state is DataState.UNAVAILABLE


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(minutes=10), {DataState.OBSERVED, DataState.FORECAST}),
        (STALE_AFTER + timedelta(minutes=1), {DataState.STALE}),
        (UNAVAILABLE_AFTER + timedelta(minutes=1), {DataState.UNAVAILABLE}),
    ],
)
def test_snapshot_ages_cached_readings(age, expected) -> None:
    weather = weather_feed(FakeNws())
    weather.fetch([Site()], NOW)
    assert states(weather.cache.snapshot(Site(), NOW + age)) == expected


def test_snapshot_without_any_fetch_is_unavailable() -> None:
    [obs] = cache(HazardType.WEATHER).snapshot(Site(), NOW)
    assert obs.data_state is DataState.UNAVAILABLE


def test_one_failed_feed_does_not_mark_others_stale() -> None:
    weather_nws, alerts_nws = FakeNws(), FakeNws()
    weather = weather_feed(weather_nws)
    floods = NwsFloodAlertFeed(alerts_nws.client(), cache(HazardType.FLOOD_ALERT))
    weather.fetch([Site()], NOW)
    floods.fetch([Site()], NOW)

    alerts_nws.fail = True
    later = NOW + timedelta(minutes=5)
    assert states(floods.fetch([Site()], later)) == {DataState.STALE}
    assert states(weather.fetch([Site()], later)) == {DataState.OBSERVED, DataState.FORECAST}


def test_sites_are_cached_independently() -> None:
    fake = FakeNws()
    weather = weather_feed(fake)
    weather.fetch([Site()], NOW)
    other = Site(id="site-other", lat=26.1, lon=-81.2)  # no route: its fetch fails
    observations = weather.fetch([Site(), other], NOW + timedelta(minutes=5))
    assert states([o for o in observations if o.site_id == "site-demo"]) != {DataState.STALE}
    assert states([o for o in observations if o.site_id == "site-other"]) == {DataState.UNAVAILABLE}


def test_unavailable_window_must_cover_stale_window() -> None:
    with pytest.raises(ValueError):
        FeedCache("NWS", HazardType.WEATHER, timedelta(hours=2), timedelta(hours=1))
