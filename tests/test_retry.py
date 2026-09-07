"""Tests for transient-failure retry at the HTTP transport boundary.

Regression cover for unattended sync aborting on a single blip: a read
timeout, DNS failure or 5xx used to propagate straight out of the first
request and exit the whole run non-zero, even though the next run minutes
later succeeded.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from plaud_cli import api as plaud_api


def _make_token() -> str:
    """Build a syntactically valid JWT (unsigned) with no region claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "abc", "exp": 1799508513}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.signature"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    """Neutralise the backoff so the suite stays fast."""
    monkeypatch.setattr("time.sleep", lambda _s: None)


def _client(handler) -> plaud_api.PlaudClient:
    client = plaud_api.PlaudClient(token=_make_token())
    client._http = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer x"},
    )
    return client


_FILES_OK = {"status": 200, "data": [{"file_id": "abc", "file_name": "note"}]}


def _flaky(failures: int, exc: Exception):
    """Handler that raises ``exc`` for the first ``failures`` calls."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= failures:
            raise exc
        return httpx.Response(200, json=_FILES_OK)

    return handler, calls


def _status_then_ok(failures: int, status: int):
    """Handler that returns ``status`` for the first ``failures`` calls."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= failures:
            return httpx.Response(status, json={"msg": "nope"})
        return httpx.Response(200, json=_FILES_OK)

    return handler, calls


# ── transient transport errors are retried ───────────────────────────────

def test_read_timeout_is_retried_then_succeeds():
    handler, calls = _flaky(1, httpx.ReadTimeout("The read operation timed out"))
    files = _client(handler).list_files()
    assert calls["n"] == 2
    assert files[0]["file_id"] == "abc"


def test_dns_failure_is_retried_then_succeeds():
    handler, calls = _flaky(
        1, httpx.ConnectError("[Errno -3] Temporary failure in name resolution")
    )
    files = _client(handler).list_files()
    assert calls["n"] == 2
    assert files[0]["file_id"] == "abc"


def test_retry_survives_failures_up_to_the_attempt_budget():
    handler, calls = _flaky(
        plaud_api.RETRY_ATTEMPTS - 1, httpx.ReadTimeout("timed out")
    )
    files = _client(handler).list_files()
    assert calls["n"] == plaud_api.RETRY_ATTEMPTS
    assert files[0]["file_id"] == "abc"


def test_persistent_timeout_gives_up_and_reports_network_error():
    handler, calls = _flaky(99, httpx.ReadTimeout("The read operation timed out"))
    with pytest.raises(plaud_api.PlaudApiError) as exc:
        _client(handler).list_files()
    assert calls["n"] == plaud_api.RETRY_ATTEMPTS
    assert exc.value.category == "network"
    assert "read operation timed out" in str(exc.value)


# ── retryable statuses ───────────────────────────────────────────────────

def test_503_is_retried_then_succeeds():
    handler, calls = _status_then_ok(1, 503)
    files = _client(handler).list_files()
    assert calls["n"] == 2
    assert files[0]["file_id"] == "abc"


def test_429_is_retried_then_succeeds():
    handler, calls = _status_then_ok(1, 429)
    files = _client(handler).list_files()
    assert calls["n"] == 2


def test_persistent_503_gives_up_and_reports_server_error():
    handler, calls = _status_then_ok(99, 503)
    with pytest.raises(plaud_api.PlaudApiError) as exc:
        _client(handler).list_files()
    assert calls["n"] == plaud_api.RETRY_ATTEMPTS
    assert exc.value.category == "server"
    assert exc.value.status == 503


# ── non-transient failures must stay fast ────────────────────────────────

def test_401_is_not_retried():
    handler, calls = _status_then_ok(99, 401)
    with pytest.raises(plaud_api.PlaudApiError) as exc:
        _client(handler).list_files()
    assert calls["n"] == 1, "auth failures must fail fast, not burn the budget"
    assert exc.value.category == "auth"


def test_404_is_not_retried():
    handler, calls = _status_then_ok(99, 404)
    with pytest.raises(plaud_api.PlaudApiError):
        _client(handler).list_files()
    assert calls["n"] == 1


# ── backoff shape ────────────────────────────────────────────────────────

def test_backoff_doubles_and_is_capped():
    waits: list[float] = []

    def always_timeout() -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(httpx.ReadTimeout):
        plaud_api._send_with_retry(always_timeout, attempts=6, sleep=waits.append)

    # One wait per failed attempt except the last, doubling from the base and
    # never exceeding the cap.
    assert waits == [1.0, 2.0, 4.0, 8.0, 8.0]
    assert max(waits) <= plaud_api.RETRY_MAX_SLEEP


def test_single_attempt_does_not_sleep():
    waits: list[float] = []

    def always_timeout() -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(httpx.ReadTimeout):
        plaud_api._send_with_retry(always_timeout, attempts=1, sleep=waits.append)
    assert waits == []


# ── login path shares the policy ─────────────────────────────────────────

def test_authenticate_retries_a_read_timeout(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("The read operation timed out")
        return httpx.Response(200, json={"access_token": "fresh-token"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    token = plaud_api._authenticate(http, "a@b.c", "pw", plaud_api.API_BASE)
    assert calls["n"] == 2
    assert token == "fresh-token"
