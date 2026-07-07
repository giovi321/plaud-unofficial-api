# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.1.0] - 2026-07-07

Reliability pass on `sync` to stop transcripts silently going missing or being
duplicated in downstream mirrors.

### Added
- `--trash` on `list` and `sync` to include trashed recordings (the default still
  hides them).
- **`--ready-timeout-days N`** — with `--only-ready`, a recording older than `N`
  days is synced with whatever content is available instead of being withheld
  forever when its AI summary never materialises. It is recorded as incomplete so
  it still heals if the summary arrives later. `0` (default) keeps the old
  wait-forever behaviour.

### Changed
- **`--only-ready` now requires *every* requested `--include` text type**, not just
  "summary or highlights". Previously a recording whose transcript was ready but
  whose summary never generated would either be skipped forever, or written as a
  summary-less/near-empty note and frozen. Recordings are now retried until every
  requested section is present (or `--ready-timeout-days` forces them through).
- **Incomplete downloads are retried.** The registry records which sections were
  present and a `complete` flag; an entry written before all requested sections
  were ready is re-fetched on later runs and rewritten once they arrive. Legacy
  entries with no `complete` key are treated as complete.
- **Filenames are stable across re-downloads.** When a recording is re-fetched
  (e.g. to heal an incomplete note), it keeps the filename from its registry entry
  even if its title changed on the Plaud side — so downstream mirrors do not get a
  second copy under the new name.
- **Filename date uses the local timezone**, not UTC, so a recording started just
  after midnight local time is dated the correct day (and lands in the right
  month).
- Truncated titles no longer leave a trailing space or dot before the extension
  (Windows-hostile); an empty/whitespace title falls back to the `file_id`.
- Same-name collisions (same day + identical or truncation-equal title) get a
  short `file_id` suffix instead of silently overwriting the earlier recording.

### Fixed
- **Diarized transcript text is no longer mis-exported as the summary.** When a
  Plaud payload nested raw transcript under generic summary keys, the `## Summary`
  section filled with speaker-labelled transcript and falsely satisfied
  `--only-ready`. The normalizer now drops a candidate summary only when it is
  clearly transcript: dominated by explicit `Speaker N:` / timestamp lines, or
  mostly verbatim lines from the transcript. Label-heavy genuine summaries
  (`Date:`, `Attendees:`, `Action items:`) are kept — an earlier version of this
  guard wrongly discarded them.
- **A corrupt `.plaud_registry.json` no longer silently resets to empty** (which
  re-downloaded everything and duplicated any re-titled recording downstream). A
  copy is saved as `.corrupt-<timestamp>`, the original is left in place, and the
  run aborts — so every subsequent run keeps failing loudly until a human fixes
  it, rather than starting from an empty registry.
- Control characters (tab/newline/CR) are stripped from filenames, so a stray
  one in a Plaud title can no longer corrupt downstream tab-separated state.
- Registry writes are now atomic (temp file + `os.replace`) and flushed after
  every file, so a crash mid-run cannot corrupt the registry or forget files
  already written to disk.
- `sync` exits `2` when one or more recordings failed to download (previously it
  exited `0`, so schedulers and wrappers saw success on partial failure).

### Removed
- A dead code path that would have written transcripts to a separate `.txt` file.
  Transcript already renders inline (`## Transcript`) in the formatted export when
  included — behaviour is unchanged.

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
