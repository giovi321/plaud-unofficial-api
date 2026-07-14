---
title: export
description: Export one recording to Markdown, JSON, or plain text, and optionally its audio.
---

Export a single recording's text content to a file (or stdout), and optionally download the audio alongside it.

```bash
plaud export <file_id> --format markdown -o ./meeting.md
```

## Options

| Option | Description |
| --- | --- |
| `--token TEXT` | Override the stored token for this call. |
| `--format markdown\|json\|txt` | Output format for the included text content. Default: `markdown`. |
| `--output`, `-o PATH` | Output file (base name). All selected text goes into this one file; an included recording is saved alongside with the same base name. Omit to print to stdout. |
| `--hydrate` / `--no-hydrate` | Fetch full transcript/summary (default). |
| `--include TYPE` | Content to include; repeat to select multiple. One of `transcript`, `summary`, `highlights`, `recording`. Defaults to all text types (`transcript`, `summary`, `highlights`). |

## Notes

- The `--format` option applies to the text content (summary, highlights, transcript), rendered into a single file.
- `--include recording` downloads the audio as a separate file using the same base name; it is not affected by `--format`.
- Markdown output has front matter (`file_id`, `date`, `duration`) and `## Summary` / `## Highlights` / `## Transcript` sections, each emitted only when that content is present and requested.

## Examples

```bash
# Just the transcript, as plain text, to stdout
plaud export <file_id> --format txt --include transcript

# Markdown note plus the audio file
plaud export <file_id> -o ./notes/call.md \
  --include summary --include transcript --include recording
```

To do this across your whole account instead of one recording at a time, use [`sync`](/plaud-unofficial-api/commands/sync/).
