"""Tests for summary/transcript disambiguation in the normalizer.

Regression coverage for the observed failure where Plaud payloads nested raw
diarized transcript under generic summary keys, so the exported "## Summary"
section contained transcript text and falsely satisfied --only-ready.
"""

from __future__ import annotations

from plaud_cli import normalizer


def _detail(**over):
    base = {
        "file_id": "fid123",
        "file_name": "Some Meeting",
        "start_time": 1_780_000_000_000,
        "duration": 600_000,
    }
    base.update(over)
    return base


def test_genuine_summary_is_kept():
    detail = _detail(summary="We agreed to ship the factsheet by Friday and assign owners.")
    norm = normalizer.normalize(detail)
    assert norm["summary"].startswith("We agreed to ship")


def test_diarized_text_under_summary_is_rejected():
    transcript_blob = "\n".join([
        "Speaker 1: Okay let's get started.",
        "Speaker 2: Sure, I pulled the numbers.",
        "Unknown Speaker 1: Can everyone hear me?",
        "Speaker 2: Yes go ahead.",
        "Speaker 1: Great, first item is the deck.",
    ])
    detail = _detail(summary=transcript_blob)
    norm = normalizer.normalize(detail)
    assert norm["summary"] == "", "diarized transcript must not be exported as the summary"


def test_timestamped_text_under_summary_is_rejected():
    blob = "\n".join([
        "00:00:03 Welcome everybody.",
        "00:00:10 Let's begin with the agenda.",
        "00:01:22 First topic is hiring.",
        "00:02:40 Then we cover the budget.",
    ])
    detail = _detail(summary=blob)
    norm = normalizer.normalize(detail)
    assert norm["summary"] == ""


def test_summary_verbatim_inside_transcript_is_dropped():
    line = "Speaker 1: The whole meeting was about the Q3 roadmap."
    detail = _detail(
        summary=line,
        trans_result={"full_text": f"{line}\nSpeaker 2: Agreed, roadmap first."},
    )
    norm = normalizer.normalize(detail)
    assert norm["summary"] == ""
    assert "roadmap" in norm["transcript"]


def test_short_prose_summary_is_not_misclassified():
    # A legitimate one-line summary that happens to contain a colon.
    detail = _detail(summary="Decision: proceed with the launch next week.")
    norm = normalizer.normalize(detail)
    assert norm["summary"].startswith("Decision")


def test_structured_label_summary_is_kept():
    # A genuine, label-heavy meeting summary must NOT be mistaken for transcript.
    summary = (
        "Date: 2026-07-07\n"
        "Location: Zurich HQ\n"
        "Attendees: Alice, Bob, Carol\n"
        "Decision: proceed with the launch\n"
        "Action items: Bob to draft the deck, Carol to book the room\n"
        "Next steps: reconvene Friday"
    )
    detail = _detail(summary=summary)
    norm = normalizer.normalize(detail)
    assert norm["summary"].startswith("Date:"), "structured summary was wrongly dropped"


def test_blockquote_metadata_summary_is_kept():
    summary = (
        "> Date: 2026-07-07\n"
        "> Location: Zurich HQ\n"
        "> Attendees: Alice, Bob, Carol\n"
        "> Purpose: quarterly review\n"
        "> Outcome: budget approved"
    )
    detail = _detail(summary=summary)
    norm = normalizer.normalize(detail)
    assert norm["summary"].startswith("> Date:"), "blockquote summary was wrongly dropped"


def test_named_speaker_transcript_verbatim_in_summary_is_rejected():
    # Bare-name diarization ("Andi:") copied into the summary is caught by the
    # transcript-overlap guard even though it is not "Speaker N:" shaped.
    convo = (
        "Andi: Let's review the roadmap for next quarter.\n"
        "Giovanni: Agreed, I pulled the latest numbers this morning.\n"
        "Andi: Great, walk me through the top three items.\n"
        "Marco: The first one is the platform migration timeline."
    )
    detail = _detail(summary=convo, full_text=convo)
    norm = normalizer.normalize(detail)
    assert norm["summary"] == ""
    assert norm["transcript"].startswith("Andi:")
