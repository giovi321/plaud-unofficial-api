# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-06-22

Plaud's regional sharding and short-lived v2 tokens are now first-class.

### Added
- **Credential login** — `plaud login --email EMAIL [--password]` mints a token via
  the Plaud web login endpoint (`POST /auth/access-token`).
- **Automatic token refresh** — commands transparently re-mint the token when it is
  missing or within ~5 minutes of expiry, so unattended/cron syncs keep working.
- **Env-var credentials** — `PLAUD_EMAIL` / `PLAUD_PASSWORD` (take priority over
  `config.yaml`), enabling refresh without storing the password on disk.
- `--save-credentials / --no-save-credentials` on `plaud login`.
- Optional `email` / `password` fields in `config.yaml`.
- `CHANGELOG.md`, plus README sections for Authentication, Environment variables, and
  Upgrading from 1.x.

### Changed
- The login request now uses a **minimal header set**. The login endpoint returns a
  success envelope with an empty `access_token` when sent the full browser-fingerprint
  headers the data endpoints use; login is sent without them.
- Login (and auto-refresh) always run through the discovery host so a stale regional
  `api_base` cannot break authentication.
- Corrected the in-code help/docstrings for `export`/`sync`: transcript is rendered
  **inline** (`## Transcript`) in the formatted file when included — it is not written
  to a separate `.txt`. (No change to actual output.)
- README overhauled and the `--only-ready` description corrected (readiness checks
  summary **or** highlights, not transcript).

### Fixed
- Clearer auth errors, including the response keys when a login returns no token.

### Notes
- The login response includes a `refresh_token`, but the CLI does not use it; it
  re-mints from your stored credentials instead.
- Credential login supports **email + password** accounts only (not SSO or MFA).

## [1.6.1] - 2026-06-22

### Changed
- Stopped tracking compiled bytecode (`__pycache__/*.pyc`) in git.

## [1.6.0] - 2026-06-22

### Added
- **Automatic regional routing** — routes by the token's `region` claim to the matching
  per-region API host.
- **`-302` "user region mismatch" handling** — follows the host the server returns in
  `data.domains.api` (one hop, `*.plaud.ai` only), which wins over a stale token region
  claim.

## [1.5.1] - 2026-03-26

### Changed
- Clarified `--only-ready` (excludes transcript from the readiness check); updated skip
  messages.

## [1.5.0] - 2026-03-25

### Added
- Granular content selection via the `--include` flag (`transcript`, `summary`,
  `highlights`, `recording`) on `export` and `sync`.
- `POST /file/list` support for inline transcript retrieval, plus browser-like request
  headers.

## [1.0.0] - 2026-03-18

- First stable release: list, detail, export, and folder sync.

## Earlier

- `0.2.0`–`0.3.2` — initial CLI, configuration handling, and bug fixes.

[2.0.0]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v2.0.0
[1.6.1]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v1.6.1
[1.6.0]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v1.6.0
[1.5.1]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v1.5.1
[1.5.0]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v1.5.0
[1.0.0]: https://github.com/giovi321/plaud-unofficial-api/releases/tag/v1.0.0
