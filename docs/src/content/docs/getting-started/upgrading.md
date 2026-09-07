---
title: Upgrading
description: What changed across 1.x, 2.0 and 2.3, and what you have to do about it.
---

## From 2.x to 2.3

Nothing to do. Requests now retry transient failures (connection and read errors, DNS failures, `429`, `5xx`) three times with backoff, which changes only how a flaky network is handled, not any output or flag.

One consequence is worth knowing if you schedule the CLI: a request can now take up to roughly three times the 30s client timeout before it gives up, so a frequent schedule should be single-instance guarded. See [Keeping an unattended sync alive](/plaud-unofficial-api/guides/unattended-sync/).

## From 1.x to 2.0

v2.0.0 makes Plaud's regional sharding and short-lived v2 tokens first-class. If you are coming from 1.x:

- **Stale tokens may need re-capturing.** A token captured before the regional migration can be rejected by your account's current region. The client now routes by the token's `region` claim and follows `-302` redirects automatically, but if your stored token predates the migration, re-authenticate.
- **Unattended/cron syncs must switch to credential login.** Older long-lived tokens could sit in `config.yaml` for months; current v2 tokens expire (browser ~24h, credential-login ~30 days). Run `plaud login --email …`, or set `PLAUD_EMAIL` / `PLAUD_PASSWORD`, so the token auto-refreshes. Pasted tokens are **not** refreshed.
- **New optional config fields.** `config.yaml` may now contain `email` and `password` (written by credential login); env vars `PLAUD_EMAIL` / `PLAUD_PASSWORD` override them.
- **No behavioural change to exports.** Transcript still renders inline (`## Transcript`) in the formatted file when included; the in-code help text was corrected to match.

Full history is in the [changelog](https://github.com/giovi321/plaud-unofficial-api/blob/main/CHANGELOG.md).
