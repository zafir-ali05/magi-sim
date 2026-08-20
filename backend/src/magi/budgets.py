from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .models import CORE_ORDER, CoreId, TokenUsage


@dataclass(frozen=True)
class DiscussionLimits:
    # reviews include PASS and READY, contributions only count published acts
    max_contributions_per_core: int = 3
    max_evaluations_per_core: int = 5
    timeout_seconds: float = 300
    max_total_tokens: int = 180_000


class BudgetLedger:
    def __init__(
        self,
        limits: DiscussionLimits | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits or DiscussionLimits()
        self._clock = clock
        # this starts after the openings, so they do not eat discussion time
        self._started_at = clock()
        self._evaluations = {core: 0 for core in CORE_ORDER}
        self._contributions = {core: 0 for core in CORE_ORDER}
        self._total_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def discussion_expired(self) -> bool:
        elapsed = self._clock() - self._started_at
        return (
            elapsed >= self.limits.timeout_seconds
            or self._total_tokens >= self.limits.max_total_tokens
        )

    def can_evaluate(self, core: CoreId) -> bool:
        return (
            not self.discussion_expired()
            and self._evaluations[core] < self.limits.max_evaluations_per_core
        )

    def can_contribute(self, core: CoreId) -> bool:
        return (
            not self.discussion_expired()
            and self._contributions[core] < self.limits.max_contributions_per_core
        )

    def has_contributed(self, core: CoreId) -> bool:
        return self._contributions[core] > 0

    def remaining_evaluations(self, core: CoreId) -> int:
        return max(0, self.limits.max_evaluations_per_core - self._evaluations[core])

    def remaining_contributions(self, core: CoreId) -> int:
        return max(
            0, self.limits.max_contributions_per_core - self._contributions[core]
        )

    def record_usage(self, usage: TokenUsage) -> None:
        # total_tokens already includes the private reasoning token count
        if any(
            value < 0
            for value in (
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.reasoning_tokens,
                usage.total_tokens,
            )
        ):
            raise ValueError("Token usage cannot contain negative values")
        self._total_tokens += usage.total_tokens

    def record_evaluation(self, core: CoreId, usage: TokenUsage) -> None:
        if self._evaluations[core] >= self.limits.max_evaluations_per_core:
            raise ValueError("Core evaluation budget is exhausted")
        self.record_usage(usage)
        self._evaluations[core] += 1

    def record_contribution(self, core: CoreId) -> None:
        if self._contributions[core] >= self.limits.max_contributions_per_core:
            raise ValueError("Core contribution budget is exhausted")
        self._contributions[core] += 1
