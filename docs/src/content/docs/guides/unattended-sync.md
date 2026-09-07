---
title: Keeping an unattended sync alive
description: Scheduling plaud sync so it keeps running without manual re-login, and the wrapper mistakes that make a healthy sync look broken.
---

A scheduled `plaud sync` that runs without manual re-login is the headline use case. It works because the CLI **re-mints the token automatically** whenever the token is missing or within ~5 minutes of expiry, as long as credentials are available. A still-valid token is reused as-is, with no extra request. See [Authentication](/plaud-unofficial-api/getting-started/authentication/).

## 1. Make credentials available

Prefer environment variables so the password never touches `config.yaml`:

```bash
export PLAUD_EMAIL=you@example.com
export PLAUD_PASSWORD='your-plaud-password'
```

Or run `plaud login --email you@example.com` once to store them in `config.yaml` — simpler, but the password is written to disk in plaintext.

## 2. Schedule it

No explicit `plaud login` is required. The first scheduled run mints the token itself, and later runs refresh it before it expires.

Linux/macOS, via `crontab -e`, nightly at 03:00. cron does not inherit your shell environment, so set the variables in the crontab itself:

```cron
PLAUD_EMAIL=you@example.com
PLAUD_PASSWORD=your-plaud-password
0 3 * * * plaud --config /home/you/.config/plaud-cli/config.yaml sync /home/you/notes >> /home/you/plaud-sync.log 2>&1
```

On Windows, create a Task Scheduler task that runs `plaud sync C:\path\to\notes` on a daily trigger, with `PLAUD_EMAIL` / `PLAUD_PASSWORD` defined in the task's environment.

## Writing a wrapper around it

Anything more than the one-liner above tends to grow a wrapper script. Four things are worth getting right, each of which has caused a real false alarm.

### Guard against overlap, don't rely on runs being short

A request retries transient failures three times against a 30s timeout, so a single call can take ~90s before it gives up. On a short schedule that means runs can overlap. Take a lock and exit quietly if another run holds it:

```bash
exec 9>/run/lock/plaud-sync.lock
flock -n 9 || exit 0
```

### Don't alert on a single failed run

On a frequent schedule, some fraction of runs will fail on a network blip no matter how good the retry policy is. In one measured deployment running every minute, 62 of 88,995 runs failed (0.07%): 56 read timeouts, 5 DNS failures, one `503`, and **zero** auth or data failures. Every one was resolved by the following run without intervention.

Alerting on each of those produces pages that carry no action and train you to ignore the channel. Count *consecutive* failures and alert only once a failure persists:

```bash
n=$(cat "$STATE/consecutive-failures" 2>/dev/null || echo 0)
n=$((n + 1)); echo "$n" > "$STATE/consecutive-failures"
(( n < 3 )) && exit 1        # log it, but stay quiet
notify "sync failing for $n consecutive runs"
```

Clear the counter on success, and send a recovery notice if you had already alerted — otherwise silence leaves the last alert looking unresolved.

:::tip[All counts zero is a signature, not a coincidence]
A failure reporting `0` downloaded, `0` updated *and* `0` failed means the CLI exited before it processed any recording: exit `1`, usually the initial listing call. It is not a partial run. A per-recording failure exits `2` and reports a non-zero failed count instead.
:::

### Let the CLI own the log, or the scheduler, not both

If your wrapper already writes to a log file, do not *also* redirect the scheduler's stdout into the same file. Both copies land, every line appears twice, and `grep -c` over that log then reports exactly double the real event count. That silently corrupts any later analysis of how often something happened.

### Rotate the log

A frequent schedule produces a large log quickly. Give it a `logrotate` stanza, and verify the stanza parses before trusting it:

```bash
logrotate -d /etc/logrotate.d/your-file
```

A malformed stanza is discarded silently and rotates nothing, so the absence of an entry in `/var/lib/logrotate/status` is the signal that rotation has never run. `copytruncate` suits a writer that holds the file open.
