---
title: Content extraction
description: How raw Plaud payloads are normalized into summary, highlights, and transcript.
---

Plaud's API returns a large, inconsistent payload per recording. The normalizer turns it into a predictable shape: `title`, `start_time_ms`, `duration_ms`, `summary`, `highlights`, and `transcript`. Understanding it helps when a note comes out missing a section.

## Transcript

The transcript is read, in order, from a direct `full_text` (under `trans_result` or the top level) or `transcript_text`; otherwise it is assembled from segment arrays (`trans_result` paragraphs/sentences, or a list of segments), one `Speaker: text` line per segment.

## Summary

The summary is pulled from the first source that yields non-empty text: `summary`, `ai_content.summary`, `ai_content` (when it is a string), `ai_notes.summary` / `ai_notes.abstract`, and finally summary-typed items in `pre_download_content_list`. JSON-encoded strings are unwrapped recursively.

### The transcript-is-not-a-summary guard

Some payloads nest raw **diarized transcript** under generic summary keys. Exporting that as `## Summary` would fill the summary with speaker-labelled transcript and falsely satisfy `--only-ready`. The normalizer drops a candidate summary only when it is clearly transcript:

- **Shape** — it is dominated (>= 60% of lines) by explicit `Speaker N:` / `Unknown Speaker N:` labels or `HH:MM(:SS)` timestamp prefixes, or
- **Overlap** — its substantial lines are mostly (>= 70%) verbatim lines from the transcript.

A label-heavy but genuine summary (`Date:`, `Attendees:`, `Action items:`) is **kept** — an earlier, over-eager version of this guard wrongly discarded those, which is why the test matters (see [Contributing](/plaud-unofficial-api/development/contributing/)).

:::caution[Template matters]
If a recording's Plaud template produces only a diarized transcript and no prose summary, the summary will (correctly) come out empty. Gate such syncs on `--ready-requires transcript` rather than waiting for a summary that will never exist — see [Sync readiness](/plaud-unofficial-api/guides/readiness/).
:::

## Highlights

Highlights come from `highlights`, `ai_content` / `ai_notes` highlight or key-point fields, or note-typed `pre_download_content_list` items, normalized into a plain list of strings. JSON-encoded lists are parsed; a plain string falls back to one highlight per line.
