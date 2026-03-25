"""Plaud CLI – unofficial command-line tool for plaud.ai."""

from __future__ import annotations

import json
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich import box

from plaud_cli import api as plaud_api
from plaud_cli import config as cfg
from plaud_cli import normalizer

console = Console()
err_console = Console(stderr=True, style="red")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_token(token_opt: str | None) -> str:
    token = token_opt or cfg.get_token()
    if not token:
        err_console.print(
            "[bold red]No token found.[/bold red] "
            "Run [bold]plaud login[/bold] first, or pass --token."
        )
        sys.exit(1)
    return token


def _make_client(token: str) -> plaud_api.PlaudClient:
    return plaud_api.PlaudClient(token=token, api_base=cfg.get_api_base())


def _fmt_ms(ms: int) -> str:
    if not ms:
        return "—"
    total_sec = ms // 1000
    h, rem = divmod(total_sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _fmt_ts(ms: int) -> str:
    if not ms:
        return "—"
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ms)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option("1.5.0", prog_name="plaud")
@click.option(
    "--config", "config_path",
    type=click.Path(dir_okay=False),
    default=None,
    metavar="FILE",
    help="Path to config YAML file. Overrides the default location "
         "(~/.config/plaud-cli/config.yaml).",
)
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """Unofficial Plaud.ai CLI – manage recordings from the command line."""
    ctx.ensure_object(dict)
    if config_path:
        cfg.set_config_path(config_path)


# ---------------------------------------------------------------------------
# login / logout / whoami
# ---------------------------------------------------------------------------

@main.command()
@click.option("--token", prompt="Plaud token (starts with 'bearer eyJ…' or just the JWT)",
              hide_input=True, help="Long-lived bearer token from web.plaud.ai localStorage.")
def login(token: str) -> None:
    """Store your Plaud API token securely."""
    token = token.strip()
    if not token:
        err_console.print("Token cannot be empty.")
        sys.exit(1)
    location = cfg.save_token(token)
    console.print(f"[green]Token saved[/green] → [bold]{location}[/bold]")


@main.command()
def logout() -> None:
    """Remove the stored Plaud API token."""
    cfg.delete_token()
    console.print("[yellow]Token removed.[/yellow]")


@main.command()
@click.option("--token", default=None, hidden=True)
def whoami(token: str | None) -> None:
    """Verify token by fetching the file list (prints count on success)."""
    tok = _require_token(token)
    with _make_client(tok) as client:
        try:
            files = client.list_files()
            console.print(
                f"[green]Token is valid.[/green] "
                f"Account has [bold]{len(files)}[/bold] recording(s)."
            )
        except plaud_api.PlaudApiError as exc:
            err_console.print(f"[bold red]{exc.category}:[/bold red] {exc}")
            sys.exit(1)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@main.group()
def config() -> None:
    """Manage CLI configuration."""


@config.command("set-api")
@click.argument("url")
def config_set_api(url: str) -> None:
    """Override the API base URL (default: https://api.plaud.ai)."""
    cfg.set_api_base(url)
    console.print(f"API base set to [bold]{url}[/bold].")


@config.command("show")
def config_show() -> None:
    """Print current configuration and the config file path."""
    token = cfg.get_token()
    api_base = cfg.get_api_base()
    config_path = cfg._config_file()
    console.print(f"[bold]config file:[/bold] {config_path}")
    console.print(f"[bold]api_base:[/bold]    {api_base}")
    if token:
        preview = token[:12] + "…" if len(token) > 12 else token
        console.print(f"[bold]token:[/bold]       {preview} [dim](use 'plaud logout' to remove)[/dim]")
    else:
        console.print("[bold]token:[/bold]       [red]not set[/red] [dim]— edit the config file or run 'plaud login'[/dim]")


