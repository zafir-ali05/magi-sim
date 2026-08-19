import asyncio

import pytest

from magi.budgets import DiscussionLimits
from magi.deepseek import Generation, TokenUsage
from magi.models import CORE_ORDER, Act, Ballot, Motion


ZERO_USAGE = TokenUsage(0, 0, 0, 0)


def make_act(core, kind, content):
    return Act(core=core, kind=kind, content=content)


def make_ballot(core, vote, rationale, conditions=None):
    return Ballot(
        core=core,
        vote=vote,
        confidence=0.8,
        rationale=rationale,
        conditions=conditions or [],
    )


class ReadyAsk:
    def __init__(self):
        self.opening_delay = 0
        self.reaction_calls = []
        self.completed_ballots = []
        self.ballots = {
            "MELCHIOR-1": make_ballot("MELCHIOR-1", "AGREE", "supports the motion"),
            "BALTHASAR-2": make_ballot(
                "BALTHASAR-2",
                "CONDITIONAL",
                "supports safeguards",
                ["audit", "audit"],
            ),
            "CASPER-3": make_ballot(
                "CASPER-3",
                "DISAGREE",
                "dissent remains material",
            ),
        }

    async def __call__(self, core, messages, schema, effort, max_tokens):
        prompt = messages[1]["content"]
        if schema is Act and "Form your independent opening" in prompt:
            await asyncio.sleep(self.opening_delay)
            return Generation(
                make_act(core, "POSITION", f"opening from {core}"),
                ZERO_USAGE,
            )
        if schema is Act and "coordinator-owned shared review record" in prompt:
            self.reaction_calls.append(core)
            return Generation(make_act(core, "READY", f"ready from {core}"), ZERO_USAGE)
        if schema is Ballot and "Cast your private final ballot" in prompt:
            self.completed_ballots.append(core)
            return Generation(self.ballots[core], ZERO_USAGE)
        raise AssertionError(f"Unexpected request for {core}: {prompt}")


@pytest.mark.asyncio
async def test_deliberate_streams_atomic_openings_private_ballots_and_majority_result():
    from magi.deliberation import deliberate

    fake = ReadyAsk()
    events = []
    async for event in deliberate(Motion(question="Should the pilot proceed?"), ask=fake):
        if event.type == "ballots_locked":
            assert set(fake.completed_ballots) == set(CORE_ORDER)
        events.append(event)

    acts = [event for event in events if event.type == "act"]
    assert [event.act.core for event in acts] == list(CORE_ORDER)
    assert [event.id for event in acts] == [1, 2, 3]
    assert all(event.seen_through_event_id == 0 for event in acts)
    assert [event.phase for event in events if event.type == "phase"] == [
        "OPENING",
        "DISCUSSION",
        "BALLOTING",
    ]
    result = next(event for event in events if event.type == "result")
    assert result.quorum == "majority"
    assert result.recommendation == "APPROVED_WITH_CONDITIONS"
    assert result.outcome == "APPROVED_WITH_CONDITIONS"
    assert not result.requires_human_confirmation
    assert [ballot.vote for ballot in result.ballots] == [
        "AGREE",
        "CONDITIONAL",
        "DISAGREE",
    ]
    assert result.conditions == ["audit"]
    assert result.ballots[2].rationale == "dissent remains material"
    assert "decision support" in result.disclaimer.lower()


@pytest.mark.asyncio
async def test_deliberate_applies_the_motion_decision_policy():
    from magi.deliberation import deliberate

    events = [
        event
        async for event in deliberate(
            Motion(question="Should the pilot proceed?", quorum="unanimous"),
            ask=ReadyAsk(),
        )
    ]

    result = next(event for event in events if event.type == "result")
    assert result.quorum == "unanimous"
    assert result.recommendation == "APPROVED_WITH_CONDITIONS"
    assert result.outcome == "REJECTED"
    assert not result.requires_human_confirmation


@pytest.mark.asyncio
async def test_discussion_timeout_starts_after_openings_finish():
    from magi.deliberation import deliberate

    fake = ReadyAsk()
    fake.opening_delay = 0.25
    events = [
        event
        async for event in deliberate(
            Motion(question="Should the pilot proceed?"),
            ask=fake,
            limits=DiscussionLimits(timeout_seconds=0.2),
        )
    ]

    assert set(fake.reaction_calls) == set(CORE_ORDER)
    assert any(event.type == "result" for event in events)


@pytest.mark.asyncio
async def test_opening_failure_is_sanitized_and_commits_no_partial_snapshot():
    from magi.deliberation import deliberate

    secret = "provider-secret-and-private-reasoning"

    async def failing_ask(core, messages, schema, effort, max_tokens):
        if core == "CASPER-3":
            raise RuntimeError(secret)
        await asyncio.Event().wait()

    events = [
        event
        async for event in deliberate(
            Motion(question="Should the pilot proceed?"),
            ask=failing_ask,
        )
    ]

    assert [event.type for event in events] == ["phase", "error"]
    assert secret not in events[-1].message
