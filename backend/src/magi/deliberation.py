from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, Literal, TypeVar, cast

from .deepseek import ask_deepseek
from .models import (
    Act,
    ActEvent,
    Ballot,
    BallotsLockedEvent,
    CoreId,
    ErrorEvent,
    Motion,
    PhaseEvent,
    ResultEvent,
    StreamEvent,
)
from .prompts import ballot_messages, opening_messages, reaction_messages


CORE_ORDER: tuple[CoreId, ...] = (
    "MELCHIOR-1",
    "BALTHASAR-2",
    "CASPER-3",
)
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
    Awaitable[T],
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
) -> T:
    try:
        value = await ask(core, messages, schema, effort, max_tokens)
    except asyncio.CancelledError:
        raise
    except Exception:
        raise _DeliberationFailure from None
    return _validated(value, schema, core)


async def _gather(
    requests: Sequence[Awaitable[T]],
) -> list[T]:
    responses = await asyncio.gather(*requests, return_exceptions=True)
    for response in responses:
        if isinstance(response, BaseException):
            raise _DeliberationFailure from None
    return cast(list[T], responses)


def _commit(
    transcript: list[ActEvent],
    act: Act,
    *,
    act_id: int,
    round_number: int,
) -> ActEvent:
    event = ActEvent(id=act_id, round=round_number, act=act)
    transcript.append(event)
    return event


def _reduce_ballots(ballots: Sequence[Ballot]) -> Literal[
    "APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED"
]:
    affirmative = sum(ballot.vote in {"AGREE", "CONDITIONAL"} for ballot in ballots)
    if affirmative < 2:
        return "REJECTED"
    if any(ballot.vote == "CONDITIONAL" for ballot in ballots):
        return "APPROVED_WITH_CONDITIONS"
    return "APPROVED"


def _deduplicate_conditions(ballots: Sequence[Ballot]) -> list[str]:
    conditions: list[str] = []
    seen: set[str] = set()
    for ballot in ballots:
        for condition in ballot.conditions:
            if condition not in seen:
                seen.add(condition)
                conditions.append(condition)
    return conditions


async def _run_deliberation(motion: Motion, ask: Ask) -> AsyncIterator[StreamEvent]:
    transcript: list[ActEvent] = []
    next_id = 1

    yield PhaseEvent(phase="OPENING", active_cores=list(CORE_ORDER))
    openings = await _gather(
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
    for act in openings:
        yield _commit(transcript, act, act_id=next_id, round_number=0)
        next_id += 1

    yield PhaseEvent(phase="DISCUSSION", active_cores=list(CORE_ORDER))
    for round_number in range(1, MAX_REACTION_ROUNDS + 1):
        frozen_transcript = tuple(transcript)
        remaining_rounds = MAX_REACTION_ROUNDS - round_number
        reactions = await _gather(
            [
                _request(
                    ask,
                    core,
                    reaction_messages(core, motion, frozen_transcript, remaining_rounds),
                    Act,
                    "high",
                    4096,
                )
                for core in CORE_ORDER
            ]
        )
        for act in reactions:
            yield _commit(
                transcript,
                act,
                act_id=next_id,
                round_number=round_number,
            )
            next_id += 1
        if all(act.kind == "READY" for act in reactions):
            break

    yield PhaseEvent(phase="BALLOTING", active_cores=list(CORE_ORDER))
    frozen_transcript = tuple(transcript)
    ballots = await _gather(
        [
            _request(
                ask,
                core,
                ballot_messages(core, motion, frozen_transcript),
                Ballot,
                "max",
                8192,
            )
            for core in CORE_ORDER
        ]
    )

    yield BallotsLockedEvent()
    yield ResultEvent(
        outcome=_reduce_ballots(ballots),
        ballots=ballots,
        conditions=_deduplicate_conditions(ballots),
        disclaimer=DISCLAIMER,
    )


async def deliberate(
    motion: Motion,
    ask: Ask = ask_deepseek,
) -> AsyncIterator[StreamEvent]:
    """Stream one bounded MAGI deliberation with private final ballots."""

    try:
        async with asyncio.timeout(DELIBERATION_TIMEOUT_SECONDS):
            async for event in _run_deliberation(motion, ask):
                yield event
    except asyncio.CancelledError:
        raise
    except Exception:
        yield ErrorEvent(message=SANITIZED_ERROR_MESSAGE)
