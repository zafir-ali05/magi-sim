from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .budgets import DiscussionLimits
from .coordinator import Ask, ReactiveCoordinator
from .deepseek import ask_deepseek
from .models import ErrorEvent, Motion, StreamEvent

DELIBERATION_TIMEOUT_SECONDS = 5 * 60
SANITIZED_ERROR_MESSAGE = "Deliberation could not be completed."


async def deliberate(
    motion: Motion,
    ask: Ask = ask_deepseek,
    limits: DiscussionLimits | None = None,
) -> AsyncIterator[StreamEvent]:
    """Stream one bounded event-driven MAGI deliberation."""

    try:
        async with asyncio.timeout(DELIBERATION_TIMEOUT_SECONDS):
            coordinator = ReactiveCoordinator(ask, limits=limits)
            async for event in coordinator.run(motion):
                yield event
    except asyncio.CancelledError:
        raise
    except Exception:
        yield ErrorEvent(message=SANITIZED_ERROR_MESSAGE)
