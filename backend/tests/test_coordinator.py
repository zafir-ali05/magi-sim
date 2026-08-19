import asyncio
import re
from collections import defaultdict

import pytest

from magi.budgets import DiscussionLimits
from magi.coordinator import CoordinatorFailure, ReactiveCoordinator
from magi.deepseek import Generation, TokenUsage
from magi.models import CORE_ORDER, Act, Ballot, Motion


ZERO_USAGE = TokenUsage(0, 0, 0, 0)


def make_act(core, kind, content=None, *, reply_to=None):
    return Act(
        core=core,
        kind=kind,
        content=content or f"{kind.lower()} from {core}",
        reply_to=reply_to,
    )


def make_ballot(core, vote="AGREE"):
    return Ballot(
        core=core,
        vote=vote,
        confidence=0.8,
        rationale=f"private ballot from {core}",
        conditions=[],
    )


def prompt_version(prompt):
    match = re.search(r"SHARED TRANSCRIPT VERSION: (\d+)", prompt)
    assert match is not None
    return int(match.group(1))


def prompt_last_reviewed(prompt):
    match = re.search(r"LAST REVIEWED EVENT ID: (\d+)", prompt)
    assert match is not None
    return int(match.group(1))


async def collect(coordinator, motion=None, *, on_event=None):
    events = []
    async for event in coordinator.run(motion or Motion(question="Should it proceed?")):
        events.append(event)
        if on_event is not None:
            on_event(event)
    return events


class FunctionalAsk:
    def __init__(self, *, opening=None, reaction=None, ballot=None):
        self.opening = opening or self._opening
        self.reaction = reaction or self._reaction
        self.ballot = ballot or self._ballot
        self.opening_usage = ZERO_USAGE
        self.reaction_usage = ZERO_USAGE
        self.ballot_usage = ZERO_USAGE
        self.opening_prompts = {}
        self.reaction_calls = defaultdict(int)
        self.reaction_versions = defaultdict(list)
        self.reaction_prompts = defaultdict(list)
        self.reaction_active = defaultdict(int)
        self.max_reaction_active = defaultdict(int)
        self.ballot_calls = []
        self.ballot_completed = []
        self.cancelled_reactions = set()

    async def _opening(self, core, prompt):
        return make_act(core, "POSITION", f"opening from {core}")

    async def _reaction(self, core, call_number, version, prompt):
        return make_act(core, "READY")

    async def _ballot(self, core, prompt):
        return make_ballot(core)

    async def __call__(self, core, messages, schema, effort, max_tokens):
        prompt = messages[1]["content"]
        if schema is Act and "Form your independent opening" in prompt:
            self.opening_prompts[core] = prompt
            value = await self.opening(core, prompt)
            return Generation(value, self.opening_usage)

        if schema is Act and "coordinator-owned shared review record" in prompt:
            self.reaction_calls[core] += 1
            call_number = self.reaction_calls[core]
            version = prompt_version(prompt)
            self.reaction_versions[core].append(version)
            self.reaction_prompts[core].append(prompt)
            self.reaction_active[core] += 1
            self.max_reaction_active[core] = max(
                self.max_reaction_active[core],
                self.reaction_active[core],
            )
            try:
                value = await self.reaction(core, call_number, version, prompt)
            except asyncio.CancelledError:
                self.cancelled_reactions.add(core)
                raise
            finally:
                self.reaction_active[core] -= 1
            return Generation(value, self.reaction_usage)

        if schema is Ballot and "Cast your private final ballot" in prompt:
            self.ballot_calls.append(core)
            try:
                value = await self.ballot(core, prompt)
            finally:
                self.ballot_completed.append(core)
            return Generation(value, self.ballot_usage)

        raise AssertionError(f"Unexpected provider request for {core}: {prompt}")


