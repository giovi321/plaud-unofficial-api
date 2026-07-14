---
title: Contributing
description: Set up a development environment and run the tests.
---

## Setup

```bash
git clone https://github.com/giovi321/plaud-unofficial-api.git
cd plaud-unofficial-api
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'      # installs pytest alongside the runtime deps
```

## Layout

- `src/plaud_cli/api.py` — the HTTP client: authentication, regional routing, and payload fetch/hydration.
- `src/plaud_cli/cli.py` — the Click commands (`login`, `list`, `detail`, `export`, `sync`, `config`).
- `src/plaud_cli/normalizer.py` — turns raw payloads into `summary` / `highlights` / `transcript` (see [Content extraction](/plaud-unofficial-api/guides/extraction/)).
- `src/plaud_cli/config.py` — config file and credential handling.
- `tests/` — pytest suite; the network boundary is stubbed so the command logic, registry, and readiness gate run for real.

## Tests

```bash
python -m pytest -q
```

The suite covers the sync readiness gate and exit codes, the registry/completeness logic, filename handling, regional routing, and the summary-vs-transcript normalizer guard. If you touch `sync` readiness or the normalizer, add or update a test — those areas have subtle behaviour (e.g. the guard that must drop diarized transcript mis-nested under a summary key without discarding genuine label-heavy summaries).

## Conventions

- Keep test fixtures synthetic; never commit real recordings, transcripts, tokens, or credentials.
- Bump the version in `pyproject.toml` and add a `CHANGELOG.md` entry for user-visible changes.

Bug reports and pull requests go through the [GitHub repository](https://github.com/giovi321/plaud-unofficial-api).
