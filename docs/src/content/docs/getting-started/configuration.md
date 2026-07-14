---
title: Configuration
description: The config file, environment variables, and the API base URL.
---

## Config file

Settings live in `~/.config/plaud-cli/config.yaml` (or `$XDG_CONFIG_HOME/plaud-cli/config.yaml`). Override the location per-invocation with the global `--config FILE` option.

```yaml
api_base: https://api.plaud.ai
token: bearer eyJ...
# optional, for credential auto-refresh:
email: you@example.com
password: your-plaud-password
```

Create a starter file with:

```bash
plaud config init          # --force to overwrite
plaud config show          # prints the config path, api_base, and a token preview
```

Inspect or change the API base:

```bash
plaud config set-api https://api.plaud.ai
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `PLAUD_EMAIL` | Account email for credential auto-refresh. Overrides `email` in `config.yaml`. |
| `PLAUD_PASSWORD` | Account password. Overrides `password` in `config.yaml`. |
| `XDG_CONFIG_HOME` | Base directory for the config file. |

Using the environment variables (with `plaud login --no-save-credentials`) keeps your password out of the config file on disk.

## API base and regions

`api_base` defaults to the discovery host `https://api.plaud.ai`. You normally do not set it manually: the client derives the correct regional host from your token and follows any region-mismatch redirect the API returns. See [Content extraction](/plaud-unofficial-api/guides/extraction/) for what the client does with the responses, and the project README "How the API works" for the regional routing details.

:::tip
Only set `api_base` explicitly if you have a reason to pin a specific regional host. An explicit override is always respected; the default triggers automatic regional routing.
:::
