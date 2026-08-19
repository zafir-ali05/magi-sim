import pytest

from magi.models import Act
from magi.transcript import Transcript, TranscriptFrozenError


def test_transcript_assigns_contiguous_ids_and_preserves_seen_version():
    transcript = Transcript()
    first = transcript.append(
        Act(core="MELCHIOR-1", kind="POSITION", content="Initial claim."),
        seen_through_event_id=0,
    )
    second = transcript.append(
        Act(core="CASPER-3", kind="CHALLENGE", content="Challenge.", reply_to=1),
        seen_through_event_id=1,
    )

    assert (first.id, second.id) == (1, 2)
    assert second.seen_through_event_id == 1
    assert transcript.snapshot().version == 2


def test_transcript_rejects_future_versions_and_unseen_replies():
    transcript = Transcript()
    transcript.append(
        Act(core="MELCHIOR-1", kind="POSITION", content="Initial claim."),
        seen_through_event_id=0,
    )

    with pytest.raises(ValueError, match="seen_through_event_id"):
        transcript.append(
            Act(core="BALTHASAR-2", kind="CLARIFY", content="Future view."),
            seen_through_event_id=2,
        )

    with pytest.raises(ValueError, match="reply_to"):
        transcript.append(
            Act(core="CASPER-3", kind="CHALLENGE", content="Invalid.", reply_to=1),
            seen_through_event_id=0,
        )


@pytest.mark.parametrize("kind", ["PASS", "READY"])
def test_transcript_rejects_non_public_review_outcomes(kind):
    transcript = Transcript()

    with pytest.raises(ValueError, match="public transcript"):
        transcript.append(
            Act(core="CASPER-3", kind=kind, content="No public contribution."),
            seen_through_event_id=0,
        )


def test_frozen_transcript_rejects_new_events():
    transcript = Transcript()
    frozen = transcript.freeze()

    assert frozen.version == 0
    with pytest.raises(TranscriptFrozenError):
        transcript.append(
            Act(core="MELCHIOR-1", kind="POSITION", content="Too late."),
            seen_through_event_id=0,
        )
