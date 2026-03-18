"""Normalize raw Plaud API payloads into a consistent structure."""

from __future__ import annotations

import json
import re
from typing import Any


def _first_str(values: list[Any]) -> str:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _strip_markup(value: str) -> str:
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"!\[.*?\]\(.*?\)", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _as_nonneg_int(value: Any) -> int:
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return 0


def _extract_summary(detail: dict[str, Any]) -> str:
    direct = _first_str([
        detail.get("summary"),
        detail.get("ai_content", {}).get("summary") if isinstance(detail.get("ai_content"), dict) else None,
        detail.get("ai_notes", {}).get("summary") if isinstance(detail.get("ai_notes"), dict) else None,
        detail.get("ai_notes", {}).get("abstract") if isinstance(detail.get("ai_notes"), dict) else None,
    ])
    if direct:
        try:
            parsed = json.loads(direct)
            if isinstance(parsed, dict):
                for key in ("summary", "abstract", "content", "text", "ai_content"):
                    v = parsed.get(key)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                    if isinstance(v, dict):
                        for sub_key in ("summary", "abstract", "content", "text"):
                            sv = v.get(sub_key)
                            if isinstance(sv, str) and sv.strip():
                                return sv.strip()
        except Exception:
            pass
        return direct

    for item in (detail.get("pre_download_content_list") or []):
        if not isinstance(item, dict):
            continue
        item_type = _first_str([item.get("type"), item.get("label"), item.get("name")]).lower()
        if "summary" in item_type or "abstract" in item_type:
            content = _first_str([item.get("content"), item.get("value"), item.get("text")])
            if content:
                return content
        data_id = _first_str([item.get("data_id")]).lower()
        if data_id.startswith("auto_sum:") or "summary" in data_id:
            content = _first_str([item.get("data_content"), item.get("content"), item.get("value"), item.get("text")])
            cleaned = _strip_markup(content)
            if cleaned:
                return cleaned

    return ""


def _normalize_highlight(entry: Any) -> str:
    if isinstance(entry, dict):
        return _first_str([
            entry.get("text"), entry.get("value"), entry.get("content"),
            entry.get("highlight"), entry.get("title"),
        ])
    if isinstance(entry, str):
        return entry.strip()
    return ""


def _parse_highlights_string(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [h for h in (_normalize_highlight(p) for p in parsed) if h]
    except Exception:
        pass
    return [
        re.sub(r"^[-*]\s*", "", line).strip()
        for line in value.splitlines()
        if line.strip()
    ]


def _extract_highlights(detail: dict[str, Any]) -> list[str]:
    candidates = [
        detail.get("highlights"),
        detail.get("ai_content", {}).get("highlights") if isinstance(detail.get("ai_content"), dict) else None,
        detail.get("ai_notes", {}).get("highlights") if isinstance(detail.get("ai_notes"), dict) else None,
        detail.get("ai_notes", {}).get("key_points") if isinstance(detail.get("ai_notes"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            normalized = [h for h in (_normalize_highlight(e) for e in candidate) if h]
            if normalized:
                return normalized
        if isinstance(candidate, str):
            normalized = _parse_highlights_string(candidate.strip())
            if normalized:
                return normalized

    for item in (detail.get("pre_download_content_list") or []):
        if not isinstance(item, dict):
            continue
        data_id = _first_str([item.get("data_id")]).lower()
        if not data_id.startswith("note:"):
            continue
        content = _first_str([item.get("data_content"), item.get("content"), item.get("value"), item.get("text")])
        if not content:
            continue
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                highlights = [h for h in (_normalize_highlight(e) for e in parsed) if h]
                if highlights:
                    return highlights
        except Exception:
            fallback = _strip_markup(content)
            if fallback:
                return [fallback]

    return []


def _normalize_transcript_line(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    speaker = _first_str([entry.get("speaker"), entry.get("speaker_name"), entry.get("name")]) or "Speaker"
    text = _first_str([entry.get("text"), entry.get("content"), entry.get("value")])
    if not text:
        return ""
    return f"{speaker}: {text}"


def _extract_transcript(detail: dict[str, Any]) -> str:
    trans = detail.get("trans_result") if isinstance(detail.get("trans_result"), dict) else {}
    direct = _first_str([
        trans.get("full_text") if trans else None,
        detail.get("full_text"),
        detail.get("transcript_text"),
    ])
    if direct:
        return direct

    arrays = [
        trans.get("paragraphs") if trans else None,
        trans.get("sentences") if trans else None,
        detail.get("transcript"),
        detail.get("paragraphs"),
    ]
    for candidate in arrays:
        if not isinstance(candidate, list):
            continue
        lines = [l for l in (_normalize_transcript_line(e) for e in candidate) if l]
        if lines:
            return "\n".join(lines)

    return ""


def normalize(raw: Any) -> dict[str, Any]:
    """Return a normalized dict from a raw Plaud file detail payload."""
    detail: dict[str, Any] = raw if isinstance(raw, dict) else {}

    file_id = _first_str([detail.get("file_id"), detail.get("id")]) or "unknown"
    rec_id = _first_str([detail.get("id"), detail.get("file_id")]) or "unknown"
    title = _first_str([detail.get("file_name"), detail.get("filename"), detail.get("title")])

    return {
        "id": rec_id,
        "file_id": file_id,
        "title": title,
        "start_time_ms": _as_nonneg_int(detail.get("start_time")),
        "duration_ms": _as_nonneg_int(detail.get("duration")),
        "summary": _extract_summary(detail),
        "highlights": _extract_highlights(detail),
        "transcript": _extract_transcript(detail),
        "raw": detail,
    }
