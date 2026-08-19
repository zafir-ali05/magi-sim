import asyncio
import re
from collections import defaultdict

import pytest

from magi.budgets import DiscussionLimits
from magi.deepseek import Generation, TokenUsage
from magi.models import CORE_ORDER, Act, Ballot, Motion, ReviewDecision


ZERO_USAGE = TokenUsage(0, 0, 0, 0)


def make_act(core, kind, content):
    return Act(core=core, kind=kind, content=content)


def make_review(core, action, content=None, *, reply_to=None):
    if action in {"READY", "PASS"}:
        return ReviewDecision(core=core, action=action)
    return ReviewDecision(
        core=core,
        action="PUBLISH",
        kind=action,
        content=content or f"{action.lower()} from {core}",
        reply_to=reply_to,
    )


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
        if schema is ReviewDecision and "coordinator-owned shared review record" in prompt:
            self.reaction_calls.append(core)
            return Generation(make_review(core, "READY"), ZERO_USAGE)
        if schema is Ballot and "Cast your private final ballot" in prompt:
            self.completed_ballots.append(core)
            return Generation(self.ballots[core], ZERO_USAGE)
        raise AssertionError(f"Unexpected request for {core}: {prompt}")


def prompt_version(prompt):
    match = re.search(r"SHARED TRANSCRIPT VERSION: (\d+)", prompt)
    assert match is not None
    return int(match.group(1))


class ReactiveScenarioAsk:
    def __init__(self):
        self.opening_releases = {core: asyncio.Event() for core in CORE_ORDER}
        self.opening_completed = {core: asyncio.Event() for core in CORE_ORDER}
        self.all_openings_started = asyncio.Event()
        self.opening_started = set()
        self.opening_completion_order = []
        self.opening_prompts = {}
        self.review_versions = defaultdict(list)
        self.review_calls = defaultdict(int)
        self.initial_review_returned = {
            "MELCHIOR-1": asyncio.Event(),
            "BALTHASAR-2": asyncio.Event(),
        }
        self.challenge_committed = asyncio.Event()
        self.response_committed = asyncio.Event()
        self.condition_committed = asyncio.Event()
        self.challenge_returned = False
        self.response_returned = False
        self.condition_returned = False
        self.ballots_started = set()
        self.ballots_completed = set()
        self.all_ballots_started = asyncio.Event()

    async def __call__(self, core, messages, schema, effort, max_tokens):
        prompt = messages[1]["content"]
        if schema is Act and "Form your independent opening" in prompt:
            self.opening_prompts[core] = prompt
            self.opening_started.add(core)
            if self.opening_started == set(CORE_ORDER):
                self.all_openings_started.set()
            await self.opening_releases[core].wait()
            self.opening_completion_order.append(core)
            self.opening_completed[core].set()
            return Generation(make_act(core, "POSITION", f"opening from {core}"), ZERO_USAGE)

        if schema is ReviewDecision and "coordinator-owned shared review record" in prompt:
            version = prompt_version(prompt)
            self.review_versions[core].append(version)
            self.review_calls[core] += 1

            if core == "MELCHIOR-1" and version == 3:
                self.initial_review_returned[core].set()
                return Generation(make_review(core, "READY"), ZERO_USAGE)
            if core == "BALTHASAR-2" and version == 3:
                self.initial_review_returned[core].set()
                if self.review_calls[core] > 1:
                    await self.challenge_committed.wait()
                return Generation(make_review(core, "PASS"), ZERO_USAGE)
            if core == "CASPER-3" and not self.challenge_returned:
                await asyncio.gather(
                    *(event.wait() for event in self.initial_review_returned.values())
                )
                self.challenge_returned = True
                return Generation(
                    make_review(
                        core,
                        "CHALLENGE",
                        "The safeguards may not survive the incentive to expand.",
                    ),
                    ZERO_USAGE,
                )
            if core == "MELCHIOR-1" and version >= 4 and not self.response_returned:
                self.response_returned = True
                return Generation(
                    make_review(
                        core,
                        "RESPONSE",
                        "Use one bounded cycle with an explicit rollback threshold.",
                        reply_to=4,
                    ),
                    ZERO_USAGE,
                )
            if core == "BALTHASAR-2" and version == 4:
                await self.response_committed.wait()
                return Generation(make_review(core, "PASS"), ZERO_USAGE)
            if core == "BALTHASAR-2" and version >= 5 and not self.condition_returned:
                self.condition_returned = True
                return Generation(
                    make_review(
                        core,
                        "PROPOSE_CONDITION",
                        "Keep notice, review, and a human appeal path in force.",
                        reply_to=5,
                    ),
                    ZERO_USAGE,
                )
            if not self.condition_committed.is_set():
                await self.condition_committed.wait()
                return Generation(make_review(core, "PASS"), ZERO_USAGE)
            return Generation(make_review(core, "READY"), ZERO_USAGE)

        if schema is Ballot and "Cast your private final ballot" in prompt:
            self.ballots_started.add(core)
            if self.ballots_started == set(CORE_ORDER):
                self.all_ballots_started.set()
            await self.all_ballots_started.wait()
            ballot = {
                "MELCHIOR-1": make_ballot(
                    core,
                    "DISAGREE",
                    "The evidence does not yet support the motion.",
                ),
                "BALTHASAR-2": make_ballot(
                    core,
                    "CONDITIONAL",
                    "Proceed only with enforceable safeguards.",
                    ["Retain a human appeal path."],
                ),
                "CASPER-3": make_ballot(
                    core,
                    "AGREE",
                    "The bounded proposal respects individual agency.",
                ),
            }[core]
            self.ballots_completed.add(core)
            return Generation(ballot, ZERO_USAGE)

        raise AssertionError(f"Unexpected request for {core}: {prompt}")


