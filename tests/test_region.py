"""Tests for region-aware host routing and -302 redirect handling."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from plaud_cli import api as plaud_api


def _make_token(region: str | None = None) -> str:
    """Build a syntactically valid JWT (unsigned) carrying a region claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload_obj: dict[str, object] = {"sub": "abc", "exp": 1799508513}
    if region is not None:
        payload_obj["region"] = region
    payload = base64.urlsafe_b64encode(json.dumps(payload_obj).encode()).decode().rstrip("=")
    return f"{header}.{payload}.signature"


def _mock(client: plaud_api.PlaudClient, handler) -> None:
    """Swap the client's HTTP transport for an in-memory mock (network boundary only)."""
    client._http = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer x"},
    )


def test_us_west_2_token_routes_to_regional_host():
    client = plaud_api.PlaudClient(token=_make_token("aws:us-west-2"))
    assert client._base == "https://api-usw2.plaud.ai"


def test_eu_central_token_routes_to_regional_host():
    client = plaud_api.PlaudClient(token=_make_token("aws:eu-central-1"))
    assert client._base == "https://api-euc1.plaud.ai"


def test_explicit_api_base_override_is_respected():
    # A user who ran `plaud config set-api` keeps their chosen host.
    client = plaud_api.PlaudClient(
        token=_make_token("aws:us-west-2"),
        api_base="https://api-euc1.plaud.ai",
    )
    assert client._base == "https://api-euc1.plaud.ai"


def test_unknown_region_falls_back_to_discovery_host():
    client = plaud_api.PlaudClient(token=_make_token("aws:moon-base-1"))
    assert client._base == "https://api.plaud.ai"


def test_no_region_claim_keeps_default_host():
    client = plaud_api.PlaudClient(token=_make_token(None))
    assert client._base == "https://api.plaud.ai"


def test_minus_302_redirect_follows_domain_and_retries():
    seen_hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_hosts.append(request.url.host)
        if request.url.host == "api.plaud.ai":
            return httpx.Response(
                200,
                json={"status": -302, "msg": "user region mismatch", "domain": "api-usw2.plaud.ai"},
            )
        if request.url.host == "api-usw2.plaud.ai":
            return httpx.Response(200, json={"status": 0, "data_file_list": [{"id": "rec1"}]})
        return httpx.Response(404)

    # No region claim -> starts on the discovery host, then follows the -302.
    client = plaud_api.PlaudClient(token=_make_token(None))
    _mock(client, handler)

    files = client.list_files()

    assert files == [{"id": "rec1"}]
    assert client._base == "https://api-usw2.plaud.ai"
    assert seen_hosts == ["api.plaud.ai", "api-usw2.plaud.ai"]


def test_minus_302_follows_real_nested_domain_envelope():
    # The actual Plaud response shape, captured from the live API:
    # {"status": -302, "msg": "user region mismatch",
    #  "data": {"domains": {"api": "https://api-euc1.plaud.ai"}}}
    seen_hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_hosts.append(request.url.host)
        if request.url.host in ("api.plaud.ai", "api-usw2.plaud.ai"):
            return httpx.Response(
                200,
                json={
                    "status": -302,
                    "msg": "user region mismatch",
                    "data": {"domains": {"api": "https://api-euc1.plaud.ai"}},
                },
            )
        if request.url.host == "api-euc1.plaud.ai":
            return httpx.Response(200, json={"status": 0, "data_file_list": [{"id": "rec1"}]})
        return httpx.Response(404)

    # No region claim -> starts on the discovery host, then follows the -302.
    client = plaud_api.PlaudClient(token=_make_token(None))
    _mock(client, handler)

    files = client.list_files()

    assert files == [{"id": "rec1"}]
    assert client._base == "https://api-euc1.plaud.ai"
    assert seen_hosts == ["api.plaud.ai", "api-euc1.plaud.ai"]


def test_stale_token_region_is_overridden_by_server_redirect():
    # Token claims us-west-2 but the account's data lives in eu-central-1.
    # The server's -302 domain must win over the token's region claim.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api-usw2.plaud.ai":
            return httpx.Response(
                200,
                json={
                    "status": -302,
                    "msg": "user region mismatch",
                    "data": {"domains": {"api": "https://api-euc1.plaud.ai"}},
                },
            )
        if request.url.host == "api-euc1.plaud.ai":
            return httpx.Response(200, json={"status": 0, "data_file_list": []})
        return httpx.Response(404)

    # Default base -> startup routing sends the us-west-2 token to api-usw2,
    # which -302s to the real EU host.
    client = plaud_api.PlaudClient(token=_make_token("aws:us-west-2"))
    assert client._base == "https://api-usw2.plaud.ai"
    _mock(client, handler)

    client.list_files()

    assert client._base == "https://api-euc1.plaud.ai"


def test_minus_302_without_domain_uses_token_region_claim():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.plaud.ai":
            return httpx.Response(200, json={"status": -302, "msg": "user region mismatch"})
        if request.url.host == "api-usw2.plaud.ai":
            return httpx.Response(200, json={"status": 0, "data_file_list": []})
        return httpx.Response(404)

    # Force start on the discovery host despite the region claim, to exercise
    # the body-less -302 fallback that recovers the host from the token.
    client = plaud_api.PlaudClient(
        token=_make_token("aws:us-west-2"),
        api_base="https://api.plaud.ai",
    )
    object.__setattr__(client, "_base", "https://api.plaud.ai")
    _mock(client, handler)

    client.list_files()

    assert client._base == "https://api-usw2.plaud.ai"


def test_minus_302_redirect_rejects_non_plaud_domain():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": -302, "msg": "user region mismatch", "domain": "evil.example.com"},
        )

    client = plaud_api.PlaudClient(token=_make_token(None))
    _mock(client, handler)

    with pytest.raises(plaud_api.PlaudApiError):
        client.list_files()
    # Never redirected to the untrusted host.
    assert client._base == "https://api.plaud.ai"
