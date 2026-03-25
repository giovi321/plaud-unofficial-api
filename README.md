# Plaud unofficial API

Unofficial command-line tool for [plaud.ai](https://web.plaud.ai/) — reverse-engineered from the Plaud web app.



> **Disclaimer** – This project is not affiliated with or endorsed by Plaud AI.
> Use it solely with your own account and in compliance with Plaud's Terms of Service.

---

## Table of contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Obtaining your token](#obtaining-your-token)
5. [Configuration](#configuration)
6. [Quick start](#quick-start)
7. [Commands reference](#commands-reference)
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
8. [Project structure](#project-structure)
9. [How the API works](#how-the-api-works)
10. [Legal](#legal)
11. [License](#license)

---

## Features

- **Token-based auth** — uses the long-lived JWT stored in `localStorage` on `web.plaud.ai`
- **YAML config file** — token and settings live in a human-editable `config.yaml`; no keychain required
- **`--config FILE`** global switch — point any command at an alternative config file
- **List** all recordings in a formatted table
- **Detail view** — title, date, duration, AI summary, highlights, full transcript with speaker labels
- **Export** a single recording to Markdown, JSON, or plain text
- **Folder sync** — one-way (remote → local) or two-way (+ orphan detection) with `--dry-run` support
- **Download registry** — optional `.plaud_registry.json` sidecar tracks what was downloaded so moved/renamed files are never re-fetched
- **`--only-ready` flag** — skip recordings that have no AI-generated content yet (no summary, highlights, or transcript)
- **`--include` flag** — choose exactly which content types to download: `transcript`, `summary`, `highlights`, `recording` (repeatable, works on `export` and `sync`)
- **Transcript embedded in Markdown** — when `--include transcript` is used with `--format markdown`, the transcript is included as a `## Transcript` section in the `.md` file (same for `txt` and `json`)
- **`--json` flag** on most commands for easy scripting and piping
- **Content hydration** — uses `POST /file/list` to fetch full file details including inline transcript data; falls back to signed-URL hydration when needed


## Requirements

- Python ≥ 3.9
- Dependencies: `httpx`, `click`, `rich`, `pyyaml`, `python-dateutil`


## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/plaud-unofficial-api.git
cd plaud-unofficial-api

# Install (editable mode recommended for development)
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

After installation the `plaud` command is available in your shell.

## Obtaining your token

Plaud has no official API or developer portal. Authentication relies on the
long-lived JWT that the Plaud web app stores in `localStorage`.

**Steps:**

1. Open [web.plaud.ai](https://web.plaud.ai/) and log in with your account.
2. Open the browser **Developer Tools** (`F12` on Windows/Linux, `Cmd+Opt+I` on macOS).
3. Go to the **Console** tab and run:
   ```js
   localStorage.getItem("tokenstr")
   ```
4. Copy the full string returned. It starts with `bearer eyJ…`.

> The token is long-lived (approximately 10 months) but will eventually expire.
> When it does, repeat these steps and update your `config.yaml` or run `plaud login` again.

## Configuration

All settings are stored in a single YAML file:

| Platform | Default path |
|----------|-------------|
| Linux / macOS | `~/.config/plaud-cli/config.yaml` |
| Windows | `%USERPROFILE%\.config\plaud-cli\config.yaml` |

> You can point any command at a different file using the global `--config FILE` switch
> (see [Global options](#global-options)), or override the base directory with the
> `XDG_CONFIG_HOME` environment variable.

### Config file format

```yaml
api_base: https://api.plaud.ai
token: bearer eyJ...
```

### Setting up the config file

**Option A — interactive login:**
```bash
plaud login
# You will be prompted to paste your token
```

**Option B — create a starter file and edit manually:**
```bash
plaud config init
# Opens ~/.config/plaud-cli/config.yaml with a placeholder token
# Edit the file and replace the token value with your JWT
```

**Option C — edit directly:**

Create `~/.config/plaud-cli/config.yaml` with the content shown above and
paste your token as the `token` value.

## Quick start

```bash
# 1. Create the config file and set your token
plaud config init          # creates config.yaml with a placeholder
#    then edit the file and replace the token value

# 2. Verify the token works
plaud whoami

# 3. List all recordings
plaud list

# 4. View full detail for a recording (use the ID from the list)
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

## Commands reference

### Global options

These options are placed **before** the subcommand name and apply to every command:

```
plaud [OPTIONS] COMMAND [ARGS]...
```

| Option | Description |
|--------|-------------|
| `--config FILE` | Use this YAML file instead of the default `config.yaml` location. The file is created by `config init` or `login` if it does not exist yet. |
| `--version` | Print the version and exit. |
| `--help` | Show help and exit. |

**Example — use a project-specific config:**
```bash
plaud --config ./project.yaml login
plaud --config ./project.yaml sync ./notes/
```

### `plaud login`

```
plaud login [--token TEXT]
```

Prompts for your Plaud token and saves it to `config.yaml`.
Pass `--token` to provide it directly without the prompt.

```bash
plaud login
# Plaud token: <paste here>
```

### `plaud logout`

```
plaud logout
```

Removes the `token` field from `config.yaml`.

### `plaud whoami`

```
plaud whoami [--token TEXT]
```

Validates the stored token by calling the API and prints how many recordings
are in the account.

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
| `--token TEXT` | config | Override stored token |
| `--json` | off | Print raw JSON array instead of a table |
| `--no-trash` | on | Hide trashed recordings |
| `--limit N` | 0 (all) | Cap the number of results returned |

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
| `--token TEXT` | config | Override stored token |
| `--json` | off | Print raw JSON payload |
| `--hydrate / --no-hydrate` | hydrate | Fetch transcript/summary from signed URLs |

**What is shown:**
- Recording ID and file ID
- Date and duration
- AI-generated summary
- Key highlights (bullet list)
- Full transcript with speaker labels

### `plaud export <FILE_ID>`

```
plaud export [OPTIONS] FILE_ID
```

Exports a single recording to a file or stdout.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token |
| `--format` | `markdown` | Output format: `markdown`, `json`, or `txt`. Applies to all included content types (summary, highlights, transcript). |
| `-o / --output PATH` | stdout | Output file path (base name). |
| `--hydrate / --no-hydrate` | hydrate | Fetch transcript/summary from the API |
| `--include TYPE` | all text | Content to include. Repeatable. Choices: `transcript`, `summary`, `highlights`, `recording`. Defaults to all text types. |

When `--include recording` is specified, the audio file is downloaded alongside
the text export. The recording is saved with the same base name but an audio
extension (`.ogg`, `.mp3`, `.wav`, `.m4a`).

**Examples:**

```bash
# Export summary + highlights + transcript to Markdown
plaud export abc123 -o standup-2024-11-03.md
# → standup-2024-11-03.md  (summary, highlights, transcript in Markdown)

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

Synchronises a local folder with your Plaud recordings. Each recording is
saved as a separate file named `YYYY-MM-DD_<title>.<ext>`.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token |
| `--mode` | `one-way` | Sync mode — see below |
| `--format` | `markdown` | Output format: `markdown`, `json`, or `txt`. Applies to all included content types. |
| `--no-trash` | on | Skip trashed recordings |
| `--hydrate / --no-hydrate` | hydrate | Fetch transcript/summary from signed URLs |
| `--since DATE` | (all) | Only sync recordings newer than this ISO-8601 date |
| `--registry / --no-registry` | off | Enable the download registry (see below) |
| `--dry-run` | off | Print what would be downloaded without writing anything |
| `--only-ready` | off | Skip recordings that have no AI-generated content yet (no summary, highlights, or transcript) |
| `--include TYPE` | all text | Content to include. Repeatable. Choices: `transcript`, `summary`, `highlights`, `recording`. Defaults to all text types. |

When `--include recording` is specified, the audio file for each recording is
downloaded alongside the text export into the same output directory.

#### Sync modes

**`--mode one-way`** *(default)*

Downloads recordings that are not yet present locally. A recording is
considered present if:
- its `file_id` already appears in the registry (`--registry`), **or**
- a file with the expected name already exists in the output directory
  (when `--no-registry`).

Nothing is ever deleted locally.

**`--mode two-way`**

Same download behaviour as `one-way`, but additionally checks the registry
for local files whose recording has since been **deleted from the remote**.
Those files are reported as orphans — no local files are deleted
automatically; you decide what to do with them.

> Two-way orphan detection requires `--registry` to be enabled.
> Without a registry there is no reliable way to map local filenames back
> to remote `file_id`s.

#### Download registry

When `--registry` is enabled, `sync` maintains a hidden JSON file
(`.plaud_registry.json`) inside the output directory. It records the
`file_id`, local filename, and download timestamp for every file that has
been written.

```json
{
  "abc123def456": {
    "filename": "2024-11-03_Team standup.md",
    "downloaded_at": "2024-11-04T08:00:00Z"
  }
}
```

Because the lookup is by `file_id`, the file can be freely **renamed or
moved** inside the output directory without triggering a re-download.

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

# Only sync recordings that have AI-generated content
plaud sync ./notes/ --only-ready

# Sync only transcripts
plaud sync ./notes/ --include transcript

# Sync summary + transcript together in one Markdown file
plaud sync ./notes/ --include summary --include transcript
# → 2024-11-03_Meeting.md  (summary + transcript in Markdown)

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

Prints the current configuration including the path to `config.yaml`, the
API base URL, and a preview of the stored token.

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
`api_base`. Use this as the starting point for manual token setup.

```yaml
api_base: https://api.plaud.ai
token: bearer eyJ...
```

Pass `--force` to overwrite an existing config file.

### `plaud config set-api <URL>`

```
plaud config set-api <URL>
```

Overrides the API base URL saved in `config.yaml`.
Useful if Plaud changes their API domain or for local testing.

```bash
plaud config set-api https://api.plaud.ai
```

## Project structure

```
plaud-unofficial-api/
├── src/
│   └── plaud_cli/
│       ├── __init__.py
│       ├── cli.py          # Click command definitions
│       ├── api.py          # HTTP client, endpoint calls, content hydration
│       ├── normalizer.py   # Raw API payload → consistent Python dict
│       └── config.py       # YAML config read/write, token storage
├── pyproject.toml          # Package metadata and entry point
├── requirements.txt        # Pinned dependencies
├── LICENSE
└── README.md
```

## How the API works

Plaud exposes an undocumented REST API at `https://api.plaud.ai`. All requests
are authenticated with a `Bearer` token in the `Authorization` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/file/simple/web` | `GET` | List all recordings (summary objects) |
| `/file/list` | `POST` | Full detail for one or more recordings (body: `["file_id"]`). Returns `trans_result` (transcript segments) and `ai_content` inline. |
| `/file/detail/{id}` | `GET` | Full detail for one recording (may omit transcript) |
| `content_list[].data_link` | `GET` | Signed URL for transcript or AI summary |

**Response envelope:**

The API wraps responses in different envelope shapes depending on the endpoint.
`api.py` normalises all variants, looking for the payload in `payload`,
`data`, `data_file_list`, or at the root of the response.

**Content hydration:**

The client first tries `POST /file/list` which returns transcript data
(`trans_result`) inline as a list of speaker-labelled segments. If that
endpoint fails or returns incomplete data, it falls back to
`GET /file/detail/{id}` and fetches transcript/summary from signed URLs
in the `content_list` array.

## Legal

This tool is provided for **personal interoperability** purposes only —
enabling users to access their own data in ways the official app does not
expose. The author is not affiliated with Plaud AI.

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