@config.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
def config_init(force: bool) -> None:
    """Create a starter config.yaml with a token placeholder."""
    import yaml
    config_path = cfg._config_file()
    if config_path.exists() and not force:
        console.print(
            f"Config file already exists: [bold]{config_path}[/bold]\n"
            "Use [bold]--force[/bold] to overwrite."
        )
        return
    starter: dict[str, str] = {
        "api_base": "https://api.plaud.ai",
        "token": "bearer eyJ...",
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(starter, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    console.print(
        f"[green]Created[/green] {config_path}\n"
        "Edit it and replace the [bold]token[/bold] value with your JWT from "
        "[bold]web.plaud.ai[/bold] → DevTools → "
        "[dim]localStorage.getItem(\"tokenstr\")[/dim]"
    )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@main.command("list")
@click.option("--token", default=None, help="Override stored token.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--no-trash", is_flag=True, default=True, show_default=True,
              help="Hide trashed recordings.")
@click.option("--limit", default=0, help="Limit number of results (0 = all).")
def list_files(token: str | None, as_json: bool, no_trash: bool, limit: int) -> None:
    """List all recordings in your Plaud account."""
    tok = _require_token(token)
    with _make_client(tok) as client:
        try:
            files = client.list_files()
        except plaud_api.PlaudApiError as exc:
            err_console.print(f"[bold red]{exc.category}:[/bold red] {exc}")
            sys.exit(1)

    if no_trash:
        files = [f for f in files if not f.get("is_trash")]

    if limit > 0:
        files = files[:limit]

    if as_json:
        click.echo(json.dumps(files, indent=2, ensure_ascii=False))
        return

    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Date", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Title / File Name")

    for i, rec in enumerate(files, 1):
        rec_id = rec.get("file_id") or rec.get("id") or "?"
        start_ms = rec.get("start_time", 0) or 0
        duration_ms = rec.get("duration", 0) or 0
        title = rec.get("file_name") or rec.get("filename") or rec.get("title") or "—"
        table.add_row(
            str(i),
            rec_id,
            _fmt_ts(start_ms),
            _fmt_ms(duration_ms),
            title,
        )

    console.print(table)
    console.print(f"[dim]{len(files)} recording(s)[/dim]")


# ---------------------------------------------------------------------------
# detail
# ---------------------------------------------------------------------------

@main.command()
@click.argument("file_id")
@click.option("--token", default=None, help="Override stored token.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--hydrate/--no-hydrate", default=True, show_default=True,
              help="Fetch transcript/summary from signed URLs.")
def detail(file_id: str, token: str | None, as_json: bool, hydrate: bool) -> None:
    """Show full detail for a single recording."""
    tok = _require_token(token)
    with _make_client(tok) as client:
        try:
            raw = client.get_file_detail_hydrated(file_id) if hydrate else client.get_file_detail(file_id)
        except plaud_api.PlaudApiError as exc:
            err_console.print(f"[bold red]{exc.category}:[/bold red] {exc}")
            sys.exit(1)

    if as_json:
        click.echo(json.dumps(raw, indent=2, ensure_ascii=False))
        return

    norm = normalizer.normalize(raw)
    _print_detail(norm)


def _print_detail(norm: dict[str, Any]) -> None:
    console.rule(f"[bold]{norm['title'] or norm['file_id']}[/bold]")
    console.print(f"[bold]ID:[/bold]       {norm['id']}")
    console.print(f"[bold]File ID:[/bold]  {norm['file_id']}")
    console.print(f"[bold]Date:[/bold]     {_fmt_ts(norm['start_time_ms'])}")
    console.print(f"[bold]Duration:[/bold] {_fmt_ms(norm['duration_ms'])}")

    if norm["summary"]:
        console.rule("[dim]Summary[/dim]")
        console.print(norm["summary"])

    if norm["highlights"]:
        console.rule("[dim]Highlights[/dim]")
        for h in norm["highlights"]:
            console.print(f"  • {h}")

    if norm["transcript"]:
        console.rule("[dim]Transcript[/dim]")
        console.print(norm["transcript"])

    console.rule()


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

EXPORT_FORMATS = ["markdown", "json", "txt"]
CONTENT_TYPES = ["transcript", "summary", "highlights", "recording"]
ALL_TEXT_TYPES = {"transcript", "summary", "highlights"}
FORMATTED_TYPES = {"summary", "highlights", "transcript"}


@main.command()
@click.argument("file_id")
@click.option("--token", default=None, help="Override stored token.")
@click.option("--format", "fmt", type=click.Choice(EXPORT_FORMATS), default="markdown",
              show_default=True,
              help="Output format for summary and highlights. "
                   "Transcript is always saved as plain text.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path (base name). "
                   "Transcript is written to a separate .txt file with the same base name.")
@click.option("--hydrate/--no-hydrate", default=True, show_default=True)
@click.option(
    "--include", "include_types", multiple=True,
    type=click.Choice(CONTENT_TYPES, case_sensitive=False),
    help="Content to include. Repeat to select multiple "
         "(e.g. --include transcript --include summary). "
         "Defaults to all text types (transcript, summary, highlights).",
)
def export(file_id: str, token: str | None, fmt: str, output: str | None,
          hydrate: bool, include_types: tuple[str, ...]) -> None:
    """Export a recording to Markdown, JSON, or plain text.

    \b
    The --format option applies to summary and highlights only.
    Transcript is always exported as plain text (.txt) because Plaud
    does not provide formatted transcript content.
    When multiple content types are requested, each type is written to
    its own file using the same base name.
    """
    includes = set(include_types) if include_types else ALL_TEXT_TYPES
    tok = _require_token(token)
    with _make_client(tok) as client:
        try:
            raw = client.get_file_detail_hydrated(file_id) if hydrate else client.get_file_detail(file_id)
        except plaud_api.PlaudApiError as exc:
            err_console.print(f"[bold red]{exc.category}:[/bold red] {exc}")
            sys.exit(1)

        norm = normalizer.normalize(raw)

        if "recording" in includes:
            try:
                audio_bytes, audio_ext = client.download_recording(raw)
            except plaud_api.PlaudApiError as exc:
                err_console.print(f"[yellow]Recording download failed:[/yellow] {exc}")
                audio_bytes, audio_ext = None, None
        else:
            audio_bytes, audio_ext = None, None

    base = pathlib.Path(output).stem if output else (norm["title"] or file_id)
    base_dir = pathlib.Path(output).parent if output else pathlib.Path(".")

    formatted_includes = includes & FORMATTED_TYPES
    want_transcript = "transcript" in includes

    if formatted_includes:
        ext_map = {"markdown": "md", "json": "json", "txt": "txt"}
        ext = ext_map[fmt]
        if fmt == "json":
            rendered = json.dumps(_filter_norm(norm, formatted_includes), indent=2, ensure_ascii=False)
        elif fmt == "txt":
            rendered = _render_txt(norm, formatted_includes)
        else:
            rendered = _render_markdown(norm, formatted_includes)

        if output:
            out_path = base_dir / f"{base}.{ext}"
            out_path.write_text(rendered, encoding="utf-8")
            console.print(f"[green]Exported to[/green] {out_path}")
        else:
            click.echo(rendered)

    if want_transcript and "transcript" not in formatted_includes and norm["transcript"]:
        transcript_text = norm["transcript"]
        if output:
            transcript_path = base_dir / f"{base}_transcript.txt"
            transcript_path.write_text(transcript_text, encoding="utf-8")
            console.print(f"[green]Transcript saved to[/green] {transcript_path}")
        else:
            if formatted_includes:
                click.echo("\n--- TRANSCRIPT ---\n")
            click.echo(transcript_text)

    if audio_bytes is not None:
        audio_out = base_dir / f"{base}.{audio_ext}"
        audio_out.write_bytes(audio_bytes)
        console.print(f"[green]Recording saved to[/green] {audio_out}")


def _filter_norm(norm: dict[str, Any], includes: set[str]) -> dict[str, Any]:
    filtered = dict(norm)
    if "summary" not in includes:
        filtered["summary"] = ""
    if "highlights" not in includes:
        filtered["highlights"] = []
    if "transcript" not in includes:
        filtered["transcript"] = ""
    return filtered


def _render_markdown(norm: dict[str, Any], includes: set[str] | None = None) -> str:
    if includes is None:
        includes = FORMATTED_TYPES
    lines: list[str] = []
    title = norm["title"] or norm["file_id"]
    lines.append(f"---")
    lines.append(f"file_id: {norm['file_id']}")
    lines.append(f"date: {_fmt_ts(norm['start_time_ms'])}")
    lines.append(f"duration: {_fmt_ms(norm['duration_ms'])}")
    lines.append(f"---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")

    if "summary" in includes and norm["summary"]:
        lines.append("## Summary")
        lines.append("")
        lines.append(norm["summary"])
        lines.append("")

    if "highlights" in includes and norm["highlights"]:
        lines.append("## Highlights")
        lines.append("")
        for h in norm["highlights"]:
            lines.append(f"- {h}")
        lines.append("")

    if "transcript" in includes and norm["transcript"]:
        lines.append("## Transcript")
        lines.append("")
        lines.append(norm["transcript"])
        lines.append("")

    return "\n".join(lines)


def _render_txt(norm: dict[str, Any], includes: set[str] | None = None) -> str:
    if includes is None:
        includes = FORMATTED_TYPES
    title = norm["title"] or norm["file_id"]
    lines: list[str] = [
        title,
        "=" * len(title),
        f"Date:     {_fmt_ts(norm['start_time_ms'])}",
        f"Duration: {_fmt_ms(norm['duration_ms'])}",
        "",
    ]
    if "summary" in includes and norm["summary"]:
        lines += ["SUMMARY", "-------", norm["summary"], ""]
    if "highlights" in includes and norm["highlights"]:
        lines += ["HIGHLIGHTS", "----------"]
        for h in norm["highlights"]:
            lines.append(f"  * {h}")
        lines.append("")
    if "transcript" in includes and norm["transcript"]:
        lines += ["TRANSCRIPT", "----------", norm["transcript"], ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# sync  (bulk export / folder synchronisation)
# ---------------------------------------------------------------------------

REGISTRY_FILENAME = ".plaud_registry.json"


def _load_registry(dest: pathlib.Path) -> dict[str, Any]:
    """Load the download registry from dest/.plaud_registry.json."""
    path = dest / REGISTRY_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_registry(dest: pathlib.Path, registry: dict[str, Any]) -> None:
    """Persist the download registry."""
    path = dest / REGISTRY_FILENAME
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_filename(norm: dict[str, Any], ext: str) -> str:
    title = norm["title"] or norm["file_id"]
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:80]
    date_str = ""
    if norm["start_time_ms"]:
        try:
            dt = datetime.fromtimestamp(norm["start_time_ms"] / 1000, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d_")
        except Exception:
            pass
    return f"{date_str}{safe_title}.{ext}"


def _render_content(norm: dict[str, Any], fmt: str, includes: set[str] | None = None) -> str:
    if includes is None:
        includes = FORMATTED_TYPES
    if fmt == "json":
        return json.dumps(_filter_norm(norm, includes), indent=2, ensure_ascii=False)
    if fmt == "txt":
        return _render_txt(norm, includes)
    return _render_markdown(norm, includes)


@main.command()
@click.argument("output_dir", type=click.Path())
@click.option("--token", default=None, help="Override stored token.")
@click.option(
    "--mode",
    type=click.Choice(["one-way", "two-way"]),
    default="one-way",
    show_default=True,
    help=(
        "Sync mode. "
        "one-way: download missing/updated recordings from remote to local. "
        "two-way: same as one-way, plus warn about local files whose recording "
        "has been deleted from the remote."
    ),
)
@click.option("--format", "fmt", type=click.Choice(EXPORT_FORMATS), default="markdown",
              show_default=True,
              help="Output format for summary and highlights. "
                   "Transcript is always saved as plain text.")
@click.option("--no-trash", is_flag=True, default=True, show_default=True,
              help="Skip trashed recordings.")
@click.option("--hydrate/--no-hydrate", default=True, show_default=True,
              help="Fetch transcript/summary from signed URLs.")
@click.option(
    "--since", default=None, metavar="DATE",
    help="Only sync recordings newer than this ISO-8601 date (e.g. 2024-01-01).",
)
@click.option(
    "--registry/--no-registry",
    default=False,
    show_default=True,
    help=(
        "Maintain a " + REGISTRY_FILENAME + " file in the output directory. "
        "Tracks which file_ids have been downloaded so that moved or renamed "
        "local files are not downloaded again."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be downloaded/warned about without writing any files.",
)
@click.option(
    "--only-ready",
    is_flag=True,
    default=False,
    help="Skip recordings that have no AI-generated content yet "
         "(no summary, highlights, or transcript).",
)
@click.option(
    "--include", "include_types", multiple=True,
    type=click.Choice(CONTENT_TYPES, case_sensitive=False),
    help="Content to include. Repeat to select multiple "
         "(e.g. --include transcript --include recording). "
         "Defaults to all text types (transcript, summary, highlights).",
)
def sync(
    output_dir: str,
    token: str | None,
    mode: str,
    fmt: str,
    no_trash: bool,
    hydrate: bool,
    since: str | None,
    registry: bool,
    dry_run: bool,
    only_ready: bool,
    include_types: tuple[str, ...],
) -> None:
    """Synchronise a local folder with your Plaud recordings.

    \b
    Modes
    -----
    one-way   Download recordings that are not yet present locally.
              A file is considered present if its file_id appears in the
              registry (--registry) OR if a file with the expected name
              already exists in the output directory.
    two-way   Same as one-way, but also reports local files (tracked in
              the registry) whose recording has since been deleted from
              the remote.  No local files are deleted automatically.

    \b
    Registry
    --------
    When --registry is enabled a hidden JSON file (.plaud_registry.json)
    is kept inside the output directory.  It maps each downloaded file_id
    to the filename and download timestamp so that renamed or moved files
    are not downloaded again.
    """
    includes = set(include_types) if include_types else ALL_TEXT_TYPES
    formatted_includes = includes & FORMATTED_TYPES
    want_transcript = "transcript" in includes
    want_recording = "recording" in includes
    tok = _require_token(token)
    dest = pathlib.Path(output_dir)

    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    since_ms: int | None = None
    if since:
        try:
            from dateutil.parser import parse as parse_date
            since_ms = int(parse_date(since).timestamp() * 1000)
        except Exception:
            err_console.print(f"[red]Invalid --since date:[/red] {since}")
            sys.exit(1)

    with _make_client(tok) as client:
        try:
            all_files = client.list_files()
        except plaud_api.PlaudApiError as exc:
            err_console.print(f"[bold red]{exc.category}:[/bold red] {exc}")
            sys.exit(1)

        if no_trash:
            all_files = [f for f in all_files if not f.get("is_trash")]

        if since_ms is not None:
            all_files = [f for f in all_files if (f.get("start_time") or 0) > since_ms]

        remote_ids: set[str] = {
            rec.get("file_id") or rec.get("id", "")
            for rec in all_files
        } - {""}

        ext_map = {"markdown": "md", "json": "json", "txt": "txt"}
        ext = ext_map[fmt]

        reg: dict[str, Any] = _load_registry(dest) if registry and dest.exists() else {}

        # ── two-way: detect local orphans ────────────────────────────────
        if mode == "two-way" and registry:
            orphans = [
                (fid, entry)
                for fid, entry in reg.items()
                if fid not in remote_ids
            ]
            if orphans:
                console.print(
                    f"[yellow][two-way][/yellow] "
                    f"{len(orphans)} local file(s) no longer exist on remote:"
                )
                for fid, entry in orphans:
                    console.print(
                        f"  [yellow]![/yellow] {entry.get('filename', fid)} "
                        f"[dim](file_id: {fid})[/dim]"
                    )
            else:
                console.print("[dim][two-way] No orphaned local files found.[/dim]")

        # ── determine which files to download ────────────────────────────
        to_download = []
        for rec in all_files:
            fid = rec.get("file_id") or rec.get("id")
            if not fid:
                continue
            if registry and fid in reg:
                continue  # already downloaded (regardless of current filename)
            # Fall back to name-based check when registry is disabled
            # We need the normalised name, so do a quick name estimation
            # from the list record (no detail fetch needed for the check).
            if not registry:
                start_ms = rec.get("start_time", 0) or 0
                title_raw = (
                    rec.get("file_name") or rec.get("filename") or
                    rec.get("title") or fid
                )
                safe = re.sub(r'[\\/:*?"<>|]', "_", title_raw)[:80]
                date_str = ""
                if start_ms:
                    try:
                        dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
                        date_str = dt.strftime("%Y-%m-%d_")
                    except Exception:
                        pass
                candidate = dest / f"{date_str}{safe}.{ext}"
                if candidate.exists():
                    continue
            to_download.append(rec)

        console.print(
            f"Syncing [bold]{len(to_download)}[/bold] / {len(all_files)} "
            f"recording(s) → {dest}/ "
            f"[dim](mode={mode}, format={fmt}{'  dry-run' if dry_run else ''})[/dim]"
        )

        if dry_run and to_download:
            console.print("[dim]Files that would be downloaded:[/dim]")

        ok = 0
        skipped = 0
        failed = 0
        now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for rec in to_download:
            fid = rec.get("file_id") or rec.get("id")
            try:
                raw = (
                    client.get_file_detail_hydrated(fid)
                    if hydrate else client.get_file_detail(fid)
                )
                norm = normalizer.normalize(raw)

                if only_ready and not (norm["summary"] or norm["highlights"] or norm["transcript"]):
                    console.print(f"  [yellow]–[/yellow] {fid}: skipped (no generated content yet)")
                    skipped += 1
                    continue

                filename = _make_filename(norm, ext)

                if dry_run:
                    console.print(f"  [dim]→[/dim] {filename}")
                    ok += 1
                    continue

                if formatted_includes:
                    content = _render_content(norm, fmt, formatted_includes)
                    out_path = dest / filename
                    out_path.write_text(content, encoding="utf-8")
                    console.print(f"  [green]✓[/green] {filename}")

                if want_transcript and "transcript" not in formatted_includes and norm["transcript"]:
                    transcript_filename = _make_filename(norm, "txt") if not formatted_includes else _make_filename(norm, "transcript.txt")
                    transcript_path = dest / transcript_filename
                    transcript_path.write_text(norm["transcript"], encoding="utf-8")
                    console.print(f"  [green]✓[/green] {transcript_filename} [dim](transcript)[/dim]")

                if want_recording:
                    try:
                        audio_bytes, audio_ext = client.download_recording(raw)
                        audio_filename = _make_filename(norm, audio_ext)
                        audio_path = dest / audio_filename
                        audio_path.write_bytes(audio_bytes)
                        console.print(f"  [green]✓[/green] {audio_filename} [dim](recording)[/dim]")
                    except plaud_api.PlaudApiError as exc:
                        console.print(f"  [yellow]⚠[/yellow] {fid}: recording download failed: {exc}")

                if registry:
                    reg[fid] = {"filename": filename, "downloaded_at": now_iso}

                ok += 1
            except plaud_api.PlaudApiError as exc:
                console.print(f"  [red]✗[/red] {fid}: {exc}")
                failed += 1

        if registry and not dry_run:
            _save_registry(dest, reg)

    summary_parts = [f"{ok} downloaded"]
    if skipped:
        summary_parts.append(f"[yellow]{skipped} skipped (no generated content)[/yellow]")
    if failed:
        summary_parts.append(f"[red]{failed} failed[/red]")
    if dry_run:
        summary_parts.append("[yellow]dry-run – nothing written[/yellow]")
    console.print(f"\n[bold]Done.[/bold] {', '.join(summary_parts)}")
