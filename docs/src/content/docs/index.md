---
title: Plaud CLI
description: Unofficial command-line tool for the Plaud.ai API
---

`plaud-cli` is an unofficial, reverse-engineered command-line client for [plaud.ai](https://web.plaud.ai/). It downloads your recordings, transcripts, AI summaries and highlights, and syncs them to a local folder.

:::caution[Not affiliated with Plaud]
This project is not affiliated with or endorsed by Plaud AI. Use it only with your own account and in compliance with Plaud's Terms of Service. It authenticates with the same web token the Plaud web app uses, not Plaud's official OAuth developer platform.
:::

## What it does

- **List** every recording in your account.
- **Show detail** for a single recording: summary, highlights, and full transcript.
- **Export** a recording to Markdown, JSON, or plain text, and optionally download the audio.
- **Sync** a whole folder: download new and changed recordings, keep a registry so moved or renamed files are not re-downloaded, and gate on content readiness so you never write half-generated notes.
- **Authenticate** with a pasted web token or with email + password, and re-mint the short-lived token automatically for unattended runs.
- **Route by region** automatically: Plaud shards accounts across regional API hosts, and the client follows the region in your token.

## Where to start

- [Installation](/plaud-unofficial-api/getting-started/installation/) — install the package and its dependencies.
- [Authentication](/plaud-unofficial-api/getting-started/authentication/) — log in and keep the token fresh.
- [Configuration](/plaud-unofficial-api/getting-started/configuration/) — the config file and environment variables.
- [`sync`](/plaud-unofficial-api/commands/sync/) — the command most people run on a schedule.
- [Sync readiness](/plaud-unofficial-api/guides/readiness/) — how `--only-ready`, `--ready-requires`, and `--ready-timeout-days` decide when a recording is downloaded.

## Quick start

```bash
pip install -e .
plaud login --email you@example.com          # or: plaud login  (paste a token)
plaud list
plaud sync ./notes --mode two-way --registry --only-ready \
  --include transcript --include summary
```

The source lives at [github.com/giovi321/plaud-unofficial-api](https://github.com/giovi321/plaud-unofficial-api).
