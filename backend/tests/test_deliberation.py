import asyncio
from collections import defaultdict, deque

import pytest

from magi.models import Act, Ballot, Motion


CORES = ("MELCHIOR-1", "BALTHASAR-2", "CASPER-3")


def make_act(core: str, kind: str, content: str, reply_to: int | None = None) -> Act:
    return Act(core=core, kind=kind, content=content, reply_to=reply_to)


def make_ballot(
    core: str,
    vote: str,
    rationale: str,
    conditions: list[str] | None = None,
) -> Ballot:
    return Ballot(
        core=core,
        vote=vote,
        confidence=0.8,
        rationale=rationale,
        conditions=conditions or [],
    )


class QueuedAsk:
    """Small fake provider that records the coordinator's visibility barriers."""

    def __init__(self, *, ready_round: int | None = 1):
        self.ready_round = ready_round
        self.opening_values = {
            core: deque([make_act(core, "POSITION", f"opening from {core}")])
            for core in CORES
        }
        self.reaction_values = {
            core: deque(
                [
                    make_act(
                        core,
                        "READY" if ready_round == round_number else "PASS",
                        f"round {round_number} from {core}",
                    )
                    for round_number in range(1, 4)
                ]
            )
            for core in CORES
        }
        self.ballot_values = {
            "MELCHIOR-1": deque(
                [make_ballot("MELCHIOR-1", "AGREE", "supports the motion")]
            ),
            "BALTHASAR-2": deque(
                [
                    make_ballot(
                        "BALTHASAR-2",
                        "CONDITIONAL",
                        "supports a safeguarded motion",
                        ["audit", "audit"],
                    )
                ]
            ),
            "CASPER-3": deque(
                [make_ballot("CASPER-3", "DISAGREE", "dissent remains material")]
            ),
        }
        self.opening_active = 0
        self.max_opening_active = 0
        self.opening_calls: list[str] = []
        self.reaction_calls: defaultdict[str, int] = defaultdict(int)
        self.reaction_snapshots: list[tuple[str, int, str]] = []
        self.ballot_snapshots: dict[str, str] = {}
        self.completed_ballots: list[str] = []

    async def __call__(self, core, messages, schema, effort, max_tokens):
        prompt = messages[1]["content"]

        if schema is Act and "Form your independent opening" in prompt:
            self.opening_calls.append(core)
            self.opening_active += 1
            self.max_opening_active = max(self.max_opening_active, self.opening_active)
            await asyncio.sleep(0)
            self.opening_active -= 1
            return self.opening_values[core].popleft()

        if schema is Act and "Review the motion and the numbered frozen transcript" in prompt:
            remaining_rounds = int(
                prompt.split("There are ", 1)[1].split(" reaction round", 1)[0]
            )
            round_number = 3 - remaining_rounds
            transcript = prompt.split("FROZEN TRANSCRIPT:\n", 1)[1].split(
                "\n\nRequired output JSON example:", 1
            )[0]
            self.reaction_calls[core] += 1
            self.reaction_snapshots.append((core, round_number, transcript))
            return self.reaction_values[core].popleft()

        if schema is Ballot and "Cast your private final ballot" in prompt:
            transcript = prompt.split("FINAL FROZEN TRANSCRIPT:\n", 1)[1].split(
                "\n\nRequired output JSON example:", 1
            )[0]
            self.ballot_snapshots[core] = transcript
            self.completed_ballots.append(core)
            return self.ballot_values[core].popleft()

        raise AssertionError(f"unexpected request for {core}: {prompt}")


@pytest.mark.asyncio
async def test_deliberation_barriers_and_private_ballots():
    from magi.deliberation import deliberate

    fake = QueuedAsk(ready_round=1)
    motion = Motion(question="Should the pilot proceed?", context="A bounded test motion.")

    events = []
    async for event in deliberate(motion, ask=fake):
        if event.type == "ballots_locked":
            assert set(fake.completed_ballots) == set(CORES)
        events.append(event)

    act_events = [event for event in events if event.type == "act"]
    reaction_snapshots = fake.reaction_snapshots
    assert fake.max_opening_active == 3
    assert fake.opening_calls == list(CORES)
    assert {core: count for core, count in fake.reaction_calls.items()} == {
        core: 1 for core in CORES
    }
    assert all(round_number == 1 for _, round_number, _ in reaction_snapshots)
    assert all(
        snapshot.count("[POSITION]") == 3 and "[READY]" not in snapshot
        for _, _, snapshot in reaction_snapshots
    )
    assert [event.round for event in act_events] == [0, 0, 0, 1, 1, 1]
    assert [event.id for event in act_events] == list(range(1, 7))

    ballot_transcripts = list(fake.ballot_snapshots.values())
    assert len(ballot_transcripts) == 3
    assert len(set(ballot_transcripts)) == 1
    assert ballot_transcripts[0].count("[POSITION]") == 3
    assert ballot_transcripts[0].count("[READY]") == 3

    event_types = [event.type for event in events]
    assert event_types.index("ballots_locked") > max(
        index for index, event_type in enumerate(event_types) if event_type == "act"
    )
    result = next(event for event in events if event.type == "result")
    assert result.outcome == "APPROVED_WITH_CONDITIONS"
    assert [ballot.vote for ballot in result.ballots] == [
        "AGREE",
        "CONDITIONAL",
        "DISAGREE",
    ]
    assert result.conditions == ["audit"]
    assert result.ballots[2].rationale == "dissent remains material"
    assert "decision support" in result.disclaimer.lower()


@pytest.mark.asyncio
async def test_deliberation_reacts_at_most_three_rounds_before_balloting():
    from magi.deliberation import deliberate

    fake = QueuedAsk(ready_round=None)
    events = [
        event
        async for event in deliberate(Motion(question="Should it proceed?"), ask=fake)
    ]

    assert dict(fake.reaction_calls) == {core: 3 for core in CORES}
    assert len(fake.ballot_snapshots) == 3
    for round_number in range(1, 4):
        snapshots = [
            snapshot
            for _, observed_round, snapshot in fake.reaction_snapshots
            if observed_round == round_number
        ]
        assert len(snapshots) == 3
        assert all(snapshot.count("[POSITION]") == 3 for snapshot in snapshots)
        assert all(snapshot.count("[PASS]") == 3 * (round_number - 1) for snapshot in snapshots)
    assert [event.round for event in events if event.type == "act"] == [
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        2,
        3,
        3,
        3,
    ]


@pytest.mark.asyncio
async def test_provider_failure_emits_one_sanitized_error_without_result():
    from magi.deliberation import deliberate

    secret = "provider-secret-and-private-reasoning"

    async def failing_ask(core, messages, schema, effort, max_tokens):
        raise RuntimeError(secret)

    events = [
        event
        async for event in deliberate(
            Motion(question="Should it proceed?"), ask=failing_ask
        )
    ]

    assert [event.type for event in events].count("error") == 1
    assert events[-1].type == "error"
    assert not any(event.type == "result" for event in events)
    assert secret not in events[-1].message
