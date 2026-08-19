import pytest

from magi.budgets import BudgetLedger, DiscussionLimits
from magi.deepseek import TokenUsage


CORE = "MELCHIOR-1"
USAGE = TokenUsage(
    prompt_tokens=1,
    completion_tokens=2,
    reasoning_tokens=1,
    total_tokens=3,
)


def limits(**overrides):
    values = {
        "max_contributions_per_core": 3,
        "max_evaluations_per_core": 5,
        "timeout_seconds": 300,
        "max_total_tokens": 100,
    }
    values.update(overrides)
    return DiscussionLimits(**values)


def test_fourth_contribution_is_refused_without_affecting_other_cores():
    ledger = BudgetLedger(limits())

    for _ in range(3):
        ledger.record_contribution(CORE)

    assert not ledger.can_contribute(CORE)
    assert ledger.remaining_contributions(CORE) == 0
    assert ledger.can_contribute("CASPER-3")
    with pytest.raises(ValueError, match="contribution budget"):
        ledger.record_contribution(CORE)


def test_sixth_evaluation_is_refused_and_usage_is_not_double_counted():
    ledger = BudgetLedger(limits())

    for _ in range(5):
        ledger.record_evaluation(CORE, USAGE)

    assert not ledger.can_evaluate(CORE)
    assert ledger.remaining_evaluations(CORE) == 0
    assert ledger.total_tokens == 15
    with pytest.raises(ValueError, match="evaluation budget"):
        ledger.record_evaluation(CORE, USAGE)
    assert ledger.total_tokens == 15


def test_total_token_exhaustion_ends_discussion():
    ledger = BudgetLedger(limits(max_total_tokens=6))

    ledger.record_usage(USAGE)
    assert not ledger.discussion_expired()
    ledger.record_usage(USAGE)

    assert ledger.discussion_expired()


def test_completed_in_flight_evaluation_is_recorded_after_global_expiry():
    ledger = BudgetLedger(limits(max_total_tokens=3))

    ledger.record_evaluation("MELCHIOR-1", USAGE)
    assert ledger.discussion_expired()
    ledger.record_evaluation("BALTHASAR-2", USAGE)

    assert ledger.total_tokens == 6
    assert ledger.remaining_evaluations("BALTHASAR-2") == 4


def test_completed_in_flight_contribution_is_recorded_after_global_expiry():
    ledger = BudgetLedger(limits(max_total_tokens=3))

    ledger.record_usage(USAGE)
    assert ledger.discussion_expired()
    ledger.record_contribution(CORE)

    assert ledger.remaining_contributions(CORE) == 2


def test_monotonic_deadline_ends_discussion():
    now = [100.0]
    ledger = BudgetLedger(limits(timeout_seconds=5), clock=lambda: now[0])

    now[0] = 104.99
    assert not ledger.discussion_expired()
    now[0] = 105.0
    assert ledger.discussion_expired()


@pytest.mark.parametrize(
    "usage",
    [
        TokenUsage(-1, 0, 0, 0),
        TokenUsage(0, -1, 0, 0),
        TokenUsage(0, 0, -1, 0),
        TokenUsage(0, 0, 0, -1),
    ],
)
def test_negative_usage_is_rejected(usage):
    ledger = BudgetLedger(limits())

    with pytest.raises(ValueError, match="negative"):
        ledger.record_usage(usage)


def test_unknown_core_is_rejected():
    ledger = BudgetLedger(limits())

    with pytest.raises(ValueError, match="Unknown MAGI core"):
        ledger.can_evaluate("UNKNOWN")
