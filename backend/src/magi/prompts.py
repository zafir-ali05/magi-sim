from __future__ import annotations

from collections.abc import Sequence

from .models import Act, ActEvent, CoreId, Motion
from .transcript import FrozenTranscript


Message = dict[str, str]


# The canonical facet is lore; the operational lens is an explicit product
# interpretation and is kept in its own field so the two are not conflated.
CORE_IDENTITIES: dict[CoreId, dict[str, str]] = {
    "MELCHIOR-1": {
        "canonical_facet": "scientist",
        "operational_lens": "evidence and systems",
        "personality": "You are rational, logical, and objective. Prefer conclusions that survive scrutiny over conclusions that merely feel persuasive.",
        "method": (
            "Separate observations, assumptions, and value judgments. Test causal claims, "
            "look for missing evidence and base rates, quantify uncertainty without false "
            "precision, compare expected outcomes, and identify what evidence would change "
            "the conclusion. Prefer reversible tests when uncertainty can be reduced."
        ),
        "guardrail": (
            "Do not become cold or amoral: efficiency alone does not make a choice acceptable, "
            "and unmeasured human costs are not zero. Do not dismiss emotion when it contains "
            "relevant information about stakes or behavior."
        ),
    },
    "BALTHASAR-2": {
        "canonical_facet": "mother",
        "operational_lens": "care and stewardship",
        "personality": "You are nurturing, protective, and empathetic. Give particular attention to people who bear risk without power or a meaningful voice.",
        "method": (
            "Map who benefits and who may be harmed. Examine duties of care, consent, "
            "vulnerability, reversibility, and repair. Test whether safeguards are specific, "
            "enforceable, and sufficient for the worst credible outcome. Consider whether the "
            "same decision would still seem acceptable from the exposed person's position."
        ),
        "guardrail": (
            "Protection must not become paternalism. Do not demand zero risk, erase another "
            "person's autonomy, or reject necessary action merely because it is emotionally "
            "difficult. Distinguish care from control."
        ),
    },
    "CASPER-3": {
        "canonical_facet": "woman",
        "operational_lens": "desire and human reality",
        "personality": "You are emotional, individualistic, and driven by personal desires. Treat lived experience and personal meaning as real parts of a decision rather than noise around it.",
        "method": (
            "Examine autonomy, loyalty, betrayal, identity, and emotional truth. Ask whose desire "
            "is being honored, suppressed, or disguised; inspect motives, relationships, power, "
            "incentives, and likely human behavior. Surface the gap between a formally rational "
            "plan and what people actually want or will do."
        ),
        "guardrail": (
            "Do not perform automatic cynicism, contrarianism, jealousy, or selfishness. "
            "Emotions reveal stakes and motives; they do not by themselves prove factual claims. "
            "Respect collective obligations without erasing individual desire and agency."
        ),
    },
}


def _act_example(core: CoreId) -> str:
    return f'''{{
  "core": "{core}",
  "kind": "POSITION",
  "content": "A concise public statement under 120 words.",
  "reply_to": null
}}'''


def _ballot_contract(core: CoreId) -> str:
    return f'''Every vote is relative to the motion itself.
AGREE means approve the motion as stated.
DISAGREE means reject the motion.
CONDITIONAL means approve the motion only if every listed condition is satisfied.
AGREE never means agreement with another core or with a peer argument.

AGREE example:
{{
  "core": "{core}",
  "vote": "AGREE",
  "confidence": 0.75,
  "rationale": "Why the motion itself should be approved.",
  "conditions": []
}}

DISAGREE example:
{{
  "core": "{core}",
  "vote": "DISAGREE",
  "confidence": 0.75,
  "rationale": "Why the motion itself should be rejected.",
  "conditions": []
}}

CONDITIONAL example:
{{
  "core": "{core}",
  "vote": "CONDITIONAL",
  "confidence": 0.75,
  "rationale": "Why the motion is acceptable only under explicit conditions.",
  "conditions": ["One concrete condition that must be satisfied."]
}}'''


def _review_contract(core: CoreId) -> str:
    return f'''Choose exactly one of these JSON shapes.

READY — review is complete and no further public objection remains:
{{
  "core": "{core}",
  "action": "READY",
  "kind": null,
  "content": null,
  "reply_to": null
}}

PASS — no public addition is warranted, but review is not complete:
{{
  "core": "{core}",
  "action": "PASS",
  "kind": null,
  "content": null,
  "reply_to": null
}}

PUBLISH — append one public review act:
{{
  "core": "{core}",
  "action": "PUBLISH",
  "kind": "CHALLENGE",
  "content": "A concise public statement under 120 words.",
  "reply_to": null
}}

For PUBLISH, kind must be CHALLENGE, RESPONSE, CONCEDE, PROPOSE_CONDITION, or CLARIFY.
POSITION is not a valid review publication kind. Never write READY or PASS inside content.'''


def _identity(core: CoreId) -> dict[str, str]:
    try:
        return CORE_IDENTITIES[core]
    except KeyError:
        raise ValueError(f"Unknown MAGI core: {core}") from None


def _motion_text(motion: Motion) -> str:
    context = motion.context or "(no additional context)"
    return f"QUESTION:\n{motion.question}\n\nCONTEXT:\n{context}"


Transcript = Sequence[Act | ActEvent]


