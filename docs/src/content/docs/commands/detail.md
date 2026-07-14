---
title: detail
description: Show full detail for a single recording.
---

Show the summary, highlights, and full transcript for one recording.

```bash
plaud detail <file_id>
```

## Options

| Option | Description |
| --- | --- |
| `--token TEXT` | Override the stored token for this call. |
| `--json` | Output the raw, hydrated JSON payload instead of the formatted view. |
| `--hydrate` / `--no-hydrate` | Fetch the full transcript/summary (default), or show only what the list payload already contains. |

## Hydration

By default `detail` **hydrates**: it fetches the complete transcript and summary (via `POST /file/list`, falling back to signed content URLs). With `--no-hydrate` it uses the lighter `GET /file/detail` response, which may omit the fully rendered text. Use `--json` with `--no-hydrate` to inspect the raw API shape when debugging.

## Example

```bash
plaud detail 0123456789abcdef --json | jq keys
```

How the raw payload is turned into a clean summary/transcript/highlights is described in [Content extraction](/plaud-unofficial-api/guides/extraction/).
