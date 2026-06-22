"""Plaud.ai unofficial API client."""

from __future__ import annotations

import re
from typing import Any

import httpx

API_BASE = "https://api.plaud.ai"


class PlaudApiError(Exception):
    """Raised when the Plaud API returns an error."""

    def __init__(self, category: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status = status


def _normalize_token(token: str) -> str:
    token = token.strip()
    token = re.sub(r"^bearer\s+", "", token, flags=re.IGNORECASE)
    return token


# Plaud splits accounts across dedicated regional API hosts. The host is
# derived from the AWS region claim embedded in the JWT; api.plaud.ai is the
# discovery host that rejects region-pinned tokens with a -302 redirect.
_REGION_HOSTS = {
    "aws:eu-central-1": "api-euc1.plaud.ai",
    "aws:eu-west-1": "api-euw1.plaud.ai",
    "aws:us-east-1": "api-use1.plaud.ai",
    "aws:us-east-2": "api-use2.plaud.ai",
    "aws:us-west-1": "api-usw1.plaud.ai",
    "aws:us-west-2": "api-usw2.plaud.ai",
    "aws:ap-southeast-1": "api-apse1.plaud.ai",
    "aws:ap-southeast-2": "api-apse2.plaud.ai",
    "aws:ap-northeast-1": "api-apne1.plaud.ai",
    "aws:ap-south-1": "api-aps1.plaud.ai",
}


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode a JWT payload into a claims dict (no signature verification)."""
    import base64
    import json

    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _decode_jwt_region(token: str) -> str | None:
    """Return the AWS region claim embedded in a Plaud JWT, if present."""
    region = _decode_jwt(token).get("region")
    return region if isinstance(region, str) and region else None


def token_needs_refresh(token: str | None, skew: int = 300) -> bool:
    """True when there is no token, or its ``exp`` is within ``skew`` seconds.

    A token with no ``exp`` claim is treated as long-lived (no refresh forced),
    matching Plaud's legacy tokens; current v2 tokens carry a short ``exp``
    (observed ~24h for browser-captured tokens, ~30 days for credential-login
    tokens) and are refreshed proactively as they near expiry.
    """
    import time

    if not token:
        return True
    exp = _decode_jwt(_normalize_token(token)).get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return exp - time.time() <= skew


def _region_base_from_token(token: str) -> str | None:
    """Map the token's region claim to its dedicated Plaud API base URL."""
    region = _decode_jwt_region(token)
    if not region:
        return None
    host = _REGION_HOSTS.get(region)
    return f"https://{host}" if host else None


def _safe_plaud_host(host: str) -> str | None:
    """Accept only bare ``*.plaud.ai`` hosts as redirect targets."""
    host = host.strip().lower()
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/", 1)[0]
    if host == "plaud.ai" or host.endswith(".plaud.ai"):
        return host
    return None


def _extract_redirect_domain(data: dict[str, Any]) -> str | None:
    """Pull the correct API host out of a -302 ``user region mismatch`` body.

    Observed shape (live API):
        {"status": -302, "data": {"domains": {"api": "https://api-euc1.plaud.ai"}}}
    A few flatter variants are tolerated defensively.
    """
    inner = data.get("data")
    if isinstance(inner, dict):
        domains = inner.get("domains")
        if isinstance(domains, dict):
            for k in ("api", "host", "web"):
                v = domains.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    for key in ("domain", "region_domain"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            d = v.get("api") or v.get("domain") or v.get("host")
            if isinstance(d, str) and d.strip():
                return d.strip()
    return None


def _is_region_mismatch(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return (
        data.get("status") == -302
        or str(data.get("msg", "")).strip().lower() == "user region mismatch"
    )


def _redirect_base_from_body(data: Any) -> str | None:
    """Return the ``*.plaud.ai`` base URL a -302 body points to, if any."""
    if not _is_region_mismatch(data):
        return None
    domain = _extract_redirect_domain(data)
    host = _safe_plaud_host(domain) if domain else None
    return f"https://{host}" if host else None


def _extract_access_token(data: Any) -> str | None:
    """Pull ``access_token`` out of a login response (top level or under data)."""
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    for container in (data, inner if isinstance(inner, dict) else None):
        if isinstance(container, dict):
            v = container.get("access_token")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def authenticate(
    email: str, password: str, api_base: str = API_BASE, timeout: float = 30.0
) -> str:
    """Log in with email + password and return a fresh access token.

    Calls ``POST /auth/access-token`` (the web app's credential login, form
    encoded) and follows the regional ``-302`` redirect once. Raises
    ``PlaudApiError`` on failure.

    Uses a deliberately minimal header set: the login endpoint returns a stub
    with an empty token when sent the full browser-fingerprint headers that the
    data endpoints expect.
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://web.plaud.ai",
        "Referer": "https://web.plaud.ai/",
    }
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as http:
        return _authenticate(http, email, password, api_base.rstrip("/"))


def _authenticate(http: httpx.Client, email: str, password: str, base: str) -> str:
    form = {"username": email, "password": password}
    for attempt in range(2):
        try:
            resp = http.post(f"{base}/auth/access-token", data=form)
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            cat = _map_status_category(resp.status_code)
            raise PlaudApiError(cat, f"HTTP {resp.status_code}", status=resp.status_code)
        data = resp.json()
        redirect = _redirect_base_from_body(data)
        if redirect and attempt == 0:
            base = redirect
            continue
        token = _extract_access_token(data)
        if token:
            return _normalize_token(token)
        _assert_envelope_success(data)
        keys = ", ".join(sorted(data)) if isinstance(data, dict) else type(data).__name__
        raise PlaudApiError(
            "auth", f"Login response had no access_token (response keys: {keys})."
        )
    raise PlaudApiError("auth", "Login failed after a region redirect.")


def _is_success_status(status: Any) -> bool:
    if isinstance(status, int):
        return status in (0, 200)
    if isinstance(status, str):
        normalized = status.strip().lower()
        return normalized in ("0", "200", "ok", "success")
    return False


def _map_status_category(http_status: int) -> str:
    if http_status in (401, 403):
        return "auth"
    if http_status == 429:
        return "rate_limit"
    if http_status >= 500:
        return "server"
    return "network"


def _assert_envelope_success(data: dict[str, Any]) -> None:
    if "status" not in data:
        return
    if not _is_success_status(data["status"]):
        msg = data.get("msg", "")
        raise PlaudApiError(
            "invalid_response",
            str(msg) if msg else "Plaud API returned non-success status.",
        )


def _extract_list_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise PlaudApiError("invalid_response", "Plaud file list payload is malformed.")
    _assert_envelope_success(data)
    for key in ("payload", "data_file_list", "data"):
        if isinstance(data.get(key), list):
            return data[key]
    raise PlaudApiError("invalid_response", "Plaud file list payload must be an array.")


def _extract_detail_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise PlaudApiError("invalid_response", "Plaud file detail payload is malformed.")
    _assert_envelope_success(data)
    for key in ("payload", "data"):
        if isinstance(data.get(key), dict):
            return data[key]
    return data


_BROWSER_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://web.plaud.ai",
    "Referer": "https://web.plaud.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "app-platform": "web",
    "edit-from": "web",
    "Priority": "u=3, i",
}


class PlaudClient:
    """HTTP client for the Plaud.ai API."""

    def __init__(self, token: str, api_base: str = API_BASE, timeout: float = 30.0) -> None:
        self._token = _normalize_token(token)
        base = api_base.rstrip("/")
        # When left at the default discovery host, route to the account's
        # regional host derived from the token. An explicit override (set via
        # `plaud config set-api`) is always respected.
        if base == API_BASE:
            region_base = _region_base_from_token(self._token)
            if region_base:
                base = region_base
        self._base = base
        self._http = httpx.Client(
            timeout=timeout,
            headers={
                **_BROWSER_HEADERS,
                "Authorization": f"Bearer {self._token}",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "PlaudClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str, *, _redirected: bool = False) -> Any:
        try:
            resp = self._http.get(f"{self._base}{path}")
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            cat = _map_status_category(resp.status_code)
            raise PlaudApiError(cat, f"HTTP {resp.status_code}", status=resp.status_code)
        data = resp.json()
        if not _redirected:
            target = self._region_redirect_target(data)
            if target:
                self._base = target
                return self._get(path, _redirected=True)
        return data

    def _post(self, path: str, json_body: Any = None, *, _redirected: bool = False) -> Any:
        try:
            resp = self._http.post(f"{self._base}{path}", json=json_body)
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            cat = _map_status_category(resp.status_code)
            raise PlaudApiError(cat, f"HTTP {resp.status_code}", status=resp.status_code)
        data = resp.json()
        if not _redirected:
            target = self._region_redirect_target(data)
            if target:
                self._base = target
                return self._post(path, json_body, _redirected=True)
        return data

    def _region_redirect_target(self, data: Any) -> str | None:
        """Return the host to retry on when the API signals a region mismatch.

        The server's host (from the -302 body) wins over the token's region
        claim, which can be stale after an account migration. Only
        ``*.plaud.ai`` hosts are honoured.
        """
        if not _is_region_mismatch(data):
            return None
        return _redirect_base_from_body(data) or _region_base_from_token(self._token)

    def _fetch_url(self, url: str) -> Any:
        """Fetch an arbitrary URL (used for signed content links)."""
        try:
            resp = self._http.get(url)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return resp.text
        except httpx.HTTPStatusError as exc:
            raise PlaudApiError("network", f"HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def list_files(self) -> list[dict[str, Any]]:
        """Return a list of recording summaries."""
        data = self._get("/file/simple/web")
        return _extract_list_payload(data)

    def get_file_detail(self, file_id: str) -> dict[str, Any]:
        """Return full detail for a single recording."""
        from urllib.parse import quote
        data = self._get(f"/file/detail/{quote(file_id, safe='')}")
        return _extract_detail_payload(data)

    def get_file_detail_full(self, file_id: str) -> dict[str, Any]:
        """Return full detail via POST /file/list (includes trans_result inline)."""
        data = self._post("/file/list", json_body=[file_id])
        files = _extract_list_payload(data)
        if not files:
            raise PlaudApiError("not_found", f"Recording not found: {file_id}")
        return files[0]

    def get_file_detail_hydrated(self, file_id: str) -> dict[str, Any]:
        """Return full detail with transcript/summary.

        Uses POST /file/list as primary source (returns trans_result inline).
        Falls back to GET /file/detail + signed-URL hydration if the POST
        endpoint fails or returns incomplete data.
        """
        try:
            detail = self.get_file_detail_full(file_id)
            if _has_transcript(detail) and _has_summary(detail):
                return detail
            # Have inline data but missing some content – try hydration on top
            return self._hydrate(detail)
        except PlaudApiError:
            pass
        # Fallback: original GET + hydration path
        detail = self.get_file_detail(file_id)
        return self._hydrate(detail)

    def download_recording(self, detail: dict[str, Any]) -> tuple[bytes, str]:
        """Download the recording audio file. Returns (bytes, suggested_extension)."""
        link = _pick_recording_link(detail)
        if not link:
            raise PlaudApiError("not_found", "No recording download link found for this file.")
        try:
            resp = self._http.get(link)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PlaudApiError("network", f"HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc
        content_type = resp.headers.get("content-type", "")
        if "ogg" in content_type or link.endswith(".ogg"):
            ext = "ogg"
        elif "wav" in content_type or link.endswith(".wav"):
            ext = "wav"
        elif "mp3" in content_type or link.endswith(".mp3"):
            ext = "mp3"
        elif "mp4" in content_type or "m4a" in content_type or link.endswith(".m4a"):
            ext = "m4a"
        else:
            ext = "ogg"
        return resp.content, ext

    def _hydrate(self, detail: dict[str, Any]) -> dict[str, Any]:
        """Best-effort: fetch transcript and summary from content_list signed URLs."""
        result = dict(detail)

        if not _has_summary(result):
            link = _pick_content_link(result, "auto_sum_note")
            if link:
                try:
                    content = self._fetch_url(link)
                    _apply_summary(result, content)
                except PlaudApiError:
                    pass

        if not _has_transcript(result):
            link = _pick_content_link(result, "transaction")
            if link:
                try:
                    content = self._fetch_url(link)
                    _apply_transcript(result, content)
                except PlaudApiError:
                    pass

        return result


# ------------------------------------------------------------------
# Hydration helpers
# ------------------------------------------------------------------

def _has_transcript(detail: dict[str, Any]) -> bool:
    if isinstance(detail.get("transcript_text"), str) and detail["transcript_text"].strip():
        return True
    if isinstance(detail.get("full_text"), str) and detail["full_text"].strip():
        return True
    if isinstance(detail.get("transcript"), list) and detail["transcript"]:
        return True
    trans = detail.get("trans_result")
    if isinstance(trans, list) and trans:
        return True
    if isinstance(trans, dict):
        if isinstance(trans.get("full_text"), str) and trans["full_text"].strip():
            return True
        if isinstance(trans.get("paragraphs"), list) and trans["paragraphs"]:
            return True
        if isinstance(trans.get("sentences"), list) and trans["sentences"]:
            return True
    return False


def _has_summary(detail: dict[str, Any]) -> bool:
    import json as _json
    summary = detail.get("summary")
    if isinstance(summary, str) and summary.strip():
        try:
            _json.loads(summary.strip())
        except Exception:
            return True
    ai = detail.get("ai_content")
    if isinstance(ai, dict):
        for key in ("summary", "abstract", "ai_content"):
            v = ai.get(key)
            if isinstance(v, str) and v.strip():
                try:
                    _json.loads(v.strip())
                except Exception:
                    return True
    return False


def _pick_content_link(detail: dict[str, Any], data_type: str) -> str:
    content_list = detail.get("content_list", [])
    if not isinstance(content_list, list):
        return ""
    for item in content_list:
        if not isinstance(item, dict):
            continue
        item_type = ""
        for k in ("data_type", "type", "label", "name"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                item_type = v.strip().lower()
                break
        if item_type == data_type.lower():
            for k in ("data_link", "link", "url"):
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return ""


def _pick_recording_link(detail: dict[str, Any]) -> str:
    content_list = detail.get("content_list", [])
    if not isinstance(content_list, list):
        return ""
    for item in content_list:
        if not isinstance(item, dict):
            continue
        item_type = ""
        for k in ("data_type", "type", "label", "name"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                item_type = v.strip().lower()
                break
        if item_type in ("recording", "record", "audio", "raw_record"):
            for k in ("data_link", "link", "url"):
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return ""


def _parse_maybe_json(value: str) -> Any:
    import json
    try:
        return json.loads(value)
    except Exception:
        return value


def _apply_summary(detail: dict[str, Any], content: Any, _depth: int = 0) -> None:
    if _depth > 6:
        return
    if isinstance(content, str):
        parsed = _parse_maybe_json(content.strip())
        if isinstance(parsed, str):
            detail["summary"] = parsed
            return
        _apply_summary(detail, parsed, _depth + 1)
        return
    if not isinstance(content, dict):
        return
    for key in ("ai_content", "summary", "abstract", "content", "text"):
        v = content.get(key)
        if isinstance(v, str) and v.strip():
            maybe = _parse_maybe_json(v.strip())
            if isinstance(maybe, dict):
                _apply_summary(detail, maybe, _depth + 1)
            elif isinstance(maybe, str):
                detail["summary"] = maybe
            break
        if isinstance(v, dict):
            _apply_summary(detail, v, _depth + 1)
            break
    if not isinstance(detail.get("ai_content"), dict):
        detail["ai_content"] = {}
    ai: dict[str, Any] = detail["ai_content"]
    for key in ("summary", "highlights", "key_points", "abstract", "content"):
        if key in content and key not in ai:
            ai[key] = content[key]


def _apply_transcript(detail: dict[str, Any], content: Any) -> None:
    if isinstance(content, str):
        trimmed = content.strip()
        if not trimmed:
            return
        parsed = _parse_maybe_json(trimmed)
        if isinstance(parsed, str):
            detail["transcript_text"] = parsed
            return
        _apply_transcript(detail, parsed)
        return
    if isinstance(content, list):
        detail["transcript"] = content
        return
    if isinstance(content, dict):
        detail["trans_result"] = content
