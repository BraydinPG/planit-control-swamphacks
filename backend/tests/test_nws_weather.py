"""T043: NWS weather and forecast feed."""

from datetime import timedelta

from app.ingestion import nws_weather
from app.ingestion.nws_weather import (
    HEAT_INDEX,
    PRECIPITATION_PROBABILITY,
    RELATIVE_HUMIDITY,
    TEMPERATURE,
    NwsWeatherFeed,
)
from app.schemas import DataState, HazardType
from tests.nws_fakes import NOW, FakeNws, Site, cache, latest


def feed(fake: FakeNws, **kwargs) -> NwsWeatherFeed:
    return NwsWeatherFeed(fake.client(**kwargs), cache(HazardType.WEATHER), forecast_hours=3)


def by(observations, hazard_type, label):
    return [o for o in observations if o.hazard_type == hazard_type and o.label == label]


def test_one_site_receives_timestamped_observed_and_forecast_readings() -> None:
    observations = feed(FakeNws()).fetch([Site()], NOW)

    observed = [o for o in observations if o.hazard_type == HazardType.WEATHER]
    forecast = [o for o in observations if o.hazard_type == HazardType.FORECAST]
    assert {o.label for o in observed} == {TEMPERATURE, RELATIVE_HUMIDITY, HEAT_INDEX}
    assert {o.label for o in forecast} == {
        TEMPERATURE,
        RELATIVE_HUMIDITY,
        PRECIPITATION_PROBABILITY,
    }
    assert len(forecast) == 9
    for o in observations:
        assert o.site_id == "site-demo"
        assert o.source == "NWS"
        assert o.observed_at.tzinfo is not None
        assert o.fetched_at == NOW
    assert all(o.data_state is DataState.OBSERVED for o in observed)
    assert all(o.data_state is DataState.FORECAST and o.valid_at for o in forecast)


def test_converts_celsius_to_fahrenheit() -> None:
    observations = feed(FakeNws()).fetch([Site()], NOW)
    [temp] = by(observations, HazardType.WEATHER, TEMPERATURE)
    [heat] = by(observations, HazardType.WEATHER, HEAT_INDEX)
    assert (temp.value, temp.unit) == (93.9, "°F")
    assert heat.value == 107.1
    assert (temp.lon, temp.lat) == (-80.43, 25.65)


def test_missing_value_is_skipped_not_zero() -> None:
    fake = FakeNws({"/stations/KTMB/observations/latest": latest(heat_index=None)})
    observations = feed(fake).fetch([Site()], NOW)
    assert by(observations, HazardType.WEATHER, HEAT_INDEX) == []
    assert all(o.value is not None for o in observations)


EMPTY_READING = latest(heat_index=None, temperature=None, humidity=None)


def test_station_with_null_values_falls_back_to_next_station() -> None:
    fake = FakeNws(
        {
            "/stations/KTMB/observations/latest": EMPTY_READING,
            "/stations/KMIA/observations/latest": latest(),
        }
    )
    observed = [o for o in feed(fake).fetch([Site()], NOW) if o.hazard_type == HazardType.WEATHER]
    assert {o.source_ref for o in observed} == {"station:KMIA"}
    assert all(o.data_state is DataState.OBSERVED for o in observed)


def test_no_station_values_is_unavailable_while_forecast_stays_current() -> None:
    fake = FakeNws(
        {
            "/stations/KTMB/observations/latest": EMPTY_READING,
            "/stations/KMIA/observations/latest": EMPTY_READING,
        }
    )
    observations = feed(fake).fetch([Site()], NOW)
    [observed] = [o for o in observations if o.hazard_type == HazardType.WEATHER]
    assert observed.data_state is DataState.UNAVAILABLE and observed.value is None
    forecast = [o for o in observations if o.hazard_type == HazardType.FORECAST]
    assert forecast and all(o.data_state is DataState.FORECAST for o in forecast)


def test_old_station_reading_is_stale() -> None:
    old = latest(observed_at=NOW - timedelta(hours=3))
    observations = feed(FakeNws({"/stations/KTMB/observations/latest": old})).fetch([Site()], NOW)
    observed = [o for o in observations if o.hazard_type == HazardType.WEATHER]
    assert observed and all(o.data_state is DataState.STALE for o in observed)


def test_sends_user_agent_and_reuses_point_lookup() -> None:
    fake = FakeNws()
    weather = feed(fake)
    weather.fetch([Site()], NOW)
    weather.fetch([Site()], NOW + timedelta(minutes=5))
    assert all(r.headers["User-Agent"] == "PlanIT Control tests" for r in fake.requests)
    assert sum(r.url.path.startswith("/points/") for r in fake.requests) == 1


def test_missing_user_agent_is_unavailable_without_request() -> None:
    fake = FakeNws()
    [obs] = feed(fake, user_agent=None).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    assert obs.value is None
    assert fake.requests == []


def test_outage_is_unavailable_when_nothing_cached() -> None:
    fake = FakeNws()
    fake.fail = True
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    assert obs.hazard_type == HazardType.WEATHER


def test_module_fetch_uses_environment_settings(monkeypatch) -> None:
    monkeypatch.delenv("NWS_USER_AGENT", raising=False)
    monkeypatch.setattr(nws_weather, "_default_feed", None)
    nws_weather.get_ingestion_settings.cache_clear()
    monkeypatch.chdir("/")  # keep a developer's backend/.env out of the test
    [obs] = nws_weather.fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    nws_weather.get_ingestion_settings.cache_clear()
