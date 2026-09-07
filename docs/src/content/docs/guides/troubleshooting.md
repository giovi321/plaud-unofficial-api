---
title: Troubleshooting
description: The errors this CLI actually produces, what causes each one, and how to confirm the diagnosis.
---

Errors are printed as `category: message`. Start with [Common error categories](#common-error-categories) if yours is not covered below.

## `invalid_response: user region mismatch`

Plaud shards accounts across regional API hosts and migrates accounts between them (their "Service Region Adjustment"). When the host you contact doesn't hold your account's data, the API replies with `status: -302` / `msg: "user region mismatch"` and the correct host in `data.domains.api`.

The client handles this automatically: it routes by the token's region claim on startup and follows the server's redirect (capped at one hop, `*.plaud.ai` only). If you still see this error, find your real host — the server tells you directly:

```bash
TOKEN=$(grep -i '^token:' ~/.config/plaud-cli/config.yaml \
  | sed -E 's/^token:[[:space:]]*(bearer[[:space:]]+)?//I' | tr -d '"')
curl -s https://api.plaud.ai/file/simple/web \
  -H "Authorization: Bearer $TOKEN" | grep -o '"api":"[^"]*"'
# → "api":"https://api-euc1.plaud.ai"
```

Then pin it if you want to skip the redirect hop: `plaud config set-api https://api-euc1.plaud.ai`.

:::note
The `region` claim inside your token is the region it was *issued* in and can be **stale** after a migration. The host in the `-302` body is authoritative — the client always prefers it over the token claim. Logging in again at `web.plaud.ai` (or via `plaud login --email`) refreshes the claim to your current region.
:::

## `auth: HTTP 401` / `token invalid or expired`

The (correct) regional host is rejecting your token. Two causes:

- **Expired token** — browser session tokens last only ~24h. Decode the `exp` claim to check:

  ```bash
  T=$(grep -i '^token:' ~/.config/plaud-cli/config.yaml | sed -E 's/^token:[[:space:]]*(bearer[[:space:]]+)?//I' | tr -d '"')
  python3 -c "import sys,base64,json,time;p=sys.argv[1].split('.')[1];p+='='*(-len(p)%4);d=json.loads(base64.urlsafe_b64decode(p));print('region',d.get('region'),'| exp',time.strftime('%F %T',time.localtime(d['exp'])),'->','EXPIRED' if d['exp']<time.time() else 'valid')" "$T"
  ```

- **Cross-region token** — a still-valid token whose `region` no longer matches where your data lives (e.g. an old `us-west-2` token after your account moved to `eu-central-1`). The discovery host issues a `-302` (followed automatically), but the destination host then refuses the foreign token with `401`.

Fix either by capturing a fresh token, or — better — by switching to [credential login](/plaud-unofficial-api/getting-started/authentication/) so the token auto-refreshes.

## `Login failed (auth): Login response had no access_token`

The login endpoint returned a success envelope with an empty token. Causes:

- The request reached a host/path that doesn't mint tokens for your account (the client routes login through the discovery host to avoid this). Re-run `plaud login --email`.
- Your account uses **SSO or MFA**, which the email+password flow does not support — capture a token manually instead (see [Authentication](/plaud-unofficial-api/getting-started/authentication/)).
- A transient server-side stub — retry.

## `Auto-login failed (...)`

Shown when auto-refresh is needed but fails and there is no usable existing token (the command then exits non-zero). Check that `PLAUD_EMAIL` / `PLAUD_PASSWORD` (or the `email` / `password` config fields) are correct, and that the account is email+password (not SSO/MFA).

## `network: Network error: The read operation timed out`

A request exhausted its retries. Every request already retries connection errors, read timeouts, DNS failures, `429` and `5xx` three times with backoff, so seeing this means the failure outlasted roughly three attempts against a 30s timeout, not that a single packet was dropped.

Treat it as a real connectivity or Plaud-side problem rather than noise. If it appears on a *scheduled* run and the next run succeeds, that is the retry budget being genuinely exceeded on a bad minute — see [Keeping an unattended sync alive](/plaud-unofficial-api/guides/unattended-sync/) for why a scheduler should not alert on one such run.

## Common error categories

Errors are printed as `category: message` (and the command exits non-zero, except where noted). The categories:

| Category | Meaning |
|----------|---------|
| `network` | Connectivity/transport failure, or an unclassified non-2xx HTTP response. Retried before it surfaces. |
| `auth` | Authentication failure — bad/expired token (HTTP 401/403) or a login that returned no token. Not retried. |
| `rate_limit` | HTTP 429 — too many requests. Retried before it surfaces. |
| `server` | HTTP 5xx — a Plaud server-side error. Retried before it surfaces. |
| `invalid_response` | A malformed or non-success response envelope. Not retried. |
| `not_found` | The requested recording (or its download link) does not exist. Not retried. |

:::note
Recording-download failures during `export`/`sync` are **non-fatal** — they print a yellow warning and the run continues.
:::

## Exit codes from `sync`

See [sync → Exit codes](/plaud-unofficial-api/commands/sync/). In short: `1` means the run aborted before any recording was processed, so every count is zero; `2` means some recordings failed individually and the rest succeeded.
