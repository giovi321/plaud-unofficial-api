---
title: Sync readiness
description: How --only-ready, --ready-requires, and --ready-timeout-days decide when a recording is downloaded.
---

Plaud generates a recording's AI content (summary, highlights) after the audio is uploaded, so for a while a recording exists but its text is incomplete. The readiness options let `sync` avoid writing half-generated notes without withholding them forever.

## The requested text types

`--include` selects what gets exported. The **text** types are `transcript`, `summary`, and `highlights` (`recording` is audio, not text). If you pass no `--include`, all three text types are requested.

## `--only-ready`

Without it, `sync` downloads whatever is available now. With `--only-ready`, a recording is skipped until the **required** text types are present:

```bash
plaud sync ./notes --only-ready --include transcript --include summary
```

By default the required set is *every requested text type* — the recording must have both a transcript and a summary before it downloads.

## `--ready-requires`: gate on a subset

Requiring every included type is often too strict. Some Plaud templates only ever produce a transcript (no prose summary), so waiting for a summary means waiting forever.

`--ready-requires TYPE` narrows the readiness gate to just the listed types, while still **exporting** the others when they happen to be present:

```bash
plaud sync ./notes --only-ready \
  --ready-requires transcript \
  --include transcript --include summary
```

- A transcript-only recording downloads as soon as its transcript is ready; no summary is required.
- A recording that *does* have a summary still gets it exported.
- Default (no `--ready-requires`) is unchanged: all requested text types are required.

## `--ready-timeout-days`: a backstop

If an AI section never materialises, you do not want the recording withheld indefinitely. `--ready-timeout-days N` force-syncs a recording once it is older than N days, with whatever content is available (`0`, the default, means wait forever):

```bash
plaud sync ./notes --only-ready --ready-timeout-days 5 --ready-requires transcript
```

## The registry and completeness

With `--registry`, each downloaded `file_id` is recorded in `.plaud_registry.json` with its filename, the `sections` that were present, and a `complete` flag. On later runs:

- A recording whose entry is `complete` is skipped.
- An **incomplete** entry is retried, so the note *heals* once the missing section appears.

A recording is marked **complete** when either:

1. every requested text type is present, or
2. it has aged out (`--ready-timeout-days`) **and** its required (`--ready-requires`) types are present.

Rule 2 is what stops a transcript-only recording from re-downloading on every run forever: once it passes the timeout with its transcript in hand, it is frozen complete. With no `--ready-requires` set, completeness reduces to rule 1, i.e. the previous behaviour is unchanged.

:::note
`--ready-requires` and the aged-out completeness rule were added in v2.2.0.
:::
