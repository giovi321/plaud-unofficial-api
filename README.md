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
  <a href="https://giovi321.github.io/plaud-unofficial-api/"><strong>Full documentation</strong></a>
</p>

> **Not affiliated with or endorsed by Plaud AI.** Reverse-engineered from the
> [web app](https://web.plaud.ai/); authenticates with the same web token
> `web.plaud.ai` uses, not Plaud's official OAuth developer platform. See [Legal](#legal).

If your Plaud recordings, transcripts, and AI summaries only live inside the browser
tab at `web.plaud.ai`, this gets them out. `plaud-cli` logs in the way the web app
does, lists what's in your account, and exports or syncs it to a local folder — one
command, or a scheduled job that keeps running unattended.

## Quick start

```bash
git clone https://github.com/giovi321/plaud-unofficial-api.git
cd plaud-unofficial-api
pip install -e .

plaud login --email you@example.com   # mints a token, saves credentials for auto-refresh
plaud list                            # see what's in your account
plaud export <file_id> -o note.md     # summary + highlights + transcript, one file
plaud sync ./notes/ --registry        # or sync the whole library to a folder
```

Needs Python ≥ 3.9 and a Plaud.ai account — email + password, or a web token pasted
from `localStorage`. See
[Installation](https://giovi321.github.io/plaud-unofficial-api/getting-started/installation/)
and
[Authentication](https://giovi321.github.io/plaud-unofficial-api/getting-started/authentication/).

## What it does

- Lists every recording in a table, or shows full detail for one: summary,
  highlights, and the full transcript with speaker labels.
- Exports a recording — or syncs your whole library — to Markdown, JSON, or plain
  text, with the transcript rendered inline alongside the summary.
- `--include` picks exactly which content to fetch (`transcript`, `summary`,
  `highlights`, `recording`), so you can pull just the audio, or just the text.
- One-way or two-way folder sync, with `--dry-run`, an optional download registry
  that survives renames, and `--only-ready` to skip notes until their AI summary
  actually exists (with a timeout so nothing waits forever).
- Handles Plaud's regional API sharding and short-lived tokens automatically —
  routing, redirects, and refresh all happen without you noticing. Transient network
  failures are retried rather than aborting a run. Full mechanics in
  [How the API works](https://giovi321.github.io/plaud-unofficial-api/guides/how-it-works/).

## Authentication

Three ways to log in, in increasing order of automation:

- **Paste a token** — capture the JWT from a logged-in browser session and
  `plaud login`. Simple, but not auto-refreshed (~24h lifetime).
- **Credential login** (recommended) — `plaud login --email you@example.com` mints
  a token via Plaud's own login endpoint and saves it for reuse (~30 days).
- **Automatic refresh** — once credentials are saved (or set via `PLAUD_EMAIL` /
  `PLAUD_PASSWORD`), every command re-mints the token on its own before it expires.
  This is what keeps a scheduled `plaud sync` running unattended.

Full method-by-method detail, token lifetimes, and limits (email+password accounts
only, no SSO/MFA):
[Authentication](https://giovi321.github.io/plaud-unofficial-api/getting-started/authentication/).
For scheduling, including the wrapper mistakes that make a healthy sync look broken:
[Keeping an unattended sync alive](https://giovi321.github.io/plaud-unofficial-api/guides/unattended-sync/).

## Configuration

Settings live in one YAML file — `~/.config/plaud-cli/config.yaml` (Linux/macOS) or
`%USERPROFILE%\.config\plaud-cli\config.yaml` (Windows), overridable with
`--config FILE` or `XDG_CONFIG_HOME`. Full format, env vars, and setup options:
[Configuration](https://giovi321.github.io/plaud-unofficial-api/getting-started/configuration/).

## Commands

| Command | Does | Reference |
|---------|------|-----------|
| `plaud login` / `logout` / `whoami` | Authenticate, clear, or check the stored token. | [Authentication](https://giovi321.github.io/plaud-unofficial-api/getting-started/authentication/) |
| `plaud list` | Table of all recordings. | [list](https://giovi321.github.io/plaud-unofficial-api/commands/list/) |
| `plaud detail <file_id>` | Full detail for one recording. | [detail](https://giovi321.github.io/plaud-unofficial-api/commands/detail/) |
| `plaud export <file_id>` | Export one recording to Markdown, JSON, or text. | [export](https://giovi321.github.io/plaud-unofficial-api/commands/export/) |
| `plaud sync <dir>` | One-way or two-way sync of a local folder. | [sync](https://giovi321.github.io/plaud-unofficial-api/commands/sync/) |
| `plaud config show` / `init` / `set-api` | Inspect or bootstrap `config.yaml`. | [Configuration](https://giovi321.github.io/plaud-unofficial-api/getting-started/configuration/) |

## Tech

| Component | Technology |
|-----------|------------|
| Language | Python ≥ 3.9 |
| CLI framework | Click |
| HTTP client | httpx |
| Output / config | Rich (tables), PyYAML (`config.yaml`) |
| Tests | pytest, `httpx.MockTransport` + Click's `CliRunner` |

## Legal

This tool is provided for **personal interoperability** — accessing your own data in
ways the official app doesn't expose — not as a general-purpose Plaud API client.
Reverse-engineering for interoperability is permitted under EU Directive 2009/24/EC
Art. 6, 17 U.S.C. § 107 (fair use), and equivalent provisions elsewhere. Use it only
with your own account and in compliance with Plaud's Terms of Service. See
[How the API works](https://giovi321.github.io/plaud-unofficial-api/guides/how-it-works/)
for what it actually talks to.

## Development

```bash
pip install -e ".[dev]"
pytest
```

A single Python package under `src/plaud_cli/`, tested with a mocked API — no network
or real account needed. Layout and conventions:
[Contributing](https://giovi321.github.io/plaud-unofficial-api/development/contributing/).

Coming from 1.x? See
[Upgrading](https://giovi321.github.io/plaud-unofficial-api/getting-started/upgrading/).
Hitting an error? See
[Troubleshooting](https://giovi321.github.io/plaud-unofficial-api/guides/troubleshooting/).
Full history in [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [MIT License](LICENSE).
