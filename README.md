# Plaud unofficial API

Unofficial command-line tool for [plaud.ai](https://web.plaud.ai/) — reverse-engineered
from the Plaud web app. Download your recordings, transcripts, AI summaries and
highlights, and sync them to a local folder.

<p align="center">
  <a href="https://github.com/giovi321/plaud-unofficial-api/actions/workflows/docs.yml"><img src="https://github.com/giovi321/plaud-unofficial-api/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+">
</p>

<p align="center">
  <a href="https://giovi321.github.io/plaud-unofficial-api/"><img src="https://img.shields.io/badge/Read%20the%20docs-2ea44f?style=for-the-badge&logo=readthedocs&logoColor=white" alt="Read the docs"></a>
</p>

> **Documentation:** full docs are published at <https://giovi321.github.io/plaud-unofficial-api/>.

> **Disclaimer** — This project is **not affiliated with or endorsed by Plaud AI**.
> Use it solely with your own account and in compliance with Plaud's Terms of Service.
>
> It authenticates with the **web token** the Plaud web app uses, not Plaud's
> official OAuth developer platform. Plaud's official API
> (`platform-<region>.plaud.ai/developer/api`, OAuth 2.0, with real refresh
> tokens) is a separate, private-beta product — see
> [How the API works](#how-the-api-works).

---

## Table of contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Authentication](#authentication)
5. [Obtaining your token (paste mode)](#obtaining-your-token)
6. [Configuration](#configuration)
7. [Environment variables](#environment-variables)
8. [Quick start](#quick-start)
9. [Keeping an unattended sync alive](#keeping-an-unattended-sync-alive)
10. [Commands reference](#commands-reference)
    - [Global options](#global-options)
    - [login](#plaud-login)
    - [logout](#plaud-logout)
    - [whoami](#plaud-whoami)
    - [list](#plaud-list)
    - [detail](#plaud-detail-file_id)
    - [export](#plaud-export-file_id)
    - [sync](#plaud-sync-output_dir)
    - [config show](#plaud-config-show)
    - [config init](#plaud-config-init)
    - [config set-api](#plaud-config-set-api-url)
11. [Project structure](#project-structure)
12. [How the API works](#how-the-api-works)
13. [Troubleshooting](#troubleshooting)
14. [Upgrading from 1.x](#upgrading-from-1x)
15. [Changelog](#changelog)
16. [Legal](#legal)
17. [License](#license)

---

## Features

- **Credential login** — `plaud login --email` mints a token via the Plaud web
  login endpoint and (optionally) stores your credentials so the CLI can refresh
  it automatically.
- **Automatic token refresh** — commands re-mint the short-lived token on their
  own when it is missing or about to expire, so **unattended/cron syncs keep
  working** without manual re-login.
- **Env-var credentials** — supply `PLAUD_EMAIL` / `PLAUD_PASSWORD` to keep the
  password out of `config.yaml`.
- **Automatic regional routing** — Plaud shards accounts across per-region API
  hosts; the client auto-discovers and follows the right one (no manual host
  configuration).
- **Token-based auth** — alternatively, paste the JWT the Plaud web app stores in
  `localStorage`; settings live in a human-editable `config.yaml` (no keychain).
- **`--config FILE`** global switch — point any command at an alternative config file.
- **List** all recordings in a formatted table.
- **Detail view** — title, date, duration, AI summary, highlights, full transcript
  with speaker labels.
- **Export** a single recording to Markdown, JSON, or plain text.
- **Folder sync** — one-way (remote → local) or two-way (+ orphan detection), with
  `--dry-run` support.
- **Download registry** — optional `.plaud_registry.json` sidecar tracks what was
  downloaded so moved/renamed files are never re-fetched.
- **`--only-ready` flag** — skip recordings that have no AI-generated content yet
  (no summary or highlights).
- **`--include` flag** — choose exactly which content types to download:
  `transcript`, `summary`, `highlights`, `recording` (repeatable; works on
  `export` and `sync`).
- **Transcript embedded in the export** — when `transcript` is included with
  `--format markdown` (or `txt`/`json`), it is rendered inline as a `## Transcript`
  section in the same file as the summary and highlights.
- **`--json` flag** on most commands for easy scripting and piping.
- **Content hydration** — uses `POST /file/list` to fetch full file details
  including inline transcript data; falls back to signed-URL hydration when needed.

## Requirements

- Python ≥ 3.9
- Dependencies: `httpx`, `click`, `rich`, `pyyaml`, `python-dateutil`
- A Plaud.ai account — either email + password (for credential login) or a web
  token captured from `web.plaud.ai`.

## Installation

```bash
# Clone the repository
git clone https://github.com/giovi321/plaud-unofficial-api.git
cd plaud-unofficial-api

# Install (editable mode recommended for development)
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

After installation the `plaud` command is available in your shell.

> **Tip (WSL / dual-boot):** do not place the virtualenv *inside* a folder shared
> between Windows and Linux (e.g. a Windows drive mounted in WSL). A venv created
> under one OS will not run under the other. Keep `.venv` on a native filesystem.

## Authentication

The CLI supports three ways to authenticate, in increasing order of automation:

### 1. Paste a token

```bash
plaud login                 # prompts (hidden) for the token, then saves it
plaud login --token "eyJ…"  # provide it directly
```

Captures the JWT from the web app (see [Obtaining your token](#obtaining-your-token)).
A pasted token is used as-is and is **not** auto-refreshed — when it expires you
re-capture and re-run `plaud login`. Fine for interactive use; not ideal for cron.

### 2. Credential login (recommended)

```bash
plaud login --email you@example.com        # prompts (hidden) for the password
```

This calls the Plaud web login endpoint (`POST /auth/access-token`), mints a fresh
token, and — unless you pass `--no-save-credentials` — stores your email and
password in `config.yaml` so the token can be re-minted automatically later. A
credential-login token is comparatively long-lived (observed ~30 days).

### 3. Automatic refresh (for unattended use)

Once credentials are available — saved by credential login **or** provided via the
`PLAUD_EMAIL` / `PLAUD_PASSWORD` environment variables — every command that hits the
API checks the stored token first and **transparently re-mints it** when it is
missing or within ~5 minutes of expiry. A still-valid token is reused unchanged
(no extra request). This is what keeps a scheduled `plaud sync` working past the
token's lifetime. See [Keeping an unattended sync alive](#keeping-an-unattended-sync-alive).

> **Notes & limits**
> - Credential login currently supports **email + password** accounts only —
>   **not** Google/Apple SSO or MFA/OTP.
> - With `--save-credentials` (the default) the password is written in **plaintext**
>   to the gitignored `config.yaml`. To avoid that, use `PLAUD_EMAIL` /
>   `PLAUD_PASSWORD` env vars together with `--no-save-credentials`.
> - Passing `--token` explicitly to any command bypasses all refresh logic.
> - This CLI does **not** use refresh tokens. (The login response *does* include a
>   `refresh_token`, but the CLI ignores it and simply re-mints from your
>   credentials.)

### Token lifetimes

The token is a region-scoped JWT; its `exp` claim drives refresh decisions.

| Token source | Observed `exp` lifetime | Notes |
|--------------|-------------------------|-------|
| Credential login (`plaud login --email`, `POST /auth/access-token`) | **~30 days** | Recommended. Response also returns an (unused) `refresh_token`. |
| Browser session token (captured from `localStorage`) | **~24 hours** | Short-lived web-session token; paste with `plaud login`. |
| Legacy tokens (no `region` / `ver` claim) | often **no `exp`** | Treated as long-lived — never proactively refreshed. (Historically observed ~300 days.) |

`token_needs_refresh()` returns `True` when the token is missing or within the skew
window (default 300 s) of `exp`; a token with no `exp` claim is treated as
long-lived and is never proactively refreshed.

## Obtaining your token

If you prefer to paste a token rather than use credential login, capture it from a
logged-in `web.plaud.ai` session. Each token carries a `region: aws:<region>` claim
and the CLI routes to the matching host automatically — see
[How the API works](#how-the-api-works).

**Steps:**

1. Open [web.plaud.ai](https://web.plaud.ai/) and log in. Confirm your recordings load.
2. Open **Developer Tools** (`F12` on Windows/Linux, `Cmd+Opt+I` on macOS) → **Console**.
3. Paste this. It scans the app's stored values, picks the **freshest non-expired**
   access token (skipping profile blobs and stale tokens), and copies it to your clipboard:
   ```js
   copy(Object.values(localStorage)
     .flatMap(v => (v && v.match(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g)) || [])
     .map(t => { try { const p = JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))); return p.exp*1000 > Date.now() ? { t, iat: p.iat || 0 } : null; } catch (e) { return null; } })
     .filter(Boolean).sort((a, b) => b.iat - a.iat)[0]?.t);
   ```
   Your clipboard now holds a `eyJ…` JWT. *(Older app builds also expose it as
   `localStorage.getItem("tokenstr")`. If the one-liner returns nothing, use the
   **Network** tab → any `api-*.plaud.ai` request → `authorization: Bearer …`.)*
4. Load it: `plaud login` and paste at the prompt (or put it in `config.yaml`).

> A browser-captured token is short-lived (~24h) and is **not** auto-refreshed.
> For unattended use, prefer [credential login](#2-credential-login-recommended).

## Configuration

All settings are stored in a single YAML file:

| Platform | Default path |
|----------|-------------|
| Linux / macOS | `~/.config/plaud-cli/config.yaml` |
| Windows | `%USERPROFILE%\.config\plaud-cli\config.yaml` |

> Point any command at a different file with the global `--config FILE` switch
> (see [Global options](#global-options)), or relocate the base directory with the
> `XDG_CONFIG_HOME` environment variable (see [Environment variables](#environment-variables)).

### Config file format

```yaml
api_base: https://api.plaud.ai
token: bearer eyJ...
# Optional — only if you use credential login for automatic token refresh:
email: you@example.com
password: your-plaud-password
```

| Key | Purpose |
|-----|---------|
| `token` | The bearer JWT. Written by `plaud login`; auto-refreshed in place. |
| `api_base` | API host. Defaults to `https://api.plaud.ai` (the discovery host). Usually leave it at the default and let regional routing handle the rest. |
| `email` / `password` | Optional credentials for credential login / auto-refresh. Stored in plaintext; env vars take priority over them. |

### Setting up the config file

**Option A — credential login (recommended):**
```bash
plaud login --email you@example.com
# enter the password when prompted; the token + credentials are saved
```

**Option B — paste a token:**
```bash
plaud login
# You will be prompted to paste your token
```

**Option C — create a starter file and edit manually:**
```bash
plaud config init
# creates config.yaml with a placeholder; edit it and set the token value
```

**Option D — edit directly:** create the file at the path above with the content
shown under [Config file format](#config-file-format).

## Environment variables

| Variable | Effect | Precedence |
|----------|--------|------------|
| `PLAUD_EMAIL` | Account email for credential login / auto-refresh. | Overrides `email` in `config.yaml`. |
| `PLAUD_PASSWORD` | Account password for credential login / auto-refresh. | Overrides `password` in `config.yaml`. |
| `XDG_CONFIG_HOME` | If set, the config directory becomes `$XDG_CONFIG_HOME/plaud-cli`. | Overridden only by `--config FILE`. |

`PLAUD_EMAIL` and `PLAUD_PASSWORD` are resolved independently — you can set just one
via the environment and the other in the file. There is **no** environment override
for `token` or `api_base`.

## Quick start

```bash
# 1. Authenticate (credential login keeps the token self-refreshing)
plaud login --email you@example.com

# 2. Verify it works
plaud whoami

# 3. List all recordings
plaud list

# 4. View full detail for a recording (use an ID from the list)
plaud detail <file_id>

# 5. Export a recording to Markdown
plaud export <file_id> -o my-note.md

# 6. Sync your entire library (one-way, skips already-present files)
plaud sync ./notes/

# 7. Sync with registry + two-way orphan detection
plaud sync ./notes/ --mode two-way --registry

# 8. Use an alternative config file
plaud --config ~/work-plaud.yaml list
```

> For a scheduled, self-refreshing sync, see
> [Keeping an unattended sync alive](#keeping-an-unattended-sync-alive).

## Keeping an unattended sync alive

A scheduled `plaud sync` that runs without manual re-login is the headline use case. It
works because the CLI **re-mints the token automatically** (see
[Authentication → automatic refresh](#3-automatic-refresh-for-unattended-use)) whenever
the token is missing or within ~5 minutes of expiry — as long as credentials are
available. A still-valid token is reused as-is (no extra request).

**1. Make credentials available.** Prefer environment variables so the password never
touches `config.yaml`:

```bash
export PLAUD_EMAIL=you@example.com
export PLAUD_PASSWORD='your-plaud-password'
```

(Or run `plaud login --email you@example.com` once to store them in `config.yaml` —
simpler, but the password is written to disk in plaintext.)

**2. Schedule it.** No explicit `plaud login` is required — the first scheduled run mints
the token itself, and later runs refresh it before it expires.

*Linux/macOS — `crontab -e`, nightly at 03:00. cron does not inherit your shell
environment, so set the variables in the crontab itself:*

```cron
PLAUD_EMAIL=you@example.com
PLAUD_PASSWORD=your-plaud-password
0 3 * * * plaud --config /home/you/.config/plaud-cli/config.yaml sync /home/you/notes >> /home/you/plaud-sync.log 2>&1
```

*Windows — create a Task Scheduler task that runs `plaud sync C:\path\to\notes` on a
daily trigger, with `PLAUD_EMAIL` / `PLAUD_PASSWORD` defined in the task's environment.*

## Commands reference

### Global options

These options are placed **before** the subcommand name and apply to every command:

```
plaud [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--config FILE` | Use this YAML file instead of the default `config.yaml` location. Must precede the subcommand. |
| `--version` | Print the version (`plaud, version 2.0.0`) and exit. |
| `--help` | Show help and exit. |

**Example — use a project-specific config:**
```bash
plaud --config ./project.yaml login --email you@example.com
plaud --config ./project.yaml sync ./notes/
```

### `plaud login`

```
plaud login [--token TEXT]
plaud login --email EMAIL [--password PW] [--no-save-credentials]
```

Two modes (see [Authentication](#authentication) for the full picture):

- **Paste a token** (default) — prompts (hidden) for the token and saves it. Not
  auto-refreshed.
- **Credential login** (`--email`) — calls `POST /auth/access-token`, mints a token,
  and (unless `--no-save-credentials`) stores email + password so the CLI can
  re-mint the token automatically before each command.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | — | Bearer token to store (paste mode). |
| `--email EMAIL` | — | Account email; enables credential login. |
| `--password PW` | prompt | Account password; omit to be prompted securely. |
| `--save-credentials / --no-save-credentials` | save | Store email+password in `config.yaml` for auto-refresh. Use `--no-save-credentials` with env-var credentials. |

```bash
# paste-based
plaud login
# Plaud token: <paste here>

# credential login (prompts for the password)
plaud login --email you@example.com

# env-var credentials — don't write the password to disk
export PLAUD_EMAIL=you@example.com PLAUD_PASSWORD='…'
plaud login --email "$PLAUD_EMAIL" --password "$PLAUD_PASSWORD" --no-save-credentials
```

### `plaud logout`

```
plaud logout
```

Removes the `token` field from `config.yaml`. **Stored credentials
(`email`/`password`) are left in place** — delete them by editing the file if you
want to fully de-authenticate.

### `plaud whoami`

```
plaud whoami
```

Validates the active token (refreshing it first if credentials are available) by
calling the API, and prints how many recordings are in the account. It also accepts a
hidden `--token TEXT` to validate a specific token without storing it.

```
Token is valid. Account has 42 recording(s).
```

### `plaud list`

```
plaud list [OPTIONS]
```

Lists all recordings in a rich table showing ID, date, duration and title.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token (skips auto-refresh). |
| `--json` | off | Print raw JSON array instead of a table. |
| `--no-trash / --trash` | hide | Trashed recordings are hidden by default; pass `--trash` to include them. |
| `--limit N` | 0 (all) | Cap the number of results returned. |

**Example output:**

```
 #   ID                  Date                 Duration   Title / File Name
 1   abc123def456        2024-11-03 09:12 UTC   4m 32s   Team standup
 2   xyz789ghi012        2024-11-01 14:05 UTC  12m 08s   Product review
```

### `plaud detail <FILE_ID>`

```
plaud detail [OPTIONS] FILE_ID
```

Fetches and displays full information for a single recording.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token. |
| `--json` | off | Print raw JSON payload. |
| `--hydrate / --no-hydrate` | hydrate | Fetch full transcript/summary (POST /file/list → signed URLs). |

**What is shown:** recording ID and file ID, date and duration, AI-generated
summary, key highlights (bullet list), and the full transcript with speaker labels
(each section only when present).

### `plaud export <FILE_ID>`

```
plaud export [OPTIONS] FILE_ID
```

Exports a single recording to a file or stdout.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token. |
| `--format` | `markdown` | Output format for the included text content: `markdown`, `json`, or `txt`. |
| `-o / --output PATH` | stdout | Output file path (base name). |
| `--hydrate / --no-hydrate` | hydrate | Fetch full transcript/summary (POST /file/list → signed URLs). |
| `--include TYPE` | text types | Content to include. Repeatable. Choices: `transcript`, `summary`, `highlights`, `recording`. Defaults to `transcript`, `summary`, `highlights`. |

Included text content (`summary`, `highlights`, and `transcript`) is rendered into a
single file in the chosen `--format`. When `recording` is included, the audio file is
downloaded too and saved with the same base name and an audio extension (`.ogg`,
`.mp3`, `.wav`, `.m4a`); a recording-download failure is non-fatal (a yellow warning).
With no `-o`, text output is echoed to stdout.

**Examples:**

```bash
# Export summary + highlights + transcript to Markdown
plaud export abc123 -o standup-2024-11-03.md
# → standup-2024-11-03.md  (summary, highlights, transcript inline)

# Export as JSON to stdout (useful for piping)
plaud export abc123 --format json | jq '.summary'

# Export only the transcript (plain text to stdout)
plaud export abc123 --include transcript

# Export only summary + highlights (no transcript)
plaud export abc123 --include summary --include highlights

# Export everything including the audio recording
plaud export abc123 --include transcript --include summary --include highlights --include recording -o note.md
# → note.md  (summary, highlights, transcript)  +  note.ogg

# Export only the recording file
plaud export abc123 --include recording
```

**Markdown output format:**

```markdown
---
file_id: abc123def456
date: 2024-11-03 09:12 UTC
duration: 4m 32s
---

# Team standup

## Summary
...

## Highlights
- Point one
- Point two

## Transcript
Speaker 1: ...
Speaker 2: ...
```

### `plaud sync <OUTPUT_DIR>`

```
plaud sync [OPTIONS] OUTPUT_DIR
```

Synchronises a local folder with your Plaud recordings. Each recording is saved as a
separate file named `YYYY-MM-DD_<title>.<ext>`.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token. |
| `--mode` | `one-way` | Sync mode — see below. |
| `--format` | `markdown` | Output format for the included text content: `markdown`, `json`, or `txt`. |
| `--no-trash / --trash` | hide | Trashed recordings are skipped by default; pass `--trash` to include them. |
| `--hydrate / --no-hydrate` | hydrate | Fetch full transcript/summary (POST /file/list → signed URLs). |
| `--since DATE` | (all) | Only sync recordings newer than this ISO-8601 date. |
| `--registry / --no-registry` | off | Enable the download registry (see below). |
| `--dry-run` | off | Print what would be downloaded without writing anything. |
| `--only-ready` | off | Skip a recording until **every requested `--include` text type** is present (e.g. both summary and transcript). Prevents summary-less or empty notes. |
| `--ready-timeout-days N` | `0` | With `--only-ready`: once a recording is older than `N` days, sync it anyway with whatever content is available (and record it as incomplete so it heals later). `0` = wait forever. |
| `--include TYPE` | text types | Content to include. Repeatable. Choices: `transcript`, `summary`, `highlights`, `recording`. Defaults to `transcript`, `summary`, `highlights`. |

When `recording` is included, the audio file for each recording is downloaded into the
same output directory (failures are non-fatal). Per-recording errors are counted and
reported; the run then **exits `2`** (partial failure) so schedulers notice, while
still writing every recording that did succeed. The run ends with a
`Done. N downloaded, …` summary line.

> **Readiness and healing.** With `--only-ready`, a recording is written only once
> all requested sections exist. If it is forced through by `--ready-timeout-days`
> (or a section disappears server-side), the registry marks it `complete: false`
> and later runs re-fetch and rewrite it until it is whole. Re-fetches keep the
> original filename even if the recording was re-titled on Plaud, so downstream
> mirrors never get a duplicate.

#### Sync modes

**`--mode one-way`** *(default)* — downloads recordings that are not yet present
locally. A recording is considered present if its `file_id` already appears in the
registry (`--registry`), or a file with the expected name already exists in the output
directory (when `--no-registry`). Nothing is ever deleted locally.

**`--mode two-way`** — same download behaviour, but additionally checks the registry
for local files whose recording has since been **deleted from the remote**. Those are
reported as orphans; **no local files are deleted automatically** — you decide.

> Two-way orphan detection requires `--registry`. Without a registry there is no
> reliable way to map local filenames back to remote `file_id`s.

#### Download registry

With `--registry`, `sync` maintains a hidden `.plaud_registry.json` inside the output
directory, recording the `file_id`, local filename, and download timestamp of every
file written:

```json
{
  "abc123def456": {
    "filename": "2024-11-03_Team standup.md",
    "downloaded_at": "2024-11-04T08:00:00Z",
    "sections": ["summary", "transcript"],
    "complete": true
  }
}
```

Because the lookup is by `file_id`, files can be freely **renamed or moved** inside the
output directory without triggering a re-download. `sections` lists the content types
present at download time and `complete` is `false` while any requested section is still
missing — those entries are re-fetched on later runs until they are whole (see
*Readiness and healing* above). The file is written atomically and, if it is ever found
corrupt, preserved as `.plaud_registry.json.corrupt-<timestamp>` rather than silently
discarded.

**Examples:**

```bash
# Basic one-way sync (name-based duplicate check)
plaud sync ./notes/

# One-way sync with registry (handles renames)
plaud sync ./notes/ --registry

# Two-way sync — also warn about recordings deleted from remote
plaud sync ./notes/ --mode two-way --registry

# Preview what would be downloaded without writing anything
plaud sync ./notes/ --dry-run
plaud sync ./notes/ --mode two-way --registry --dry-run

# Sync only recordings from 2024 onwards as plain text
plaud sync ./archive/ --format txt --since 2024-01-01

# Sync as JSON (useful for further processing)
plaud sync ./json-export/ --format json --registry

# Only sync recordings whose AI content is ready
plaud sync ./notes/ --only-ready

# Sync only transcripts
plaud sync ./notes/ --include transcript

# Sync summary + transcript together in one Markdown file
plaud sync ./notes/ --include summary --include transcript
# → 2024-11-03_Meeting.md  (summary + transcript inline)

# Sync transcripts and audio recordings
plaud sync ./notes/ --include transcript --include recording

# Sync everything including audio files
plaud sync ./notes/ --include transcript --include summary --include highlights --include recording

# Combine with other options
plaud sync ./notes/ --only-ready --registry --mode two-way --dry-run
```

### `plaud config show`

```
plaud config show
```

Prints the config file path, the API base URL, and a **truncated preview** of the
stored token (never the full token). Stored `email` / `password` credentials are **not**
displayed (inspect the file directly if you need to confirm them).

```
config file: /home/you/.config/plaud-cli/config.yaml
api_base:    https://api.plaud.ai
token:       bearer eyJhb… (use 'plaud logout' to remove)
```

### `plaud config init`

```
plaud config init [--force]
```

Creates a starter `config.yaml` with a `token` placeholder and the default
`api_base`. Pass `--force` to overwrite an existing file.

```yaml
api_base: https://api.plaud.ai
token: bearer eyJ...
```

### `plaud config set-api <URL>`

```
plaud config set-api <URL>
```

Overrides the API base URL saved in `config.yaml`. Useful for pinning a specific
regional host, local testing, or if Plaud changes their API domain.

```bash
# Pin a specific regional host (skips the region-discovery redirect)
plaud config set-api https://api-euc1.plaud.ai

# Reset to the discovery host to re-enable automatic region routing
plaud config set-api https://api.plaud.ai
```

By default (discovery host) the client auto-detects your account's region from the
token and follows any redirect the API issues — see [How the API works](#how-the-api-works).
An explicit override set here always wins.

## Project structure

```
plaud-unofficial-api/
├── src/
│   └── plaud_cli/
│       ├── __init__.py
│       ├── cli.py          # Click command definitions, auto-refresh wiring
│       ├── api.py          # HTTP client, region routing, login, content hydration
│       ├── normalizer.py   # Raw API payload → consistent Python dict
│       └── config.py       # YAML config + credential storage
├── tests/                  # pytest suite (httpx MockTransport + CliRunner)
├── pyproject.toml          # Package metadata and entry point
├── requirements.txt        # Pinned dependencies
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## How the API works

Plaud exposes an undocumented REST API. All requests are authenticated with a
`Bearer` token in the `Authorization` header.

### Regional routing

Plaud shards accounts across dedicated regional API hosts. `api.plaud.ai` is a
**discovery** host that rejects region-pinned tokens with
`status: -302` / `msg: "user region mismatch"` and returns the correct host. The
region is encoded in the token's `region` claim and mapped to a host:

| `region` claim | API host | | `region` claim | API host |
|----------------|----------|---|----------------|----------|
| `aws:eu-central-1` | `api-euc1.plaud.ai` | | `aws:us-west-1` | `api-usw1.plaud.ai` |
| `aws:eu-west-1` | `api-euw1.plaud.ai` | | `aws:us-west-2` | `api-usw2.plaud.ai` |
| `aws:us-east-1` | `api-use1.plaud.ai` | | `aws:ap-southeast-1` | `api-apse1.plaud.ai` |
| `aws:us-east-2` | `api-use2.plaud.ai` | | `aws:ap-southeast-2` | `api-apse2.plaud.ai` |
| `aws:ap-northeast-1` | `api-apne1.plaud.ai` | | `aws:ap-south-1` | `api-aps1.plaud.ai` |

The client handles this automatically:

1. On startup, **only if `api_base` is left at the default discovery host**, it reads
   the `region` claim from your token and routes to the matching regional host. An
   explicit `plaud config set-api` override is always respected.
2. If a request still hits a `-302`, it follows the host the API returns in
   `data.domains.api` and retries **once**. The server's host is authoritative and
   wins over the token's region claim, which can be **stale** after an account
   migration (e.g. a token issued as `aws:us-west-2` whose data now lives in
   `aws:eu-central-1`). Only `*.plaud.ai` hosts are accepted as redirect targets; if
   the body omits a host it falls back to the token's region claim.

### Data endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/file/simple/web` | `GET` | List all recordings (summary objects). |
| `/file/list` | `POST` | Full detail for one or more recordings (body: `["file_id"]`). Returns `trans_result` and `ai_content` inline. |
| `/file/detail/{id}` | `GET` | Full detail for one recording (may omit transcript). |
| `content_list[].data_link` | `GET` | Signed URL for transcript, AI summary, or recording. |

**Response envelope:** the API wraps responses in different shapes depending on the
endpoint. `api.py` normalises all variants, looking for the payload under `payload`,
`data`, `data_file_list`, or at the root; `status` of `0`/`200`/`ok`/`success` is a
success.

**Content hydration:** the client first tries `POST /file/list`, which returns
transcript data (`trans_result`) inline as speaker-labelled segments. If that fails or
returns incomplete data, it falls back to `GET /file/detail/{id}` and fetches
transcript/summary from signed URLs in the `content_list` array.

### Authentication endpoints

The bearer token is minted by the web app's own (undocumented) auth endpoints, on the
**regional** host (they follow the same `-302` redirect as the data endpoints):

| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/auth/access-token` | `POST` | form-encoded `username` (the email) + `password` | `{access_token, refresh_token, token_type, …}` |
| `/auth/otp-send-code` | `POST` | JSON `{username, user_area}` | `{token}` |
| `/auth/otp-login` | `POST` | JSON `{code, token, user_area}` | `{access_token, token_type}` |

This CLI implements only the **email + password** flow (`/auth/access-token`). Two
non-obvious details:

- The login request must be sent with a **minimal** header set. Sending the full
  browser-fingerprint headers the data endpoints use makes the login endpoint return a
  *success envelope with an empty `access_token`* (a stub). The client therefore sends
  only `Content-Type`, `Accept`, `Origin`, and `Referer` for login.
- The response carries a `refresh_token`, but the CLI **ignores** it and re-mints from
  your stored credentials instead.

Plaud's **official, supported** API is different: an OAuth 2.0 client-credentials
surface at `platform-<region>.plaud.ai/developer/api` (with real refresh tokens),
currently in private beta — see the
[developer platform](https://www.plaud.ai/pages/developer-platform). It is unrelated
to the web token this CLI uses.

## Troubleshooting

### `invalid_response: user region mismatch`

Plaud shards accounts across regional API hosts and migrates accounts between them
(their "Service Region Adjustment"). When the host you contact doesn't hold your
account's data, the API replies with `status: -302` / `msg: "user region mismatch"`
and the correct host in `data.domains.api`.

The client handles this automatically: it routes by the token's region claim on startup
and follows the server's redirect (capped at one hop, `*.plaud.ai` only). If you still
see this error, find your real host — the server tells you directly:

```bash
TOKEN=$(grep -i '^token:' ~/.config/plaud-cli/config.yaml \
  | sed -E 's/^token:[[:space:]]*(bearer[[:space:]]+)?//I' | tr -d '"')
curl -s https://api.plaud.ai/file/simple/web \
  -H "Authorization: Bearer $TOKEN" | grep -o '"api":"[^"]*"'
# → "api":"https://api-euc1.plaud.ai"
```

Then pin it if you want to skip the redirect hop:
`plaud config set-api https://api-euc1.plaud.ai`.

> **Note:** the `region` claim inside your token is the region it was *issued* in and
> can be **stale** after a migration. The host in the `-302` body is authoritative —
> the client always prefers it over the token claim. Logging in again at `web.plaud.ai`
> (or via `plaud login --email`) refreshes the claim to your current region.

### `auth: HTTP 401` / `token invalid or expired`

The (correct) regional host is rejecting your token. Two causes:

- **Expired token** — browser session tokens last only ~24h. Decode the `exp` claim to check:
  ```bash
  T=$(grep -i '^token:' ~/.config/plaud-cli/config.yaml | sed -E 's/^token:[[:space:]]*(bearer[[:space:]]+)?//I' | tr -d '"')
  python3 -c "import sys,base64,json,time;p=sys.argv[1].split('.')[1];p+='='*(-len(p)%4);d=json.loads(base64.urlsafe_b64decode(p));print('region',d.get('region'),'| exp',time.strftime('%F %T',time.localtime(d['exp'])),'->','EXPIRED' if d['exp']<time.time() else 'valid')" "$T"
  ```
- **Cross-region token** — a still-valid token whose `region` no longer matches where
  your data lives (e.g. an old `us-west-2` token after your account moved to
  `eu-central-1`). The discovery host issues a `-302` (followed automatically), but the
  destination host then refuses the foreign token with `401`.

Fix either by capturing a fresh token, or — better — by switching to
[credential login](#2-credential-login-recommended) so the token auto-refreshes.

### `Login failed (auth): Login response had no access_token`

The login endpoint returned a success envelope with an empty token. Causes:

- The request reached a host/path that doesn't mint tokens for your account (the client
  routes login through the discovery host to avoid this). Re-run `plaud login --email`.
- Your account uses **SSO or MFA**, which the email+password flow does not support —
  capture a token manually instead (see [Obtaining your token](#obtaining-your-token)).
- A transient server-side stub — retry.

### `Auto-login failed (...)`

Shown when auto-refresh is needed but fails and there is no usable existing token
(the command then exits non-zero). Check that `PLAUD_EMAIL` / `PLAUD_PASSWORD` (or the
`email` / `password` config fields) are correct, and that the account is email+password
(not SSO/MFA).

### Common error categories

Errors are printed as `category: message` (and the command exits non-zero, except where
noted). The categories:

| Category | Meaning |
|----------|---------|
| `network` | Connectivity/transport failure, or an unclassified non-2xx HTTP response. |
| `auth` | Authentication failure — bad/expired token (HTTP 401/403) or a login that returned no token. |
| `rate_limit` | HTTP 429 — too many requests; back off and retry. |
| `server` | HTTP 5xx — a Plaud server-side error. |
| `invalid_response` | A malformed or non-success response envelope. |
| `not_found` | The requested recording (or its download link) does not exist. |

> Recording-download failures during `export`/`sync` are **non-fatal** — they print a
> yellow warning and the run continues.

## Upgrading from 1.x

v2.0.0 makes Plaud's regional sharding and short-lived v2 tokens first-class. If you
are coming from 1.x:

- **Stale tokens may need re-capturing.** A token captured before the regional
  migration can be rejected by your account's current region. The client now routes by
  the token's `region` claim and follows `-302` redirects automatically, but if your
  stored token predates the migration, re-authenticate.
- **Unattended/cron syncs must switch to credential login.** Older long-lived tokens
  could sit in `config.yaml` for months; current v2 tokens expire (browser ~24h,
  credential-login ~30 days). Run `plaud login --email …`, or set `PLAUD_EMAIL` /
  `PLAUD_PASSWORD`, so the token auto-refreshes. Pasted tokens are **not** refreshed.
- **New optional config fields.** `config.yaml` may now contain `email` and `password`
  (written by credential login); env vars `PLAUD_EMAIL` / `PLAUD_PASSWORD` override them.
- **No behavioural change to exports.** Transcript still renders inline (`## Transcript`)
  in the formatted file when included; the in-code help text was corrected to match.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full history. Highlights:

- **2.0.0** — credential login (`plaud login --email`) + automatic token refresh;
  env-var credentials (`PLAUD_EMAIL` / `PLAUD_PASSWORD`); minimal-header login fix;
  accurate v2 token-lifetime handling; documentation overhaul; repo hygiene.
- **1.6.0–1.6.1** — automatic regional routing and `-302` redirect handling; stopped
  tracking compiled bytecode.
- **1.5.0–1.5.1** — granular `--include` content selection; `POST /file/list` inline
  transcript retrieval; browser-like request headers.

## Legal

This tool is provided for **personal interoperability** purposes only — enabling users
to access their own data in ways the official app does not expose. The author is not
affiliated with Plaud AI.

Reverse-engineering for interoperability is expressly permitted under:
- **EU Directive 2009/24/EC**, Article 6 (Software Directive)
- **17 U.S.C. § 107** (fair use) for personal/interoperability use cases
- Equivalent provisions in other jurisdictions

## License

MIT License

Copyright (c) 2026 plaud-cli contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
