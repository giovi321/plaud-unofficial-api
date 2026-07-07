"""Tests for filename hygiene and registry safety in the sync command."""

from __future__ import annotations

import json

import click
import pytest

from plaud_cli import cli


def _norm(title, fid="abcd1234ef", start_ms=1_780_000_000_000):
    return {
        "title": title,
        "file_id": fid,
        "start_time_ms": start_ms,
        "duration_ms": 600_000,
        "summary": "s",
        "highlights": [],
        "transcript": "t",
    }


def test_filename_strips_trailing_space_before_extension():
    # An 80-char cut that lands on a space must not yield "... .md".
    title = "Meeting_ Audio Troubleshooting, GPT in Slack, AI Rollout, Recording Tools " + ("x" * 40)
    name = cli._make_filename(_norm(title), "md")
    stem = name[:-3]
    assert not stem.endswith(" "), name
    assert not stem.endswith("."), name
    assert name.endswith(".md")


def test_filename_forbidden_chars_replaced():
    name = cli._make_filename(_norm('Deal: A/B <test> "x"?'), "md")
    assert not any(c in name[:-3] for c in ':/<>"?*|\\')


def test_filename_strips_control_chars():
    # Tab/newline/CR in a Plaud title would corrupt the downstream TSV state.
    name = cli._make_filename(_norm("Weekly\tsync\nmeeting\rnotes"), "md")
    assert not any(c in name for c in "\t\n\r"), repr(name)


def test_filename_empty_title_falls_back_to_fid():
    name = cli._make_filename(_norm("   ", fid="deadbeef00"), "md")
    assert "deadbeef00" in name


def test_filename_has_date_prefix():
    name = cli._make_filename(_norm("Hello"), "md")
    # YYYY-MM-DD_ prefix (exact day is timezone-dependent; shape is not)
    assert name[:11].count("-") == 2 and name[10] == "_"


def test_load_registry_ok(tmp_path):
    (tmp_path / cli.REGISTRY_FILENAME).write_text(
        json.dumps({"fid": {"filename": "x.md", "complete": True}}), encoding="utf-8"
    )
    reg = cli._load_registry(tmp_path)
    assert reg["fid"]["filename"] == "x.md"


def test_corrupt_registry_raises_and_preserves(tmp_path):
    p = tmp_path / cli.REGISTRY_FILENAME
    p.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(click.ClickException):
        cli._load_registry(tmp_path)
    # canonical file stays in place so EVERY run fails loud (no silent
    # re-download), and a copy is left for inspection.
    assert p.exists(), "corrupt registry must stay at the canonical path"
    assert "not json" in p.read_text(encoding="utf-8")
    backups = list(tmp_path.glob(cli.REGISTRY_FILENAME + ".corrupt-*"))
    assert backups, "a copy must be saved for recovery"
    assert "not json" in backups[0].read_text(encoding="utf-8")
    # a second run must also raise (state not silently reset)
    with pytest.raises(click.ClickException):
        cli._load_registry(tmp_path)


def test_save_registry_atomic_roundtrip(tmp_path):
    data = {"fid": {"filename": "a.md", "complete": False, "sections": ["transcript"]}}
    cli._save_registry(tmp_path, data)
    assert not list(tmp_path.glob(cli.REGISTRY_FILENAME + ".tmp"))  # no temp left behind
    assert cli._load_registry(tmp_path) == data
