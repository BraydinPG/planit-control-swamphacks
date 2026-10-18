"""Offline transport regressions: no sockets or application database configuration."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Event, Lock

import httpx
import pytest

from app.ingestion import runtime
from app.ingestion.base import FeedError
from app.ingestion.http import HttpPolicy, PooledHttp, RequestFailure, retry_after, safe_url
from app.ingestion.json_client import JsonClient


def policy(**overrides):
    return HttpPolicy(min_interval_seconds=0, backoff_seconds=0, **overrides)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503, 504])
def test_only_transient_statuses_retry_with_searchable_redacted_diagnostics(status, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Retry-After": "0"})

    with _http(policy(), handler) as client:
        with runtime.round_scope() as run, runtime.labels(feed="NWS/weather", region="MA"):
            with caplog.at_level(logging.INFO), pytest.raises(RequestFailure) as caught:
                client.get(
                    "https://status.test/points/a?point=42,-71&api_key=PRIVATE",
                    None,
                    {"Authorization": "Bearer PRIVATE-TOKEN"},
                    provider="NWS",
                )
        expected = 2 if status in {429, 500, 502, 503, 504} else 1
        assert len(calls) == expected
        assert caught.value.fields["http_status"] == status
        assert not caught.value.not_covered
        report = run.report()["requests"]["NWS/weather"]
        assert report["attempts"] == expected
        assert report["failures_by_region"] == {"MA": expected}
        entries = [json.loads(r.message) for r in caplog.records if r.name.endswith("runtime")]
        assert all(e["method"] == "GET" and e["duration_seconds"] >= 0 for e in entries)
        assert entries[-1]["will_retry"] is False
        assert entries[-1]["attempt"] == expected
        assert "PRIVATE" not in caplog.text and "Bearer" not in caplog.text


@contextmanager
def _http(options, handler):
    client = PooledHttp(options, httpx.MockTransport(handler))
    try:
        yield client
    finally:
        client.close()


@pytest.mark.parametrize("error", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError])
def test_transient_network_failures_retry_and_preserve_original_type(error):
    calls = []

    def handler(request):
        calls.append(request)
        raise error("private raw provider message", request=request)

    with _http(policy(retries=1), handler) as client:
        with pytest.raises(RequestFailure) as caught:
            client.get("https://timeouts.test/data", None, {}, provider="USGS")
    assert len(calls) == 2
    assert caught.value.fields["exception_type"] == error.__name__
    assert "private" not in str(caught.value)


def test_retry_after_budget_never_sleeps_past_request_budget():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "3600"})

    started = time.monotonic()
    with _http(policy(budget_seconds=0.1), handler) as client:
        with pytest.raises(RequestFailure) as caught:
            client.get("https://budget.test/data", None, {}, provider="NWS")
    assert time.monotonic() - started < 0.5
    assert len(calls) == 1 and caught.value.fields["will_retry"] is False


def test_retry_after_date_numeric_and_malformed():
    now = datetime(2026, 10, 17, tzinfo=UTC)
    assert retry_after("Sat, 17 Oct 2026 00:00:04 GMT", now) == 4
    assert retry_after("2.5") == 2.5
    assert retry_after("-1") == 0
    for value in (None, "garbage", "nan", "inf"):
        assert retry_after(value) is None


def test_retry_after_waits_before_second_attempt():
    stamps = []

    def handler(request):
        stamps.append(time.monotonic())
        return httpx.Response(503 if len(stamps) == 1 else 200, headers={"Retry-After": ".03"})

    with _http(policy(), handler) as client:
        assert client.get("https://delay.test/data", None, {}, provider="NWS").status_code == 200
    assert len(stamps) == 2 and stamps[1] - stamps[0] >= 0.025


def test_shared_pool_connection_cap_and_pacing_between_distinct_requests():
    lock = Lock()
    active = peak = 0
    starts = []

    def handler(request):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            starts.append(time.monotonic())
        time.sleep(0.035)
        with lock:
            active -= 1
        return httpx.Response(200, json={})

    with _http(HttpPolicy(max_connections=2, min_interval_seconds=0.01), handler) as client:
        underlying = client.client
        with ThreadPoolExecutor(max_workers=6) as workers:
            rows = list(
                workers.map(
                    lambda i: client.get(f"https://pooled.test/{i}", None, {}, provider="test"),
                    range(8),
                )
            )
        assert all(r.status_code == 200 for r in rows)
        assert client.client is underlying
        assert 1 < peak <= 2
        assert all(b - a >= 0.008 for a, b in zip(starts, starts[1:], strict=False))
    assert underlying.is_closed


def test_cancellation_before_submission_and_body_limit():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=b"too much content")

    with _http(policy(max_response_bytes=4), handler) as client:
        stop = Event()
        stop.set()
        with runtime.round_scope(cancel=stop), pytest.raises(FeedError):
            client.get("https://cancel.test/data", None, {}, provider="NWS")
        assert calls == []
        with pytest.raises(RequestFailure):
            client.get("https://size.test/data", None, {}, provider="NWS")
        assert len(calls) == 1


@pytest.mark.parametrize("body,kind", [(b"broken", "InvalidJSON"), (b"[]", "InvalidPayload")])
def test_invalid_json_is_not_retried_and_carries_endpoint_status(body, kind):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=body)

    with JsonClient(transport=httpx.MockTransport(handler), policy=policy()) as client:
        with runtime.round_scope() as run, pytest.raises(RequestFailure) as caught:
            client.get_json("https://json.test/data?secret=PRIVATE")
        assert len(calls) == 1
        assert caught.value.fields["exception_type"] == kind
        assert caught.value.fields["http_status"] == 200
        assert len(run.report()["invalid_responses"]) == 1
        assert "PRIVATE" not in str(run.report())


def test_endpoint_redacts_userinfo_secret_query_fragment_and_path():
    url = safe_url("https://user:PRIVATE@redact.test/token/PRIVATE/a?point=1,2&key=PRIVATE#PRIVATE")
    assert "PRIVATE" not in url and "user" not in url and "point=1%2C2" in url


def test_single_flight_shared_request_only_within_round():
    calls = []

    def handler(request):
        calls.append(request)
        time.sleep(0.01)
        return httpx.Response(200, json={"value": 3})

    with JsonClient(transport=httpx.MockTransport(handler), policy=policy()) as client:
        with runtime.round_scope():
            rows = list(
                runtime.ordered_map(
                    lambda _: client.get_json("https://dedup.test/data"), list(range(10)), 4
                )
            )
        assert len(calls) == 1 and all(r == {"value": 3} for r in rows)
        rows[0]["value"] = 99
        assert rows[1]["value"] == 3
        with runtime.round_scope():
            client.get_json("https://dedup.test/data")
        assert len(calls) == 2


def test_failed_shared_provider_request_without_site_region_has_valid_summary():
    with _http(policy(retries=0), lambda request: httpx.Response(503)) as client:
        with runtime.round_scope() as run, pytest.raises(RequestFailure):
            client.get("https://shared-failure.test/summary", None, {}, provider="USGS")
        assert run.report()["requests"]["USGS"]["failures_by_region"] == {"shared": 1}
