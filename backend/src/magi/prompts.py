from __future__ import annotations

from collections.abc import Sequence

from .models import Act, ActEvent, CoreId, Motion


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


def _ballot_example(core: CoreId) -> str:
    return f'''{{
  "core": "{core}",
  "vote": "AGREE",
  "confidence": 0.75,
  "rationale": "A concise decision-support rationale.",
  "conditions": []
}}'''


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


def _shared_rules(*, response_example: str) -> str:
    return f"""You are one independent MAGI core in a decision-support simulation.
Write only an inspectable public answer, not hidden reasoning or chain-of-thought.
Never reveal hidden reasoning, private analysis, or provider reasoning_content.
Use only the motion and transcript supplied here; do not invent evidence or citations.
Evaluate the proposed decision; do not help carry out wrongdoing or provide operational details that increase harm, coercion, deception, or evasion.
Do not manufacture disagreement merely to perform your identity. Agree, concede, or pass when the motion and transcript warrant it.
Keep public statements under 120 words. Address a concrete peer claim by its number when peer claims are present; never manufacture a peer claim.
Return exactly one valid JSON object matching this example and no markdown:
{response_example}"""


def _system_prompt(core: CoreId, *, response_example: str) -> str:
    identity = _identity(core)
    return f"""MAGI CORE: {core}
Canonical facet: {identity['canonical_facet']}
Operational lens: {identity['operational_lens']}
Personality: {identity['personality']}
Decision method: {identity['method']}
Failure mode to avoid: {identity['guardrail']}

{_shared_rules(response_example=response_example)}"""


def opening_messages(core: CoreId, motion: Motion) -> list[Message]:
    """Build an independent opening request that has no peer transcript."""

    return [
        {"role": "system", "content": _system_prompt(core, response_example=_act_example(core))},
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
    transcript: Transcript,
    remaining_rounds: int,
) -> list[Message]:
    """Build a reaction request from one numbered, frozen transcript snapshot."""

    frozen = _transcript_text(transcript)
    return [
        {"role": "system", "content": _system_prompt(core, response_example=_act_example(core))},
        {
            "role": "user",
            "content": f"""Review the motion and the numbered frozen transcript below.
This is the only peer material visible to you for this round; respond to a concrete claim when one requires challenge, response, concession, clarification, or a condition.
There are {remaining_rounds} reaction round(s) remaining after this request. Signal READY only when you can ballot without a material unresolved objection; use PASS if no substantive addition is warranted.

{_motion_text(motion)}

FROZEN TRANSCRIPT:
{frozen}

Required output JSON example:
{_act_example(core)}""",
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
        {"role": "system", "content": _system_prompt(core, response_example=_ballot_example(core))},
        {
            "role": "user",
            "content": f"""Cast your private final ballot on the motion using the final transcript below.
Do not see, predict, or discuss peer ballots: each core must decide independently and ballots remain private until all three are complete.
Use CONDITIONAL when support depends on explicit conditions, and list those conditions. Confidence is your self-reported decision-support confidence, not a probability of truth.

{_motion_text(motion)}

FINAL FROZEN TRANSCRIPT:
{frozen}

Required output JSON example:
{_ballot_example(core)}""",
        },
    ]
