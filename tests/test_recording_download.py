"""Tests for downloading a recording's audio.

Regression cover for `export --include recording` and `sync --include
recording` saving nothing: the detail payload stopped listing the audio in
`content_list`, so the CLI reported "No recording download link found" for
every file. The audio is now fetched from `/file/temp-url/{id}`, and the signed
S3 link is requested without the API's Bearer header, which S3 rejects (400).
"""

from __future__ import annotations

import httpx
import pytest

from plaud_cli import api as plaud_api

from test_retry import _make_token

SIGNED = "https://bucket.s3.amazonaws.com/audiofiles/abc.ogg?X-Amz-Signature=sig"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)


@pytest.fixture
def setup(monkeypatch):
    """A client whose API calls and signed-URL fetches are both mocked."""
    seen = {"api": [], "signed": []}

    def api_handler(request: httpx.Request) -> httpx.Response:
        seen["api"].append(request.url.path)
        return httpx.Response(200, json={"status": 0, "temp_url": SIGNED})

    def signed_handler(request: httpx.Request) -> httpx.Response:
        seen["signed"].append(request)
        if "authorization" in request.headers:
            return httpx.Response(400, text="<Error>Only one auth mechanism allowed</Error>")
        return httpx.Response(200, content=b"OggS-audio",
                              headers={"content-type": "binary/octet-stream"})

    client = plaud_api.PlaudClient(token=_make_token())
    client._http = httpx.Client(transport=httpx.MockTransport(api_handler),
                                headers={"Authorization": "Bearer x"})
    real_client = httpx.Client
    monkeypatch.setattr(
        plaud_api.httpx, "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(signed_handler), **kw),
    )
    return client, seen


def test_falls_back_to_temp_url_without_auth_header(setup):
    client, seen = setup
    data, ext = client.download_recording({"file_id": "abc", "content_list": []})
    assert data == b"OggS-audio"
    assert ext == "ogg"                       # from the URL path, not the query
    assert seen["api"] == ["/file/temp-url/abc"]
    assert "authorization" not in seen["signed"][0].headers


def test_audio_deleted_fails_without_asking_for_a_link(setup):
    client, seen = setup
    with pytest.raises(plaud_api.PlaudApiError) as exc:
        client.download_recording({"file_id": "abc", "audio_deleted": True})
    assert exc.value.category == "not_found"
    assert seen["api"] == []


def test_content_list_link_still_used_when_present(setup):
    client, seen = setup
    detail = {"file_id": "abc",
              "content_list": [{"data_type": "audio", "data_link": SIGNED}]}
    data, _ = client.download_recording(detail)
    assert data == b"OggS-audio"
    assert seen["api"] == []


def test_missing_temp_url_is_not_found(setup, monkeypatch):
    client, _ = setup
    monkeypatch.setattr(client, "_get", lambda path: {"status": 0})
    with pytest.raises(plaud_api.PlaudApiError) as exc:
        client.download_recording({"file_id": "abc"})
    assert exc.value.category == "not_found"
