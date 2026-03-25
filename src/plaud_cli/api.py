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


class PlaudClient:
    """HTTP client for the Plaud.ai API."""

    def __init__(self, token: str, api_base: str = API_BASE, timeout: float = 30.0) -> None:
        self._token = _normalize_token(token)
        self._base = api_base.rstrip("/")
        self._http = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._token}"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "PlaudClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get(self, path: str) -> Any:
        try:
            resp = self._http.get(f"{self._base}{path}")
        except httpx.RequestError as exc:
            raise PlaudApiError("network", f"Network error: {exc}") from exc
        if resp.status_code >= 400:
            cat = _map_status_category(resp.status_code)
            raise PlaudApiError(cat, f"HTTP {resp.status_code}", status=resp.status_code)
        return resp.json()

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

    def get_file_detail_hydrated(self, file_id: str) -> dict[str, Any]:
        """Return full detail with transcript/summary fetched from signed URLs."""
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
