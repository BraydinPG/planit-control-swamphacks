"""T043A: NWS flood-alert feed."""

from app.ingestion.nws_alerts import NO_ACTIVE_ALERTS, NwsFloodAlertFeed
from app.schemas import DataState, HazardType
from tests.nws_fakes import NOW, FakeNws, Site, alerts, cache


def feed(fake: FakeNws) -> NwsFloodAlertFeed:
    return NwsFloodAlertFeed(fake.client(), cache(HazardType.FLOOD_ALERT))


def test_fixture_alert_produces_an_observation() -> None:
    fake = FakeNws()
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.hazard_type == HazardType.FLOOD_ALERT
    assert obs.value == "Flood Watch"
    assert obs.label == "Flood Watch issued for Miami-Dade"
    assert obs.source_ref == "urn:oid:test.0"
    assert obs.data_state is DataState.OBSERVED
    assert obs.valid_at is not None and obs.observed_at < NOW
    assert fake.requests[0].url.params["point"] == "25.7600,-80.4900"


def test_keeps_only_flood_events() -> None:
    fake = FakeNws(
        {
            "/alerts/active": alerts(
                "Flood Warning", "Heat Advisory", "Flash Flood Warning", "Flood Watch"
            )
        }
    )
    values = {o.value for o in feed(fake).fetch([Site()], NOW)}
    assert values == {"Flood Warning", "Flash Flood Warning", "Flood Watch"}


def test_no_active_alerts_is_an_explicit_observation() -> None:
    fake = FakeNws({"/alerts/active": alerts("Heat Advisory")})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.label == NO_ACTIVE_ALERTS
    assert obs.value is None
    assert obs.data_state is DataState.OBSERVED


def test_failed_fetch_is_unavailable_not_no_flood() -> None:
    fake = FakeNws()
    fake.fail = True
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
    assert obs.label != NO_ACTIVE_ALERTS


def test_malformed_payload_is_unavailable() -> None:
    fake = FakeNws({"/alerts/active": {"type": "FeatureCollection"}})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.UNAVAILABLE