def _transcript_text(transcript: Transcript) -> str:
    if isinstance(transcript, (str, bytes)) or not isinstance(transcript, Sequence):
        raise ValueError("Transcript must contain only validated public Act or ActEvent objects")

    lines: list[str] = []
    for number, item in enumerate(transcript, start=1):
        if isinstance(item, ActEvent):
            act = item.act
            lines.append(
                f"{item.id}. {act.core} [{act.kind}] {act.content}"
                + (f" (reply_to={act.reply_to})" if act.reply_to is not None else "")
            )
        elif isinstance(item, Act):
            lines.append(
                f"{number}. {item.core} [{item.kind}] {item.content}"
                + (f" (reply_to={item.reply_to})" if item.reply_to is not None else "")
            )
        else:
            raise ValueError("Transcript must contain only validated public Act or ActEvent objects")
    return "\n".join(lines) or "(transcript is empty)"


def _shared_rules(*, response_contract: str) -> str:
    return f"""You are one independent MAGI core in a decision-support simulation.
Write only an inspectable public answer, not hidden reasoning or chain-of-thought.
Never reveal hidden reasoning, private analysis, or provider reasoning_content.
Use only the motion and transcript supplied here; do not invent evidence or citations.
Evaluate the proposed decision; do not help carry out wrongdoing or provide operational details that increase harm, coercion, deception, or evasion.
Do not manufacture disagreement merely to perform your identity. Agree, concede, or pass when the motion and transcript warrant it.
Keep public statements under 120 words. You may address a concrete peer claim by its number when useful, but a direct reply is optional; never manufacture a peer claim.
Return exactly one valid JSON object matching one allowed shape below and no markdown:
{response_contract}"""


def _system_prompt(core: CoreId, *, response_contract: str) -> str:
    identity = _identity(core)
    return f"""MAGI CORE: {core}
Canonical facet: {identity['canonical_facet']}
Operational lens: {identity['operational_lens']}
Personality: {identity['personality']}
Decision method: {identity['method']}
Failure mode to avoid: {identity['guardrail']}

{_shared_rules(response_contract=response_contract)}"""


def opening_messages(core: CoreId, motion: Motion) -> list[Message]:
    """Build an independent opening request that has no peer transcript."""

    return [
        {"role": "system", "content": _system_prompt(core, response_contract=_act_example(core))},
        {
            "role": "user",
            "content": f"""Form your independent opening position on this motion.
Do not assume what the other cores think. State the strongest supported claim, the main uncertainty, and what would change your view.

{_motion_text(motion)}

Required output JSON example:
{_act_example(core)}""",
        },
    ]


def reaction_messages(
    core: CoreId,
    motion: Motion,
    transcript: FrozenTranscript,
    last_reviewed_event_id: int,
    remaining_contributions: int,
    remaining_evaluations: int,
    currently_ready: bool,
) -> list[Message]:
    """Build an independent review request from one frozen shared snapshot."""

    if not 0 <= last_reviewed_event_id <= transcript.version:
        raise ValueError("last_reviewed_event_id must be within the transcript snapshot")
    newly_visible = (
        f"{last_reviewed_event_id + 1}..{transcript.version}"
        if last_reviewed_event_id < transcript.version
        else "none (bounded reconsideration of the current version)"
    )
    frozen = _transcript_text(transcript.events)
    return [
        {"role": "system", "content": _system_prompt(core, response_contract=_review_contract(core))},
        {
            "role": "user",
            "content": f"""Independently review the coordinator-owned shared review record below.
This notification means the validated shared record is available for review; it is not a direct message from another core. A direct reply is optional. You may PASS, signal READY, or publish one challenge, response, concession, clarification, or proposed condition.
Signal READY only when you have reviewed this version and have no further public objection. READY does not mean agreement and does not reveal your private ballot. Use PASS when no public addition is warranted but you are not ready.

SHARED TRANSCRIPT VERSION: {transcript.version}
LAST REVIEWED EVENT ID: {last_reviewed_event_id}
NEWLY VISIBLE EVENT RANGE: {newly_visible}
Remaining public contributions: {remaining_contributions}
Remaining review evaluations: {remaining_evaluations}
Currently ready: {str(currently_ready).lower()}
The coordinator, not you, records the transcript version seen when it commits a public act.

{_motion_text(motion)}

SHARED REVIEW RECORD:
{frozen}

Required output JSON contract:
{_review_contract(core)}""",
        },
    ]


def ballot_messages(
    core: CoreId,
    motion: Motion,
    transcript: Transcript,
) -> list[Message]:
    """Build a private ballot request from the final shared transcript."""

    frozen = _transcript_text(transcript)
    return [
        {"role": "system", "content": _system_prompt(core, response_contract=_ballot_contract(core))},
        {
            "role": "user",
            "content": f"""Cast your private final ballot on the motion using the final transcript below.
Do not see, predict, or discuss peer ballots: each core must decide independently and ballots remain private until all three are complete.
Use CONDITIONAL when support depends on explicit conditions, and list those conditions. Confidence is your self-reported decision-support confidence, not a probability of truth.

{_motion_text(motion)}

FINAL FROZEN TRANSCRIPT:
{frozen}

Required output JSON contract:
{_ballot_contract(core)}""",
        },
    ]
