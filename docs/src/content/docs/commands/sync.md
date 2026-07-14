---
title: sync
description: Synchronise a local folder with your Plaud recordings.
---

Download recordings into a local folder, skipping anything already present, and (optionally) keep a registry so moved or renamed files are not downloaded again.

```bash
plaud sync ./notes --mode two-way --registry --only-ready \
  --include transcript --include summary
```

## Options

| Option | Description |
| --- | --- |
| `--token TEXT` | Override the stored token. |
| `--mode one-way\|two-way` | `one-way` (default) downloads missing/updated recordings. `two-way` also reports local files whose recording was deleted on the remote (it never deletes local files). |
| `--format markdown\|json\|txt` | Output format for the text content. Default: `markdown`. |
| `--no-trash` / `--trash` | Skip trashed recordings (default) or include them. |
| `--hydrate` / `--no-hydrate` | Fetch full transcript/summary (default). |
| `--since DATE` | Only sync recordings newer than this ISO-8601 date (e.g. `2026-01-01`). |
| `--registry` / `--no-registry` | Maintain a `.plaud_registry.json` in the output folder tracking which `file_id`s were downloaded, so renamed/moved local files are not re-downloaded. |
| `--dry-run` | Print what would be downloaded/warned about without writing files. |
| `--only-ready` | Skip a recording until the required text types are ready. See [Sync readiness](/plaud-unofficial-api/guides/readiness/). |
| `--ready-timeout-days N` | With `--only-ready`, once a recording is older than N days, sync it with whatever is available (`0` = wait forever). |
| `--ready-requires TYPE` | With `--only-ready`, only these text types must be present for a recording to count as ready (default: every included text type). Repeat to select multiple. |
| `--include TYPE` | Content to include; repeat to select multiple. `transcript`, `summary`, `highlights`, `recording`. Defaults to the text types. |

## What "present" means

A recording is considered already downloaded if its `file_id` is in the registry (with `--registry`) or a file with the expected name already exists in the output folder. Filenames are `YYYY-MM-DD_<title>.<ext>`, using the recording's local date, with filesystem-illegal and control characters replaced.

- The filename is kept **stable** across re-downloads even if the title changed on the Plaud side, so downstream mirrors do not get a second copy.
- A recording that reappears under a new name (same `file_id`) is treated as a **rename**, not a new file.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `2` | One or more recordings failed to download (partial failure). Wrappers can alert on this without treating the run as a hard failure. |

## Typical scheduled run

```bash
plaud sync /path/to/notes \
  --mode two-way --registry --format markdown \
  --only-ready --ready-timeout-days 5 --ready-requires transcript \
  --include summary --include transcript
```

This downloads a recording as soon as its transcript is ready, still exports a summary when one exists, and force-syncs anything older than 5 days even if a section never generated. The reasoning behind those flags is in [Sync readiness](/plaud-unofficial-api/guides/readiness/).
