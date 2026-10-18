"""T049C: NWS tornado and severe thunderstorm feed."""

from app.ingestion.severe_storms import NO_ACTIVE_ALERTS, NwsSevereStormFeed
from app.schemas import DataState, HazardType
from tests.nws_fakes import NOW, FakeNws, Site, alerts, cache


def feed(fake: FakeNws) -> NwsSevereStormFeed:
    return NwsSevereStormFeed(fake.client(), cache(HazardType.SEVERE_STORM))


def test_storm_warnings_and_watches_become_observations() -> None:
    fake = FakeNws(
        {
            "/alerts/active": alerts(
                "Tornado Warning",
                "Flood Warning",
                "Severe Thunderstorm Warning",
                "Severe Thunderstorm Watch",
            )
        }
    )
    rows = feed(fake).fetch([Site()], NOW)
    assert {o.value for o in rows} == {
        "Tornado Warning",
        "Severe Thunderstorm Warning",
        "Severe Thunderstorm Watch",
    }
    tornado = next(o for o in rows if o.value == "Tornado Warning")
    assert tornado.hazard_type == HazardType.SEVERE_STORM
    assert tornado.source == "NWS"
    assert tornado.label == "Tornado Warning issued for Miami-Dade"
    assert tornado.data_state is DataState.OBSERVED
    assert tornado.valid_at is not None and tornado.observed_at < NOW


def test_no_storm_alerts_is_an_explicit_observation() -> None:
    fake = FakeNws({"/alerts/active": alerts("Flood Watch")})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.value is None
    assert obs.label == NO_ACTIVE_ALERTS
    assert obs.data_state is DataState.OBSERVED


def test_failed_fetch_is_unavailable_not_no_storm() -> None:
    fake = FakeNws()
    fake.fail = True
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    assert obs.label != NO_ACTIVE_ALERTS