@pytest.mark.asyncio
async def test_openings_commit_atomically_in_core_order_after_all_finish():
    releases = {core: asyncio.Event() for core in CORE_ORDER}
    completed = {core: asyncio.Event() for core in CORE_ORDER}
    all_started = asyncio.Event()
    started = set()
    completion_order = []

    async def opening(core, prompt):
        started.add(core)
        if started == set(CORE_ORDER):
            all_started.set()
        await releases[core].wait()
        completion_order.append(core)
        completed[core].set()
        return make_act(core, "POSITION", f"opening from {core}")

    fake = FunctionalAsk(opening=opening)
    coordinator = ReactiveCoordinator(fake, review_debounce_seconds=0)
    run = asyncio.create_task(collect(coordinator))

    await asyncio.wait_for(all_started.wait(), timeout=1)
    for core in ("CASPER-3", "MELCHIOR-1", "BALTHASAR-2"):
        releases[core].set()
        await asyncio.wait_for(completed[core].wait(), timeout=1)

    events = await asyncio.wait_for(run, timeout=1)
    openings = [event for event in events if event.type == "act"][:3]

    assert started == set(CORE_ORDER)
    assert completion_order == ["CASPER-3", "MELCHIOR-1", "BALTHASAR-2"]
    assert [event.act.core for event in openings] == list(CORE_ORDER)
    assert [event.id for event in openings] == [1, 2, 3]
    assert all(event.seen_through_event_id == 0 for event in openings)
    assert all("SHARED REVIEW RECORD" not in prompt for prompt in fake.opening_prompts.values())
    assert {versions[0] for versions in fake.reaction_versions.values()} == {3}

    discussion_phase_index = next(
        index
        for index, event in enumerate(events)
        if event.type == "phase" and event.phase == "DISCUSSION"
    )
    pre_discussion = events[:discussion_phase_index]
    for core in CORE_ORDER:
        assert any(
            event.type == "core_status"
            and event.core == core
            and event.status == "THINKING"
            for event in pre_discussion
        )
        speaking_index = next(
            index
            for index, event in enumerate(pre_discussion)
            if event.type == "core_status"
            and event.core == core
            and event.status == "SPEAKING"
        )
        opening_index = next(
            index
            for index, event in enumerate(pre_discussion)
            if event.type == "act" and event.act.core == core
        )
        assert speaking_index < opening_index


@pytest.mark.asyncio
async def test_invalid_opening_kind_exposes_no_partial_opening_snapshot():
    async def opening(core, prompt):
        kind = "READY" if core == "BALTHASAR-2" else "POSITION"
        return make_act(core, kind, f"opening from {core}")

    fake = FunctionalAsk(opening=opening)
    events = []

    with pytest.raises(CoordinatorFailure):
        async for event in ReactiveCoordinator(fake, review_debounce_seconds=0).run(
            Motion(question="Should it proceed?")
        ):
            events.append(event)

    assert [event.type for event in events] == [
        "phase",
        "core_status",
        "core_status",
        "core_status",
    ]
    assert [event.core for event in events[1:]] == list(CORE_ORDER)
    assert all(event.status == "THINKING" for event in events[1:])
    assert not any(event.type == "act" for event in events)


@pytest.mark.asyncio
async def test_pass_ready_and_optional_public_act_are_independent_review_outcomes():
    async def reaction(core, call_number, version, prompt):
        if call_number == 1:
            return {
                "MELCHIOR-1": make_act(core, "READY"),
                "BALTHASAR-2": make_act(core, "PASS"),
                "CASPER-3": make_act(core, "CHALLENGE", reply_to=None),
            }[core]
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    public_acts = [event for event in events if event.type == "act"]

    assert [event.act.core for event in public_acts[:3]] == list(CORE_ORDER)
    assert [event.act.core for event in public_acts[3:]] == ["CASPER-3"]
    assert public_acts[3].act.reply_to is None
    assert public_acts[3].seen_through_event_id == 3
    assert all(event.act.kind not in {"PASS", "READY"} for event in public_acts)
    assert any(event.type == "result" for event in events)

    statuses = [event for event in events if event.type == "core_status"]
    for core in CORE_ORDER:
        assert any(event.core == core and event.status == "THINKING" for event in statuses)
    casper_speaking_index = next(
        index
        for index, event in enumerate(events)
        if event.type == "core_status"
        and event.core == "CASPER-3"
        and event.status == "SPEAKING"
    )
    casper_act_index = next(
        index
        for index, event in enumerate(events)
        if event.type == "act" and event.id == 4
    )
    assert casper_speaking_index < casper_act_index


