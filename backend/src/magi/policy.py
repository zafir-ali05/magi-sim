from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import (
    CORE_ORDER,
    Ballot,
    DecisionOutcome,
)


@dataclass(frozen=True)
class PolicyDecision:
    outcome: DecisionOutcome
    conditions: tuple[str, ...]


def reduce_ballots(
    ballots: Sequence[Ballot],
) -> PolicyDecision:
    by_core = {ballot.core: ballot for ballot in ballots}
    if len(ballots) != len(CORE_ORDER) or set(by_core) != set(CORE_ORDER):
        return PolicyDecision("INCOMPLETE", ())

    ordered = tuple(by_core[core] for core in CORE_ORDER)
    # keep the first copy when two ballots use the exact same condition
    conditions = tuple(
        dict.fromkeys(
            condition for ballot in ordered for condition in ballot.conditions
        )
    )
    affirmative = sum(ballot.vote in {"AGREE", "CONDITIONAL"} for ballot in ordered)
    if affirmative < 2:
        outcome: DecisionOutcome = "REJECTED"
    elif any(ballot.vote == "CONDITIONAL" for ballot in ordered):
        outcome = "APPROVED_WITH_CONDITIONS"
    else:
        outcome = "APPROVED"

    return PolicyDecision(outcome, conditions)
