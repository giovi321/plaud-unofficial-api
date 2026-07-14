---
title: Authentication
description: Log in with credentials or a pasted token, and keep the token fresh for unattended runs.
---

The CLI authenticates with the same **web token** the Plaud web app uses. There are two ways to obtain one.

## Credential login (recommended)

Log in with your email and password. The CLI calls the web login endpoint, stores the token, and (by default) saves your credentials so it can re-mint the short-lived token automatically before each command.

```bash
plaud login --email you@example.com          # prompts for the password
```

- `--password` can be passed directly, or omitted to be prompted securely.
- `--save-credentials` / `--no-save-credentials` controls whether the email and password are written to `config.yaml` for auto-refresh. The default is to save them.

:::caution[Plaintext credentials]
With `--save-credentials` (the default) your password is stored in plaintext in a gitignored config file. To avoid that, set the `PLAUD_EMAIL` / `PLAUD_PASSWORD` environment variables instead and log in with `--no-save-credentials`.
:::

Credential login supports email + password accounts only, not SSO or MFA.

## Paste a token

If you already have a web token, store it without logging in:

```bash
plaud login                 # prompts for the token (hidden input)
plaud login --token "bearer eyJ..."
```

To capture a token from the browser, open `web.plaud.ai`, sign in, and copy the bearer token from an authenticated API request in the developer tools network tab. See the project README section "Obtaining your token" for the current steps.

## Automatic token refresh

Web tokens are short-lived (roughly 24 hours for a browser-captured token, ~30 days for a credential-login token). When stored credentials are available (from `config.yaml` or the `PLAUD_EMAIL` / `PLAUD_PASSWORD` environment variables) and the token is missing or within ~5 minutes of expiry, the CLI mints a fresh one transparently, so scheduled/unattended syncs keep working. Environment variables take priority over any `email` / `password` in `config.yaml`.

## Verify and log out

```bash
plaud whoami     # confirms the token works and prints the recording count
plaud logout     # removes the stored token
```

## Next

- [Configuration](/plaud-unofficial-api/getting-started/configuration/) — where the token and settings live.
