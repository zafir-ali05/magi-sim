from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import (
    CORE_ORDER,
    Ballot,
    DecisionOutcome,
    DecisionPolicy,
    Recommendation,
)


@dataclass(frozen=True)
class PolicyDecision:
    recommendation: Recommendation
    outcome: DecisionOutcome
    requires_human_confirmation: bool
    conditions: tuple[str, ...]


def reduce_ballots(
    policy: DecisionPolicy,
    ballots: Sequence[Ballot],
) -> PolicyDecision:
    by_core = {ballot.core: ballot for ballot in ballots}
    if len(ballots) != len(CORE_ORDER) or set(by_core) != set(CORE_ORDER):
        return PolicyDecision("INCOMPLETE", "INCOMPLETE", True, ())

    ordered = tuple(by_core[core] for core in CORE_ORDER)
    conditions = tuple(
        dict.fromkeys(
            condition
            for ballot in ordered
            for condition in ballot.conditions
        )
    )
    affirmative = sum(ballot.vote in {"AGREE", "CONDITIONAL"} for ballot in ordered)
    if affirmative < 2:
        recommendation: Recommendation = "REJECTED"
    elif any(ballot.vote == "CONDITIONAL" for ballot in ordered):
        recommendation = "APPROVED_WITH_CONDITIONS"
    else:
        recommendation = "APPROVED"

    if policy == "human_confirm":
        return PolicyDecision(
            recommendation,
            "HUMAN_CONFIRMATION_REQUIRED",
            True,
            conditions,
        )
    if policy == "unanimous":
        if all(ballot.vote == "AGREE" for ballot in ordered):
            return PolicyDecision(recommendation, "APPROVED", False, conditions)
        if any(ballot.vote == "DISAGREE" for ballot in ordered):
            return PolicyDecision(recommendation, "REJECTED", False, conditions)
        return PolicyDecision(
            recommendation,
            "HUMAN_CONFIRMATION_REQUIRED",
            True,
            conditions,
        )
    return PolicyDecision(recommendation, recommendation, False, conditions)
