# plaud-cli

> Unofficial command-line tool for [plaud.ai](https://web.plaud.ai/) — reverse-engineered from the Plaud web app.

[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

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
8. [Environment variables](#environment-variables)
9. [Project structure](#project-structure)
10. [How the API works](#how-the-api-works)
11. [Legal](#legal)
12. [License](#license)

---

## Features

- **Token-based auth** — uses the long-lived JWT stored in `localStorage` on `web.plaud.ai`
- **YAML config file** — token and settings live in a human-editable `config.yaml`; no keychain required
- **List** all recordings in a formatted table
- **Detail view** — title, date, duration, AI summary, highlights, full transcript with speaker labels
- **Export** a single recording to Markdown, JSON, or plain text
- **Bulk sync** your entire library to a local directory, with optional `--since` date filter
- **`--json` flag** on most commands for easy scripting and piping
- **Content hydration** — fetches transcript and summary from Plaud's signed URLs when the detail endpoint omits them

---

## Requirements

- Python ≥ 3.9
- Dependencies: `httpx`, `click`, `rich`, `pyyaml`, `python-dateutil`

---

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

---

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

---

## Configuration

All settings are stored in a single YAML file:

| Platform | Default path |
|----------|-------------|
| Linux / macOS | `~/.config/plaud-cli/config.yaml` |
| Windows | `%USERPROFILE%\.config\plaud-cli\config.yaml` |

> Override the directory by setting the `XDG_CONFIG_HOME` environment variable.

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

---

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

# 6. Bulk-export your entire library
plaud sync ./notes/
```

---

## Commands reference

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

---

### `plaud logout`

```
plaud logout
```

Removes the `token` field from `config.yaml`.

---

### `plaud whoami`

```
plaud whoami [--token TEXT]
```

Validates the stored token by calling the API and prints how many recordings
are in the account.

```
Token is valid. Account has 42 recording(s).
```

---

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

---

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

---

### `plaud export <FILE_ID>`

```
plaud export [OPTIONS] FILE_ID
```

Exports a single recording to a file or stdout.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token |
| `--format` | `markdown` | Output format: `markdown`, `json`, or `txt` |
| `-o / --output PATH` | stdout | Write to this file instead of stdout |
| `--hydrate / --no-hydrate` | hydrate | Fetch transcript/summary from signed URLs |

**Examples:**

```bash
# Export to Markdown file
plaud export abc123 -o standup-2024-11-03.md

# Export as JSON to stdout (useful for piping)
plaud export abc123 --format json | jq '.summary'

# Export as plain text
plaud export abc123 --format txt -o standup.txt
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
Speaker A: Good morning everyone...
```

---

### `plaud sync <OUTPUT_DIR>`

```
plaud sync [OPTIONS] OUTPUT_DIR
```

Bulk-exports all recordings to a directory. Each recording is saved as a
separate file named `YYYY-MM-DD_<title>.<ext>`.

| Option | Default | Description |
|--------|---------|-------------|
| `--token TEXT` | config | Override stored token |
| `--format` | `markdown` | Output format: `markdown`, `json`, or `txt` |
| `--no-trash` | on | Skip trashed recordings |
| `--hydrate / --no-hydrate` | hydrate | Fetch transcript/summary from signed URLs |
| `--since DATE` | (all) | Only sync recordings newer than this ISO-8601 date |

**Examples:**

```bash
# Sync entire library as Markdown
plaud sync ./notes/

# Sync only recordings from 2024 onwards as plain text
plaud sync ./archive/ --format txt --since 2024-01-01

# Sync as JSON (useful for further processing)
plaud sync ./json-export/ --format json
```

---

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

---

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

---

### `plaud config set-api <URL>`

```
plaud config set-api <URL>
```

Overrides the API base URL saved in `config.yaml`.
Useful if Plaud changes their API domain or for local testing.

```bash
plaud config set-api https://api.plaud.ai
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `PLAUD_TOKEN` | Token value — takes precedence over `config.yaml` on all commands that accept `--token` |
| `XDG_CONFIG_HOME` | Override the base directory for `config.yaml` (default: `~/.config`) |

---

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

---

## How the API works

Plaud exposes an undocumented REST API at `https://api.plaud.ai`. All requests
are authenticated with a `Bearer` token in the `Authorization` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/file/simple/web` | `GET` | List all recordings (summary objects) |
| `/file/detail/{id}` | `GET` | Full detail for one recording |
| `content_list[].data_link` | `GET` | Signed URL for transcript or AI summary |

**Response envelope:**

The API wraps responses in different envelope shapes depending on the endpoint.
`api.py` normalises all variants, looking for the payload in `payload`,
`data`, `data_file_list`, or at the root of the response.

**Content hydration:**

The detail endpoint sometimes omits the transcript and summary, returning
signed URLs in a `content_list` array instead. When `--hydrate` is on
(the default), the client fetches those URLs automatically and merges the
content into the detail object before normalisation.

---

## Legal

This tool is provided for **personal interoperability** purposes only —
enabling users to access their own data in ways the official app does not
expose. The author is not affiliated with Plaud AI.

Reverse-engineering for interoperability is expressly permitted under:
- **EU Directive 2009/24/EC**, Article 6 (Software Directive)
- **17 U.S.C. § 107** (fair use) for personal/interoperability use cases
- Equivalent provisions in other jurisdictions

---

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
