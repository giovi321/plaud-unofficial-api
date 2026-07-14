---
title: list
description: List all recordings in your Plaud account.
---

List every recording in your account as a table (index, ID, date, duration, title).

```bash
plaud list
```

## Options

| Option | Description |
| --- | --- |
| `--token TEXT` | Override the stored token for this call. |
| `--json` | Output the raw JSON instead of a table. |
| `--no-trash` / `--trash` | Hide trashed recordings (default) or include them. |
| `--limit N` | Limit the number of results (`0` = all, the default). |

## Examples

```bash
# The 10 most recent, as a table
plaud list --limit 10

# Everything, as JSON (useful for scripting file_ids)
plaud list --json
```

Each row's ID is the `file_id` you pass to [`detail`](/plaud-unofficial-api/commands/detail/) and [`export`](/plaud-unofficial-api/commands/export/).
