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


_SUMMARY_KEYS = ("summary", "abstract", "content", "text", "ai_content", "note", "body")

# STRONG diarized-transcript signals only: explicit "Speaker 1:" /
# "Unknown Speaker 2:" labels, or "00:01:23" timestamp prefixes. Deliberately
# NOT a generic "Label: value" pattern — real meeting summaries are label-heavy
# ("Date:", "Action items:", "Attendees:"), and matching those silently drops
# genuine summaries (the transcript-overlap guard below catches bare-name
# diarization like "Andi:" instead).
_TRANSCRIPT_LINE = re.compile(
    r"^\s*(?:>?\s*(?:unknown\s+)?speaker\s*\d*\s*:|>?\s*\d{1,2}:\d{2}(?::\d{2})?\b)",
    re.IGNORECASE,
)


def _looks_like_transcript(text: str) -> bool:
    """True when a candidate 'summary' is diarized transcript by its shape.

    Fires only on unambiguous "Speaker N:" / timestamp-dominated text so a
    label-heavy but genuine summary is never misclassified.
    """
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 4:
        return False
    hits = sum(1 for l in lines if _TRANSCRIPT_LINE.match(l))
    return hits / len(lines) >= 0.6


def _overlaps_transcript(summary: str, transcript: str) -> bool:
    """True when the candidate summary is (mostly) verbatim transcript content.

    Catches transcript text mis-nested under a summary key regardless of its
    speaker-label format, without false-positiving on a genuine summary (which
    paraphrases and so shares little verbatim line content with the transcript).
    """
    if not summary or not transcript:
        return False
    s = summary.strip()
    if s in transcript:
        return True
    # Compare substantial lines (ignore short labels/headers) verbatim.
    s_lines = [l.strip() for l in s.splitlines() if len(l.strip()) >= 20]
    if len(s_lines) < 3:
        return False
    hits = sum(1 for l in s_lines if l in transcript)
    return hits / len(s_lines) >= 0.7


def _unwrap_summary_text(value: Any, _depth: int = 0) -> str:
    """Recursively unwrap a possibly JSON-encoded summary into plain text."""
    if _depth > 6:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            parsed = json.loads(stripped)
        except Exception:
            return stripped
        result = _unwrap_summary_text(parsed, _depth + 1)
        return result if result else stripped
    if isinstance(value, dict):
        for key in _SUMMARY_KEYS:
            v = value.get(key)
            if v is None:
                continue
            result = _unwrap_summary_text(v, _depth + 1)
            if result:
                return result
    return ""


def _extract_summary(detail: dict[str, Any]) -> str:
    candidates: list[Any] = [
        detail.get("summary"),
        detail.get("ai_content", {}).get("summary") if isinstance(detail.get("ai_content"), dict) else None,
        detail.get("ai_content") if isinstance(detail.get("ai_content"), str) else None,
        detail.get("ai_notes", {}).get("summary") if isinstance(detail.get("ai_notes"), dict) else None,
        detail.get("ai_notes", {}).get("abstract") if isinstance(detail.get("ai_notes"), dict) else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        result = _unwrap_summary_text(candidate)
        if result and not _looks_like_transcript(result):
            return result

    for item in (detail.get("pre_download_content_list") or []):
        if not isinstance(item, dict):
            continue
        item_type = _first_str([item.get("type"), item.get("label"), item.get("name")]).lower()
        if "summary" in item_type or "abstract" in item_type:
            content = _first_str([item.get("content"), item.get("value"), item.get("text")])
            if content:
                result = _unwrap_summary_text(content)
                if result and not _looks_like_transcript(result):
                    return result
        data_id = _first_str([item.get("data_id")]).lower()
        if data_id.startswith("auto_sum:") or "summary" in data_id:
            content = _first_str([item.get("data_content"), item.get("content"), item.get("value"), item.get("text")])
            if content:
                result = _unwrap_summary_text(content)
                if result and not _looks_like_transcript(result):
                    return result

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
    raw_trans = detail.get("trans_result")

    # trans_result may be a dict (from GET /file/detail hydration)
    # or a list of segments (from POST /file/list).
    trans_dict: dict[str, Any] = {}
    trans_list: list[Any] | None = None
    if isinstance(raw_trans, dict):
        trans_dict = raw_trans
    elif isinstance(raw_trans, list):
        trans_list = raw_trans

    direct = _first_str([
        trans_dict.get("full_text") if trans_dict else None,
        detail.get("full_text"),
        detail.get("transcript_text"),
    ])
    if direct:
        return direct

    arrays = [
        trans_list,
        trans_dict.get("paragraphs") if trans_dict else None,
        trans_dict.get("sentences") if trans_dict else None,
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

    summary = _extract_summary(detail)
    transcript = _extract_transcript(detail)
    # A "summary" that is really the transcript (mis-nested under a summary key)
    # is not a summary.
    if summary and transcript and _overlaps_transcript(summary, transcript):
        summary = ""

    return {
        "id": rec_id,
        "file_id": file_id,
        "title": title,
        "start_time_ms": _as_nonneg_int(detail.get("start_time")),
        "duration_ms": _as_nonneg_int(detail.get("duration")),
        "summary": summary,
        "highlights": _extract_highlights(detail),
        "transcript": transcript,
        "raw": detail,
    }