@pytest.mark.asyncio
async def test_complete_reactive_review_scenario_is_independent_causal_and_atomic():
    from magi.deliberation import deliberate

    fake = ReactiveScenarioAsk()
    events = []

    async def consume():
        async for event in deliberate(
            Motion(question="Should the bounded pilot proceed?", quorum="majority"),
            ask=fake,
        ):
            events.append(event)
            if event.type == "act" and event.id == 4:
                fake.challenge_committed.set()
            elif event.type == "act" and event.id == 5:
                fake.response_committed.set()
            elif event.type == "act" and event.id == 6:
                fake.condition_committed.set()

    run = asyncio.create_task(consume())
    await asyncio.wait_for(fake.all_openings_started.wait(), timeout=1)
    for core in ("CASPER-3", "MELCHIOR-1", "BALTHASAR-2"):
        fake.opening_releases[core].set()
        await asyncio.wait_for(fake.opening_completed[core].wait(), timeout=1)
    await asyncio.wait_for(run, timeout=2)

    acts = [event for event in events if event.type == "act"]
    assert fake.opening_completion_order == ["CASPER-3", "MELCHIOR-1", "BALTHASAR-2"]
    assert [event.act.core for event in acts[:3]] == list(CORE_ORDER)
    assert [event.seen_through_event_id for event in acts[:3]] == [0, 0, 0]
    assert all("SHARED REVIEW RECORD" not in prompt for prompt in fake.opening_prompts.values())
    assert {versions[0] for versions in fake.review_versions.values()} == {3}

    public_reviews = acts[3:]
    assert [event.act.core for event in public_reviews] == [
        "CASPER-3",
        "MELCHIOR-1",
        "BALTHASAR-2",
    ]
    assert [event.seen_through_event_id for event in public_reviews] == [3, 4, 5]
    assert [event.act.reply_to for event in public_reviews] == [None, 4, 5]
    assert [event.act.core for event in public_reviews] != list(CORE_ORDER)

    melchior_ready = next(
        index
        for index, event in enumerate(events)
        if event.type == "core_status"
        and event.core == "MELCHIOR-1"
        and event.status == "READY"
    )
    challenge = next(
        index for index, event in enumerate(events) if event.type == "act" and event.id == 4
    )
    assert melchior_ready < challenge
    assert all(
        any(
            event.type == "core_status"
            and event.core == core
            and event.status == "READY"
            and event.reviewed_through_event_id == 6
            for event in events
        )
        for core in CORE_ORDER
    )

    lock_index = next(
        index for index, event in enumerate(events) if event.type == "ballots_locked"
    )
    result_index = next(index for index, event in enumerate(events) if event.type == "result")
    assert fake.ballots_started == set(CORE_ORDER)
    assert fake.ballots_completed == set(CORE_ORDER)
    assert lock_index < result_index
    assert all("ballots" not in event.model_dump() for event in events[:result_index])

    result = events[result_index]
    assert result.quorum == "majority"
    assert result.recommendation == "APPROVED_WITH_CONDITIONS"
    assert result.outcome == "APPROVED_WITH_CONDITIONS"
    assert [ballot.vote for ballot in result.ballots] == [
        "DISAGREE",
        "CONDITIONAL",
        "AGREE",
    ]
    assert next(ballot for ballot in result.ballots if ballot.core == "MELCHIOR-1").vote == "DISAGREE"


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

    assert [event.type for event in events] == [
        "phase",
        "core_status",
        "core_status",
        "core_status",
        "error",
    ]
    assert [event.core for event in events[1:4]] == list(CORE_ORDER)
    assert all(event.status == "THINKING" for event in events[1:4])
    assert not any(event.type == "act" for event in events)
    assert secret not in events[-1].message
