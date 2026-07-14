---
title: Installation
description: Install plaud-cli and its dependencies.
---

## Requirements

- Python 3.9 or newer
- A Plaud account (email + password, or a web token you can paste)

Runtime dependencies (`httpx`, `click`, `rich`, `python-dateutil`, `pyyaml`) are installed automatically.

## Install from source

```bash
git clone https://github.com/giovi321/plaud-unofficial-api.git
cd plaud-unofficial-api
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

This installs the `plaud` command on your `PATH` (inside the venv). Verify it:

```bash
plaud --version
plaud --help
```

An editable install (`-e`) is convenient because pulling new commits takes effect without reinstalling. For a plain install use `pip install .`.

## Next

- [Authentication](/plaud-unofficial-api/getting-started/authentication/) — log in so the CLI can reach your account.
