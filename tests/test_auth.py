"""Tests for credential login (POST /auth/access-token) and token auto-refresh."""

from __future__ import annotations

import base64
import json
import time

import httpx
import pytest
from click.testing import CliRunner

from plaud_cli import api as plaud_api
from plaud_cli import cli
from plaud_cli import config as cfg


def _jwt(claims: dict) -> str:
    def b64(o: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(claims)}.sig"


def _auth_client(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.fixture
def tmp_cfg(tmp_path, monkeypatch):
    monkeypatch.delenv("PLAUD_EMAIL", raising=False)
    monkeypatch.delenv("PLAUD_PASSWORD", raising=False)
    cfg.set_config_path(tmp_path / "config.yaml")
    return tmp_path / "config.yaml"


# --------------------------------------------------------------------------
# token_needs_refresh
# --------------------------------------------------------------------------

def test_token_needs_refresh_when_missing():
    assert plaud_api.token_needs_refresh(None) is True
    assert plaud_api.token_needs_refresh("") is True


def test_token_needs_refresh_when_expired_or_within_skew():
    assert plaud_api.token_needs_refresh(_jwt({"exp": int(time.time()) - 10})) is True
    assert plaud_api.token_needs_refresh(_jwt({"exp": int(time.time()) + 60})) is True


def test_token_does_not_need_refresh_when_far_from_expiry():
    assert plaud_api.token_needs_refresh(_jwt({"exp": int(time.time()) + 4000})) is False


def test_token_without_exp_is_treated_as_long_lived():
    assert plaud_api.token_needs_refresh(_jwt({"region": "aws:us-west-2"})) is False


# --------------------------------------------------------------------------
# _extract_access_token
# --------------------------------------------------------------------------

def test_extract_access_token_top_level():
    assert plaud_api._extract_access_token({"access_token": "tok", "token_type": "bearer"}) == "tok"


def test_extract_access_token_nested_in_data():
    assert plaud_api._extract_access_token({"status": 0, "data": {"access_token": "tok"}}) == "tok"


def test_extract_access_token_missing():
    assert plaud_api._extract_access_token({"status": 0}) is None


# --------------------------------------------------------------------------
# authenticate (form POST + region redirect)
# --------------------------------------------------------------------------

def test_authenticate_posts_form_and_returns_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["ct"] = request.headers.get("content-type", "")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "new.jwt.tok", "token_type": "bearer"})

    tok = plaud_api._authenticate(_auth_client(handler), "me@example.com", "pw", "https://api.plaud.ai")

    assert tok == "new.jwt.tok"
    assert seen["url"].endswith("/auth/access-token")
    assert "application/x-www-form-urlencoded" in seen["ct"]
    assert "username=me%40example.com" in seen["body"]
    assert "password=pw" in seen["body"]


def test_authenticate_follows_region_redirect():
    hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "api.plaud.ai":
            return httpx.Response(200, json={
                "status": -302, "msg": "user region mismatch",
                "data": {"domains": {"api": "https://api-euc1.plaud.ai"}},
            })
        if request.url.host == "api-euc1.plaud.ai":
            return httpx.Response(200, json={"access_token": "eu.tok"})
        return httpx.Response(404)

    tok = plaud_api._authenticate(_auth_client(handler), "me@example.com", "pw", "https://api.plaud.ai")

    assert tok == "eu.tok"
    assert hosts == ["api.plaud.ai", "api-euc1.plaud.ai"]


def test_authenticate_raises_auth_on_http_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid credentials"})

    with pytest.raises(plaud_api.PlaudApiError) as ei:
        plaud_api._authenticate(_auth_client(handler), "me@example.com", "bad", "https://api.plaud.ai")
    assert ei.value.category == "auth"


def test_authenticate_raises_on_envelope_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": -1, "msg": "password error"})

    with pytest.raises(plaud_api.PlaudApiError):
        plaud_api._authenticate(_auth_client(handler), "me@example.com", "bad", "https://api.plaud.ai")


# --------------------------------------------------------------------------
# config: credentials (env-first, config fallback)
# --------------------------------------------------------------------------

def test_save_and_get_credentials(tmp_cfg):
    cfg.save_credentials("a@b.com", "secret")
    assert cfg.get_credentials() == ("a@b.com", "secret")


def test_get_credentials_env_overrides_config(tmp_cfg, monkeypatch):
    cfg.save_credentials("file@b.com", "filepw")
    monkeypatch.setenv("PLAUD_EMAIL", "env@b.com")
    monkeypatch.setenv("PLAUD_PASSWORD", "envpw")
    assert cfg.get_credentials() == ("env@b.com", "envpw")


def test_get_credentials_none_when_unset(tmp_cfg):
    assert cfg.get_credentials() == (None, None)


# --------------------------------------------------------------------------
# CLI: login --email/--password and auto-refresh in _require_token
# --------------------------------------------------------------------------

def test_login_with_credentials_mints_and_saves(tmp_cfg, monkeypatch):
    monkeypatch.setattr(plaud_api, "authenticate", lambda email, password, api_base=None: "minted.tok")
    result = CliRunner().invoke(
        cli.main,
        ["--config", str(tmp_cfg), "login", "--email", "me@x.com", "--password", "pw"],
    )
    assert result.exit_code == 0, result.output
    assert cfg.get_token() == "minted.tok"
    assert cfg.get_credentials() == ("me@x.com", "pw")


def test_login_with_credentials_no_save(tmp_cfg, monkeypatch):
    monkeypatch.setattr(plaud_api, "authenticate", lambda email, password, api_base=None: "minted.tok")
    result = CliRunner().invoke(
        cli.main,
        ["--config", str(tmp_cfg), "login", "--email", "me@x.com", "--password", "pw", "--no-save-credentials"],
    )
    assert result.exit_code == 0, result.output
    assert cfg.get_token() == "minted.tok"
    assert cfg.get_credentials() == (None, None)


def test_require_token_auto_refreshes_expired(tmp_cfg, monkeypatch):
    cfg.save_token(_jwt({"exp": int(time.time()) - 10}))
    cfg.save_credentials("me@x.com", "pw")
    monkeypatch.setattr(plaud_api, "authenticate", lambda email, password, api_base=None: "fresh.tok")

    assert cli._require_token(None) == "fresh.tok"
    assert cfg.get_token() == "fresh.tok"


def test_require_token_skips_refresh_when_valid(tmp_cfg, monkeypatch):
    valid = _jwt({"exp": int(time.time()) + 10000})
    cfg.save_token(valid)
    cfg.save_credentials("me@x.com", "pw")
    calls = {"n": 0}

    def fake_auth(*a, **k):
        calls["n"] += 1
        return "unused"

    monkeypatch.setattr(plaud_api, "authenticate", fake_auth)

    assert cli._require_token(None) == valid
    assert calls["n"] == 0


def test_require_token_explicit_token_is_not_refreshed(tmp_cfg, monkeypatch):
    cfg.save_credentials("me@x.com", "pw")
    calls = {"n": 0}
    monkeypatch.setattr(plaud_api, "authenticate", lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or "x")

    assert cli._require_token("explicit.tok") == "explicit.tok"
    assert calls["n"] == 0
