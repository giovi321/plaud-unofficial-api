"""End-to-end tests for the `sync` command's readiness gate and exit codes.

These drive the real Click command with the network boundary (_make_client,
token) stubbed, so the download loop, registry, and gating logic run for real.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from plaud_cli import cli


class _FakeClient:
    def __init__(self, listing, details):
        self._listing = listing
        self._details = details
        self.fetched = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def list_files(self):
        return self._listing

    def get_file_detail_hydrated(self, fid):
        self.fetched.append(fid)
        return self._details[fid]

    def get_file_detail(self, fid):
        return self._details[fid]


@pytest.fixture
def patch_client(monkeypatch):
    def _install(listing, details):
        client = _FakeClient(listing, details)
        monkeypatch.setattr(cli, "_require_token", lambda opt: "tok")
        monkeypatch.setattr(cli, "_make_client", lambda tok: client)
        return client
    return _install


def _rec(fid, start_ms=1_780_000_000_000):
    return {"file_id": fid, "start_time": start_ms}


def _detail(fid, *, summary="", transcript="", title="Meeting"):
    d = {"file_id": fid, "file_name": title, "start_time": 1_780_000_000_000, "duration": 600_000}
    if summary:
        d["summary"] = summary
    if transcript:
        d["full_text"] = transcript
    return d


def _run(tmp_path, extra):
    return CliRunner().invoke(
        cli.main,
        ["sync", str(tmp_path), "--registry",
         "--include", "summary", "--include", "transcript", *extra],
    )


def test_only_ready_skips_when_summary_missing(tmp_path, patch_client):
    # transcript ready, summary not -> with --only-ready, must be skipped
    patch_client([_rec("f1")], {"f1": _detail("f1", transcript="Speaker 1: hi there everyone")})
    res = _run(tmp_path, ["--only-ready"])
    assert res.exit_code == 0, res.output
    assert not list(tmp_path.glob("*.md")), "incomplete recording must not be written"
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    assert reg == {}, "skipped recording must not be registered"


def test_incomplete_is_retried_next_run(tmp_path, patch_client):
    # First run: only transcript -> skipped, nothing registered.
    c1 = patch_client([_rec("f1")], {"f1": _detail("f1", transcript="Speaker 1: hello")})
    _run(tmp_path, ["--only-ready"])
    assert not list(tmp_path.glob("*.md"))
    # Second run: summary now present -> file written and registered complete.
    patch_client([_rec("f1")], {
        "f1": _detail("f1", summary="We discussed the plan.", transcript="Speaker 1: hello")
    })
    res = _run(tmp_path, ["--only-ready"])
    assert res.exit_code == 0, res.output
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    assert reg["f1"]["complete"] is True


def test_ready_timeout_forces_sync_of_old_incomplete(tmp_path, patch_client):
    # Old recording (start far in the past), summary never ready, transcript present.
    old = _rec("f1", start_ms=1_600_000_000_000)  # 2020
    patch_client([old], {"f1": _detail("f1", transcript="Speaker 1: hi")})
    res = _run(tmp_path, ["--only-ready", "--ready-timeout-days", "5"])
    assert res.exit_code == 0, res.output
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1, "aged-out recording must sync with available content"
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    assert reg["f1"]["complete"] is False, "must record it as incomplete so it heals later"


def test_filename_stable_across_retitle(tmp_path, patch_client):
    # First download under title A.
    patch_client([_rec("f1")], {"f1": _detail("f1", summary="s", transcript="t", title="Title A")})
    _run(tmp_path, [])
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    first_name = reg["f1"]["filename"]
    assert "Title A" in first_name
    # Mark incomplete so it re-downloads, and the recording is now retitled B.
    reg["f1"]["complete"] = False
    (tmp_path / cli.REGISTRY_FILENAME).write_text(json.dumps(reg))
    patch_client([_rec("f1")], {"f1": _detail("f1", summary="s2", transcript="t2", title="Title B")})
    _run(tmp_path, [])
    # Same file_id keeps the same filename -> no downstream duplicate.
    names = [p.name for p in tmp_path.glob("*.md")]
    assert names == [first_name], names


def test_ready_timeout_still_skips_when_nothing_ready(tmp_path, patch_client):
    # Old recording but NOTHING ready (no summary, no transcript) -> must still
    # be skipped, not written empty.
    old = _rec("f1", start_ms=1_600_000_000_000)
    patch_client([old], {"f1": _detail("f1")})  # empty detail
    res = _run(tmp_path, ["--only-ready", "--ready-timeout-days", "5"])
    assert res.exit_code == 0, res.output
    assert not list(tmp_path.glob("*.md")), "nothing-ready recording must not be written"
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    assert reg == {}


def test_same_day_same_title_gets_collision_suffix(tmp_path, patch_client):
    # Two distinct recordings, same start day and identical title.
    listing = [_rec("aaaa1111"), _rec("bbbb2222")]
    details = {
        "aaaa1111": _detail("aaaa1111", summary="s", transcript="t", title="Weekly sync"),
        "bbbb2222": _detail("bbbb2222", summary="s", transcript="t", title="Weekly sync"),
    }
    patch_client(listing, details)
    res = _run(tmp_path, [])
    assert res.exit_code == 0, res.output
    names = sorted(p.name for p in tmp_path.glob("*.md"))
    assert len(names) == 2, f"both recordings must be written, got {names}"
    # one keeps the plain name, the other carries a file_id suffix
    assert any("[bbbb2222]" in n or "[aaaa1111]" in n for n in names), names


def test_registry_persisted_after_each_file(tmp_path, patch_client):
    # Second file blows up; the first must already be on disk in the registry
    # (per-file save = crash safety), and the run exits 2.
    from plaud_cli import api as plaud_api

    class _HalfBoom(_FakeClient):
        def get_file_detail_hydrated(self, fid):
            self.fetched.append(fid)
            if fid == "bbbb2222":
                raise plaud_api.PlaudApiError("server", "boom")
            return self._details[fid]

    client = _HalfBoom(
        [_rec("aaaa1111"), _rec("bbbb2222")],
        {"aaaa1111": _detail("aaaa1111", summary="s", transcript="t", title="First")},
    )
    import plaud_cli.cli as c
    c._require_token = lambda opt: "tok"
    c._make_client = lambda tok: client
    res = _run(tmp_path, [])
    assert res.exit_code == 2, res.output
    reg = json.loads((tmp_path / cli.REGISTRY_FILENAME).read_text())
    assert "aaaa1111" in reg, "first file must be registered before the crash on the second"
    assert reg["aaaa1111"]["complete"] is True


def test_failed_download_exits_2(tmp_path, patch_client):
    from plaud_cli import api as plaud_api

    class _Boom(_FakeClient):
        def get_file_detail_hydrated(self, fid):
            raise plaud_api.PlaudApiError("server", "boom")

    client = _Boom([_rec("f1")], {})
    import plaud_cli.cli as c
    # patch_client sets token; override the client with the throwing one
    patch_client([_rec("f1")], {})
    c._make_client = lambda tok: client
    res = _run(tmp_path, [])
    assert res.exit_code == 2, f"partial failure must exit 2, got {res.exit_code}: {res.output}"
