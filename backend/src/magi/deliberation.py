from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, Literal, TypeVar, cast

from .budgets import BudgetLedger, DiscussionLimits
from .deepseek import Generation, TokenUsage, ask_deepseek
from .models import (
    CORE_ORDER,
    Act,
    Ballot,
    BallotsLockedEvent,
    CoreId,
    ErrorEvent,
    Motion,
    PhaseEvent,
    ResultEvent,
    StreamEvent,
)
from .policy import reduce_ballots
from .prompts import ballot_messages, opening_messages, reaction_messages
from .transcript import Transcript


MAX_REACTION_ROUNDS = 3
DELIBERATION_TIMEOUT_SECONDS = 5 * 60
SANITIZED_ERROR_MESSAGE = "Deliberation could not be completed."
DISCLAIMER = (
    "Decision support only; this simulation does not make decisions or take real-world actions."
)


class _DeliberationFailure(Exception):
    """Internal marker for provider and public-model failures."""


T = TypeVar("T", Act, Ballot)
Ask = Callable[
    [CoreId, list[dict[str, str]], type[T], Literal["high", "max"], int],
    Awaitable[Generation[T]],
]


def _validated(value: Any, schema: type[T], core: CoreId) -> T:
    try:
        result = schema.model_validate(value)
    except Exception:
        raise _DeliberationFailure from None

    if result.core != core:
        raise _DeliberationFailure
    return result


async def _request(
    ask: Ask,
    core: CoreId,
    messages: list[dict[str, str]],
    schema: type[T],
    effort: Literal["high", "max"],
    max_tokens: int,
) -> Generation[T]:
    try:
        generation = await ask(core, messages, schema, effort, max_tokens)
    except asyncio.CancelledError:
        raise
    except Exception:
        raise _DeliberationFailure from None
    if not isinstance(generation, Generation) or not isinstance(generation.usage, TokenUsage):
        raise _DeliberationFailure
    return Generation(_validated(generation.value, schema, core), generation.usage)


async def _gather(
    requests: Sequence[Awaitable[Generation[T]]],
) -> list[Generation[T]]:
    responses = await asyncio.gather(*requests, return_exceptions=True)
    for response in responses:
        if isinstance(response, BaseException):
            raise _DeliberationFailure from None
    return cast(list[Generation[T]], responses)


async def _run_deliberation(
    motion: Motion,
    ask: Ask,
    limits: DiscussionLimits,
) -> AsyncIterator[StreamEvent]:
    transcript = Transcript()

    yield PhaseEvent(phase="OPENING", active_cores=list(CORE_ORDER))
    opening_generations = await _gather(
        [
            _request(
                ask,
                core,
                opening_messages(core, motion),
                Act,
                "high",
                4096,
            )
            for core in CORE_ORDER
        ]
    )
    budgets = BudgetLedger(limits)
    for generation in opening_generations:
        budgets.record_usage(generation.usage)
        act = generation.value
        yield transcript.append(act, seen_through_event_id=0)

    yield PhaseEvent(phase="DISCUSSION", active_cores=list(CORE_ORDER))
    for round_number in range(1, MAX_REACTION_ROUNDS + 1):
        if budgets.discussion_expired():
            break
        eligible_cores = [core for core in CORE_ORDER if budgets.can_evaluate(core)]
        if not eligible_cores:
            break

        frozen_transcript = transcript.snapshot()
        remaining_rounds = MAX_REACTION_ROUNDS - round_number
        reaction_generations = await _gather(
            [
                _request(
                    ask,
                    core,
                    reaction_messages(core, motion, frozen_transcript.events, remaining_rounds),
                    Act,
                    "high",
                    4096,
                )
                for core in eligible_cores
            ]
        )
        reactions: list[Act] = []
        for core, generation in zip(eligible_cores, reaction_generations, strict=True):
            budgets.record_evaluation(core, generation.usage)
            act = generation.value
            reactions.append(act)
            if (
                act.kind not in {"PASS", "READY"}
                and budgets.remaining_contributions(core) > 0
            ):
                budgets.record_contribution(core)
                yield transcript.append(
                    act,
                    seen_through_event_id=frozen_transcript.version,
                )
        if len(reactions) == len(CORE_ORDER) and all(
            act.kind == "READY" for act in reactions
        ):
            break

    yield PhaseEvent(phase="BALLOTING", active_cores=list(CORE_ORDER))
    frozen_transcript = transcript.freeze()
    ballot_generations = await _gather(
        [
            _request(
                ask,
                core,
                ballot_messages(core, motion, frozen_transcript.events),
                Ballot,
                "max",
                8192,
            )
            for core in CORE_ORDER
        ]
    )
    for generation in ballot_generations:
        budgets.record_usage(generation.usage)
    ballots = [generation.value for generation in ballot_generations]
    decision = reduce_ballots(motion.quorum, ballots)

    yield BallotsLockedEvent()
    yield ResultEvent(
        quorum=motion.quorum,
        recommendation=decision.recommendation,
        outcome=decision.outcome,
        requires_human_confirmation=decision.requires_human_confirmation,
        ballots=ballots,
        conditions=list(decision.conditions),
        disclaimer=DISCLAIMER,
    )


async def deliberate(
    motion: Motion,
    ask: Ask = ask_deepseek,
    limits: DiscussionLimits | None = None,
) -> AsyncIterator[StreamEvent]:
    """Stream one bounded MAGI deliberation with private final ballots."""

    try:
        async with asyncio.timeout(DELIBERATION_TIMEOUT_SECONDS):
            async for event in _run_deliberation(
                motion,
                ask,
                limits or DiscussionLimits(),
            ):
                yield event
    except asyncio.CancelledError:
        raise
    except Exception:
        yield ErrorEvent(message=SANITIZED_ERROR_MESSAGE)