@pytest.mark.asyncio
async def test_notification_arriving_in_flight_is_reviewed_by_the_same_single_worker():
    casper_started = asyncio.Event()
    release_casper = asyncio.Event()

    async def reaction(core, call_number, version, prompt):
        if core == "CASPER-3" and call_number == 1:
            casper_started.set()
            await release_casper.wait()
            return make_act(core, "PASS")
        if core == "MELCHIOR-1" and call_number == 1:
            await casper_started.wait()
            return make_act(core, "CHALLENGE", reply_to=1)
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)

    def release_after_peer_act(event):
        if event.type == "act" and event.id == 4:
            release_casper.set()

    events = await asyncio.wait_for(
        collect(
            ReactiveCoordinator(fake, review_debounce_seconds=0),
            on_event=release_after_peer_act,
        ),
        timeout=1,
    )

    assert fake.reaction_versions["CASPER-3"][:2] == [3, 4]
    assert fake.max_reaction_active["CASPER-3"] == 1
    assert any(event.type == "result" for event in events)


@pytest.mark.asyncio
async def test_concurrent_public_acts_do_not_claim_unseen_intervening_events_as_reviewed():
    responders_started = set()
    release_responders = asyncio.Event()

    async def reaction(core, call_number, version, prompt):
        if core in {"MELCHIOR-1", "CASPER-3"} and call_number == 1:
            responders_started.add(core)
            if len(responders_started) == 2:
                release_responders.set()
            await release_responders.wait()
            return make_act(core, "CHALLENGE", reply_to=1)
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    reactions = [event for event in events if event.type == "act"][3:]
    later_core = next(event.act.core for event in reactions if event.id == 5)
    second_prompt = fake.reaction_prompts[later_core][1]

    assert prompt_version(second_prompt) == 5
    assert prompt_last_reviewed(second_prompt) == 3


@pytest.mark.asyncio
async def test_optional_causal_chain_uses_only_visible_event_ids():
    casper_challenged = asyncio.Event()
    melchior_responded = asyncio.Event()

    async def reaction(core, call_number, version, prompt):
        if core == "CASPER-3" and version == 3:
            casper_challenged.set()
            return make_act(core, "CHALLENGE", reply_to=None)
        if core == "MELCHIOR-1" and version < 4:
            await casper_challenged.wait()
            return make_act(core, "PASS")
        if core == "MELCHIOR-1" and version < 6:
            if not melchior_responded.is_set():
                melchior_responded.set()
                return make_act(core, "RESPONSE", reply_to=4)
            return make_act(core, "PASS")
        if core == "BALTHASAR-2" and version < 5:
            await melchior_responded.wait()
            return make_act(core, "PASS")
        if core == "BALTHASAR-2" and version == 5:
            return make_act(core, "PROPOSE_CONDITION", reply_to=5)
        if version < 6:
            return make_act(core, "PASS")
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await asyncio.wait_for(
        collect(ReactiveCoordinator(fake, review_debounce_seconds=0.001)),
        timeout=2,
    )
    acts = [event for event in events if event.type == "act"]
    reactions = acts[3:]

    assert [event.act.core for event in reactions] == [
        "CASPER-3",
        "MELCHIOR-1",
        "BALTHASAR-2",
    ]
    assert [event.seen_through_event_id for event in reactions] == [3, 4, 5]
    assert [event.act.reply_to for event in reactions] == [None, 4, 5]
    assert all(
        event.act.reply_to is None or event.act.reply_to <= event.seen_through_event_id
        for event in reactions
    )


@pytest.mark.asyncio
async def test_pass_retries_are_bounded_by_the_per_core_evaluation_budget():
    async def reaction(core, call_number, version, prompt):
        if core == "MELCHIOR-1":
            return make_act(core, "PASS")
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))

    assert fake.reaction_calls["MELCHIOR-1"] == 5
    assert fake.reaction_calls["BALTHASAR-2"] == 1
    assert fake.reaction_calls["CASPER-3"] == 1
    assert any(
        event.type == "core_status"
        and event.core == "MELCHIOR-1"
        and event.status == "BUDGET_EXHAUSTED"
        for event in events
    )
    assert any(event.type == "result" for event in events)


