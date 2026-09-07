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

### Capturing one from the browser

Each token carries a `region: aws:<region>` claim, and the CLI routes to the matching host automatically (see [How the API works](/plaud-unofficial-api/guides/how-it-works/)).

1. Open [web.plaud.ai](https://web.plaud.ai/) and log in. Confirm your recordings load.
2. Open **Developer Tools** (`F12` on Windows/Linux, `Cmd+Opt+I` on macOS) and go to **Console**.
3. Paste this. It scans the app's stored values, picks the **freshest non-expired** access token (skipping profile blobs and stale tokens), and copies it to your clipboard:

   ```js
   copy(Object.values(localStorage)
     .flatMap(v => (v && v.match(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g)) || [])
     .map(t => { try { const p = JSON.parse(atob(t.split('.')[1].replace(/-/g,'+').replace(/_/g,'/'))); return p.exp*1000 > Date.now() ? { t, iat: p.iat || 0 } : null; } catch (e) { return null; } })
     .filter(Boolean).sort((a, b) => b.iat - a.iat)[0]?.t);
   ```

   Your clipboard now holds a `eyJ...` JWT. Older app builds also expose it as `localStorage.getItem("tokenstr")`. If the one-liner returns nothing, use the **Network** tab, pick any `api-*.plaud.ai` request, and read `authorization: Bearer ...`.
4. Load it with `plaud login` and paste at the prompt, or put it in `config.yaml`.

:::caution[Not auto-refreshed]
A browser-captured token is short-lived (~24h) and is **not** refreshed. For unattended use, prefer credential login above.
:::

## Automatic token refresh

Web tokens are short-lived (roughly 24 hours for a browser-captured token, ~30 days for a credential-login token). When stored credentials are available (from `config.yaml` or the `PLAUD_EMAIL` / `PLAUD_PASSWORD` environment variables) and the token is missing or within ~5 minutes of expiry, the CLI mints a fresh one transparently, so scheduled/unattended syncs keep working. Environment variables take priority over any `email` / `password` in `config.yaml`.

## Verify and log out

```bash
plaud whoami     # confirms the token works and prints the recording count
plaud logout     # removes the stored token
```

## Next

- [Configuration](/plaud-unofficial-api/getting-started/configuration/) — where the token and settings live.
