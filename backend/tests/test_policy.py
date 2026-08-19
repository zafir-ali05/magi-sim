from magi.models import Ballot
from magi.policy import reduce_ballots


MELCHIOR = "MELCHIOR-1"
BALTHASAR = "BALTHASAR-2"
CASPER = "CASPER-3"


def ballot(core, vote, *, conditions=None):
    return Ballot(
        core=core,
        vote=vote,
        confidence=0.8,
        rationale=f"{core} rationale",
        conditions=conditions or [],
    )


def agree(core):
    return ballot(core, "AGREE")


def conditional(core, *conditions):
    return ballot(
        core,
        "CONDITIONAL",
        conditions=list(conditions) or ["run a reversible pilot"],
    )


def disagree(core):
    return ballot(core, "DISAGREE")


def test_majority_preserves_conditional_support_and_dissent():
    decision = reduce_ballots(
        "majority",
        [agree(MELCHIOR), conditional(BALTHASAR), disagree(CASPER)],
    )

    assert decision.recommendation == "APPROVED_WITH_CONDITIONS"
    assert decision.outcome == "APPROVED_WITH_CONDITIONS"
    assert not decision.requires_human_confirmation


def test_majority_rejects_when_fewer_than_two_cores_support():
    decision = reduce_ballots(
        "majority",
        [agree(MELCHIOR), disagree(BALTHASAR), disagree(CASPER)],
    )

    assert decision.recommendation == "REJECTED"
    assert decision.outcome == "REJECTED"
    assert not decision.requires_human_confirmation


def test_unanimous_does_not_treat_conditional_as_unconditional_approval():
    decision = reduce_ballots(
        "unanimous",
        [agree(MELCHIOR), conditional(BALTHASAR), agree(CASPER)],
    )

    assert decision.recommendation == "APPROVED_WITH_CONDITIONS"
    assert decision.outcome == "HUMAN_CONFIRMATION_REQUIRED"
    assert decision.requires_human_confirmation


def test_unanimous_rejects_dissent_even_when_majority_recommends_approval():
    decision = reduce_ballots(
        "unanimous",
        [agree(MELCHIOR), agree(BALTHASAR), disagree(CASPER)],
    )

    assert decision.recommendation == "APPROVED"
    assert decision.outcome == "REJECTED"
    assert not decision.requires_human_confirmation


def test_unanimous_approves_three_unconditional_votes():
    decision = reduce_ballots(
        "unanimous",
        [agree(MELCHIOR), agree(BALTHASAR), agree(CASPER)],
    )

    assert decision.recommendation == "APPROVED"
    assert decision.outcome == "APPROVED"
    assert not decision.requires_human_confirmation


def test_human_confirm_never_marks_even_unanimous_support_executable():
    decision = reduce_ballots(
        "human_confirm",
        [agree(MELCHIOR), agree(BALTHASAR), agree(CASPER)],
    )

    assert decision.recommendation == "APPROVED"
    assert decision.outcome == "HUMAN_CONFIRMATION_REQUIRED"
    assert decision.requires_human_confirmation


def test_missing_or_duplicate_core_is_incomplete():
    missing = reduce_ballots("majority", [agree(MELCHIOR), agree(BALTHASAR)])
    duplicate = reduce_ballots(
        "majority",
        [agree(MELCHIOR), agree(MELCHIOR), agree(CASPER)],
    )

    assert missing.outcome == "INCOMPLETE"
    assert missing.recommendation == "INCOMPLETE"
    assert missing.requires_human_confirmation
    assert duplicate.outcome == "INCOMPLETE"
    assert duplicate.recommendation == "INCOMPLETE"
    assert duplicate.requires_human_confirmation


def test_conditions_are_deduplicated_in_core_order():
    decision = reduce_ballots(
        "majority",
        [
            conditional(MELCHIOR, "audit", "publish"),
            conditional(BALTHASAR, "publish", "appeal"),
            disagree(CASPER),
        ],
    )

    assert decision.conditions == ("audit", "publish", "appeal")


def test_input_order_does_not_change_the_decision_or_condition_order():
    ballots = [
        conditional(MELCHIOR, "audit"),
        conditional(BALTHASAR, "appeal"),
        disagree(CASPER),
    ]

    assert reduce_ballots("majority", ballots) == reduce_ballots(
        "majority",
        list(reversed(ballots)),
    )