@pytest.mark.asyncio
async def test_fourth_public_contribution_is_not_committed():
    async def reaction(core, call_number, version, prompt):
        if core == "CASPER-3":
            return make_act(core, "CLARIFY", f"contribution {call_number}")
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    casper_acts = [
        event for event in events if event.type == "act" and event.act.core == "CASPER-3"
    ]

    assert len(casper_acts) == 4  # opening plus three public reactions
    assert fake.reaction_calls["CASPER-3"] == 4
    assert any(
        event.type == "core_status"
        and event.core == "CASPER-3"
        and event.status == "BUDGET_EXHAUSTED"
        for event in events
    )


@pytest.mark.asyncio
async def test_total_token_expiry_waits_for_in_flight_accounting_then_ballots():
    async def reaction(core, call_number, version, prompt):
        return make_act(core, "PASS")

    fake = FunctionalAsk(reaction=reaction)
    fake.reaction_usage = TokenUsage(1, 3, 1, 4)
    limits = DiscussionLimits(max_total_tokens=10)
    events = await collect(
        ReactiveCoordinator(fake, limits=limits, review_debounce_seconds=0)
    )

    assert dict(fake.reaction_calls) == {core: 1 for core in CORE_ORDER}
    assert set(fake.ballot_calls) == set(CORE_ORDER)
    assert any(event.type == "result" for event in events)


@pytest.mark.asyncio
async def test_ready_is_review_completion_not_ballot_agreement():
    async def ballot(core, prompt):
        return make_ballot(core, "DISAGREE" if core == "CASPER-3" else "AGREE")

    fake = FunctionalAsk(ballot=ballot)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    result = next(event for event in events if event.type == "result")

    assert fake.reaction_calls["CASPER-3"] == 1
    assert next(ballot for ballot in result.ballots if ballot.core == "CASPER-3").vote == "DISAGREE"


@pytest.mark.asyncio
async def test_failed_review_core_blocks_ballots_and_returns_incomplete():
    async def reaction(core, call_number, version, prompt):
        if core == "CASPER-3":
            raise RuntimeError("private provider failure")
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    events = await collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    result = next(event for event in events if event.type == "result")

    assert fake.ballot_calls == []
    assert result.recommendation == "INCOMPLETE"
    assert result.outcome == "INCOMPLETE"
    assert result.requires_human_confirmation
    assert result.ballots == []


@pytest.mark.asyncio
async def test_ballot_failure_waits_for_peers_and_reveals_no_partial_votes():
    release_peers = asyncio.Event()
    ballot_started = {core: asyncio.Event() for core in CORE_ORDER}
    casper_failed = asyncio.Event()

    async def ballot(core, prompt):
        ballot_started[core].set()
        if core == "CASPER-3":
            casper_failed.set()
            raise RuntimeError("private ballot failure")
        await release_peers.wait()
        return make_ballot(core)

    fake = FunctionalAsk(ballot=ballot)
    run = asyncio.create_task(
        collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    )

    await asyncio.wait_for(casper_failed.wait(), timeout=1)
    await asyncio.gather(*(event.wait() for event in ballot_started.values()))
    assert not run.done()
    release_peers.set()
    events = await asyncio.wait_for(run, timeout=1)
    result = next(event for event in events if event.type == "result")

    assert set(fake.ballot_completed) == set(CORE_ORDER)
    assert result.outcome == "INCOMPLETE"
    assert result.ballots == []


@pytest.mark.asyncio
async def test_cancellation_stops_every_in_flight_worker():
    never_release = asyncio.Event()
    all_started = asyncio.Event()
    started = set()

    async def reaction(core, call_number, version, prompt):
        started.add(core)
        if started == set(CORE_ORDER):
            all_started.set()
        await never_release.wait()
        return make_act(core, "READY")

    fake = FunctionalAsk(reaction=reaction)
    run = asyncio.create_task(
        collect(ReactiveCoordinator(fake, review_debounce_seconds=0))
    )
    await asyncio.wait_for(all_started.wait(), timeout=1)

    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    assert fake.cancelled_reactions == set(CORE_ORDER)
