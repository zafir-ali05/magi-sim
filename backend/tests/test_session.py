import pytest

from magi.session import MagiSession


CORES = ("MELCHIOR-1", "BALTHASAR-2", "CASPER-3")


def discussing_session() -> MagiSession:
    session = MagiSession()
    session.begin_opening()
    session.begin_discussion(latest_event_id=3)
    return session


def ready_session(*, latest_event_id: int = 3) -> MagiSession:
    session = discussing_session()
    for core in CORES:
        session.mark_reviewed(core, latest_event_id)
        session.mark_ready(core)
    return session


def test_natural_closure_requires_every_core_to_review_the_latest_event():
    session = discussing_session()
    session.mark_reviewed("MELCHIOR-1", 3)
    session.mark_reviewed("BALTHASAR-2", 3)
    session.mark_reviewed("CASPER-3", 2)
    for core in CORES:
        session.mark_ready(core)

    assert not session.can_close_naturally(latest_event_id=3)

    session.mark_reviewed("CASPER-3", 3)
    assert session.can_close_naturally(latest_event_id=3)


def test_natural_closure_requires_empty_inboxes_and_no_in_flight_work():
    session = ready_session()
    session.note_enqueued("CASPER-3")

    assert not session.can_close_naturally(latest_event_id=3)

    session.note_dequeued("CASPER-3")
    session.mark_in_flight("MELCHIOR-1", True)
    assert not session.can_close_naturally(latest_event_id=3)

    session.mark_in_flight("MELCHIOR-1", False)
    assert session.can_close_naturally(latest_event_id=3)


def test_new_peer_event_revokes_only_peer_readiness():
    session = ready_session()

    session.revoke_peer_readiness(sender="MELCHIOR-1")

    assert session.core("MELCHIOR-1").ready
    assert not session.core("BALTHASAR-2").ready
    assert not session.core("CASPER-3").ready
    assert session.core("BALTHASAR-2").status == "LISTENING"
    assert session.core("CASPER-3").status == "LISTENING"


def test_budget_exhaustion_preserves_ballot_eligibility_without_fabricating_readiness():
    session = discussing_session()
    session.mark_ready("CASPER-3")

    session.mark_budget_exhausted("CASPER-3")
    session.close_discussion(reason="budget")

    assert not session.core("CASPER-3").ready
    assert session.core("CASPER-3").status == "BUDGET_EXHAUSTED"
    assert session.core("CASPER-3").ballot_eligible
    assert session.can_start_ballots()


def test_failed_core_blocks_ballots_instead_of_counting_as_ready():
    session = discussing_session()
    session.mark_ready("CASPER-3")
    session.mark_in_flight("CASPER-3", True)

    session.mark_failed("CASPER-3")
    with pytest.raises(RuntimeError, match="unavailable"):
        session.mark_ready("CASPER-3")
    session.close_discussion(reason="failure")

    assert not session.core("CASPER-3").ready
    assert not session.core("CASPER-3").in_flight
    assert session.core("CASPER-3").status == "FAILED"
    assert not session.core("CASPER-3").ballot_eligible
    assert not session.can_start_ballots()


def test_timeout_closure_records_reason_without_changing_core_readiness():
    session = discussing_session()
    session.mark_ready("MELCHIOR-1")

    session.close_discussion(reason="timeout")

    assert session.phase == "DISCUSSION_CLOSED"
    assert session.closure_reason == "timeout"
    assert session.core("MELCHIOR-1").ready
    assert not session.core("BALTHASAR-2").ready
    assert not session.core("CASPER-3").ready
    assert session.can_start_ballots()


def test_review_progress_is_monotonic_and_non_negative():
    session = discussing_session()
    session.mark_reviewed("CASPER-3", 4)
    session.mark_reviewed("CASPER-3", 4)

    with pytest.raises(ValueError, match="backwards"):
        session.mark_reviewed("CASPER-3", 3)
    with pytest.raises(ValueError, match="non-negative"):
        session.mark_reviewed("MELCHIOR-1", -1)

    assert session.core("CASPER-3").reviewed_through_event_id == 4


def test_queue_depth_cannot_become_negative():
    session = discussing_session()

    with pytest.raises(ValueError, match="empty"):
        session.note_dequeued("CASPER-3")

    assert session.core("CASPER-3").inbox_depth == 0


def test_a_core_cannot_start_two_requests_at_once():
    session = discussing_session()
    session.mark_in_flight("MELCHIOR-1", True)

    with pytest.raises(RuntimeError, match="already in flight"):
        session.mark_in_flight("MELCHIOR-1", True)

    session.mark_in_flight("MELCHIOR-1", False)
    assert not session.core("MELCHIOR-1").in_flight


def test_happy_path_phase_transitions_are_monotonic():
    session = MagiSession()

    assert session.phase == "CREATED"
    session.begin_opening()
    assert session.phase == "OPENING"
    session.begin_discussion(latest_event_id=3)
    assert session.phase == "DISCUSSING"
    session.close_discussion(reason="natural")
    assert session.phase == "DISCUSSION_CLOSED"
    session.begin_balloting()
    assert session.phase == "BALLOTING"
    session.begin_revealing()
    assert session.phase == "REVEALING"
    session.complete()
    assert session.phase == "COMPLETED"
    with pytest.raises(RuntimeError, match="terminal"):
        session.note_enqueued("CASPER-3")


def test_forbidden_phase_jumps_and_backward_transitions_are_rejected():
    session = MagiSession()

    with pytest.raises(RuntimeError, match="OPENING"):
        session.begin_discussion(latest_event_id=0)
    with pytest.raises(RuntimeError, match="DISCUSSING"):
        session.close_discussion(reason="timeout")
    with pytest.raises(RuntimeError, match="DISCUSSION_CLOSED"):
        session.begin_balloting()

    session.begin_opening()
    with pytest.raises(RuntimeError, match="CREATED"):
        session.begin_opening()


def test_event_versions_and_closure_reasons_are_validated():
    session = MagiSession()
    session.begin_opening()

    with pytest.raises(ValueError, match="non-negative"):
        session.begin_discussion(latest_event_id=-1)

    session.begin_discussion(latest_event_id=0)
    with pytest.raises(ValueError, match="closure reason"):
        session.close_discussion(reason="consensus")


@pytest.mark.parametrize(
    ("terminal", "expected_phase"),
    [("fail", "FAILED"), ("cancel", "CANCELLED")],
)
def test_terminal_sessions_reject_later_events_and_transitions(terminal, expected_phase):
    session = discussing_session()
    getattr(session, terminal)()

    assert session.phase == expected_phase
    with pytest.raises(RuntimeError, match="terminal"):
        session.note_enqueued("CASPER-3")
    with pytest.raises(RuntimeError, match="terminal"):
        session.close_discussion(reason="failure")
    with pytest.raises(RuntimeError, match="terminal"):
        session.cancel()


def test_unknown_core_is_rejected():
    session = discussing_session()

    with pytest.raises(ValueError, match="Unknown MAGI core"):
        session.core("UNKNOWN")
