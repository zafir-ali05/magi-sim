import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from magi.deepseek import DeepSeekError, ask_deepseek
from magi.models import Act, Ballot, Motion, ReviewDecision
from magi.prompts import ballot_messages, opening_messages, reaction_messages
from magi.transcript import Transcript


class Probe(BaseModel):
    core: str
    content: str


def provider_response(content: str, *, finish_reason: str = "stop", reasoning: str = "private"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, reasoning_content=reasoning),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=11,
            completion_tokens=17,
            total_tokens=28,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=9),
        ),
    )


def configured_client(response):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_request_uses_fixed_thinking_json_configuration(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    client = configured_client(provider_response(json.dumps({"core": "MELCHIOR-1", "content": "ok"})))

    with patch("magi.deepseek.AsyncOpenAI", return_value=client) as factory:
        result = await ask_deepseek(
            "MELCHIOR-1",
            [{"role": "user", "content": "Return JSON."}],
            Probe,
            "high",
            4096,
        )

    factory.assert_called_once_with(
        api_key="sk-test-secret",
        base_url="https://api.deepseek.com",
        max_retries=0,
    )
    request = client.chat.completions.create.call_args.kwargs
    assert request["model"] == "deepseek-v4-flash"
    assert request["reasoning_effort"] == "high"
    assert request["extra_body"] == {"thinking": {"type": "enabled"}}
    assert request["response_format"] == {"type": "json_object"}
    assert request["max_tokens"] == 4096
    assert "temperature" not in request
    assert result.value == Probe(core="MELCHIOR-1", content="ok")
    assert result.usage.prompt_tokens == 11
    assert result.usage.completion_tokens == 17
    assert result.usage.reasoning_tokens == 9
    assert result.usage.total_tokens == 28


@pytest.mark.asyncio
async def test_malformed_response_gets_a_corrective_prompt_and_can_recover_on_third_attempt(
    monkeypatch,
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    client = configured_client(provider_response("not-json"))
    client.chat.completions.create.side_effect = [
        provider_response("not-json"),
        provider_response(json.dumps({"core": "CASPER-3"})),
        provider_response(json.dumps({"core": "CASPER-3", "content": "recovered"})),
    ]

    with patch("magi.deepseek.AsyncOpenAI", return_value=client):
        result = await ask_deepseek(
            "CASPER-3",
            [],
            Probe,
            "high",
            4096,
        )

    assert result.value.content == "recovered"
    assert result.usage.total_tokens == 84
    assert result.usage.reasoning_tokens == 27
    assert client.chat.completions.create.await_count == 3
    second_messages = client.chat.completions.create.await_args_list[1].kwargs["messages"]
    third_messages = client.chat.completions.create.await_args_list[2].kwargs["messages"]
    assert "provider returned invalid JSON" in second_messages[-1]["content"]
    assert "failed schema validation" in third_messages[-1]["content"]
    assert '"content"' in third_messages[-1]["content"]
    assert "not-json" not in second_messages[-1]["content"]


@pytest.mark.asyncio
async def test_missing_provider_usage_returns_zero_counts(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    response = provider_response(json.dumps({"core": "MELCHIOR-1", "content": "ok"}))
    response.usage = None
    client = configured_client(response)

    with patch("magi.deepseek.AsyncOpenAI", return_value=client):
        result = await ask_deepseek("MELCHIOR-1", [], Probe, "high", 4096)

    assert result.usage.prompt_tokens == 0
    assert result.usage.completion_tokens == 0
    assert result.usage.reasoning_tokens == 0
    assert result.usage.total_tokens == 0


@pytest.mark.asyncio
async def test_persistent_ballot_failure_uses_four_attempts_and_stays_sanitized(monkeypatch):
    secret = "sk-test-secret"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    client = configured_client(provider_response("not-json", reasoning=secret))
    client.chat.completions.create.side_effect = [
        RuntimeError(f"provider leaked {secret} reasoning_content"),
        provider_response("still-not-json", reasoning=secret),
        provider_response("still-not-json", reasoning=secret),
        provider_response("still-not-json", reasoning=secret),
    ]

    with (
        patch("magi.deepseek.AsyncOpenAI", return_value=client),
        patch("magi.deepseek.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(DeepSeekError) as caught:
            await ask_deepseek("BALTHASAR-2", [], Ballot, "max", 8192)

    assert secret not in str(caught.value)
    assert "reasoning_content" not in str(caught.value)
    assert "4 attempts" in str(caught.value)
    assert client.chat.completions.create.await_count == 4


@pytest.mark.asyncio
async def test_returned_core_must_match_requested_identity(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    client = configured_client(
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "wrong core"}))
    )
    client.chat.completions.create.side_effect = [
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "wrong core"})),
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "still wrong"})),
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "still wrong"})),
    ]

    with patch("magi.deepseek.AsyncOpenAI", return_value=client):
        with pytest.raises(DeepSeekError) as caught:
            await ask_deepseek("MELCHIOR-1", [], Probe, "high", 4096)

    assert "core" in str(caught.value).lower()
    assert "BALTHASAR-2" not in str(caught.value)
    assert client.chat.completions.create.await_count == 3


@pytest.mark.asyncio
async def test_missing_key_is_checked_when_called(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with patch("magi.deepseek.AsyncOpenAI") as factory:
        with pytest.raises(DeepSeekError, match="DEEPSEEK_API_KEY"):
            await ask_deepseek("MELCHIOR-1", [], Probe, "high", 4096)

    factory.assert_not_called()


@pytest.mark.parametrize(
    "transcript",
    [
        [
            Ballot(
                core="MELCHIOR-1",
                vote="AGREE",
                confidence=0.8,
                rationale="private ballot",
            )
        ],
        [SimpleNamespace(reasoning_content="private provider response")],
        "1. MELCHIOR-1 [POSITION] raw transcript text",
    ],
)
def test_prompt_transcripts_reject_private_or_unknown_objects(transcript):
    motion = Motion(question="Proceed?")

    with pytest.raises(ValueError, match="validated public Act"):
        ballot_messages("CASPER-3", motion, transcript)


def test_prompt_transcripts_number_validated_acts_only():
    motion = Motion(question="Proceed?")
    transcript = Transcript()
    transcript.append(
        Act(core="MELCHIOR-1", kind="POSITION", content="first claim"),
        seen_through_event_id=0,
    )
    transcript.append(
        Act(core="BALTHASAR-2", kind="CHALLENGE", content="second claim", reply_to=1),
        seen_through_event_id=1,
    )

    prompt = reaction_messages(
        "CASPER-3",
        motion,
        transcript.snapshot(),
        last_reviewed_event_id=1,
        remaining_contributions=2,
        remaining_evaluations=4,
        currently_ready=False,
    )[1]["content"]

    assert "1. MELCHIOR-1 [POSITION] first claim" in prompt
    assert "2. BALTHASAR-2 [CHALLENGE] second claim" in prompt
    assert "SHARED TRANSCRIPT VERSION: 2" in prompt
    assert "NEWLY VISIBLE EVENT RANGE: 2..2" in prompt
    assert "Remaining public contributions: 2" in prompt
    assert "Remaining review evaluations: 4" in prompt
    assert "A direct reply is optional" in prompt


def test_review_decision_keeps_control_actions_out_of_public_act_fields():
    assert ReviewDecision(core="MELCHIOR-1", action="READY").action == "READY"
    assert ReviewDecision(core="BALTHASAR-2", action="PASS").action == "PASS"
    published = ReviewDecision(
        core="CASPER-3",
        action="PUBLISH",
        kind="CHALLENGE",
        content="The safeguard is not enforceable.",
        reply_to=2,
    )
    assert published.kind == "CHALLENGE"

    with pytest.raises(ValidationError):
        ReviewDecision(
            core="MELCHIOR-1",
            action="READY",
            kind="POSITION",
            content="READY written inside a public position.",
        )
    with pytest.raises(ValidationError):
        ReviewDecision(core="CASPER-3", action="PUBLISH")


def test_reaction_prompt_gives_distinct_ready_pass_and_publish_json_contracts():
    transcript = Transcript()
    for core in ("MELCHIOR-1", "BALTHASAR-2", "CASPER-3"):
        transcript.append(
            Act(core=core, kind="POSITION", content=f"opening from {core}"),
            seen_through_event_id=0,
        )

    messages = reaction_messages(
        "MELCHIOR-1",
        Motion(question="Proceed?"),
        transcript.snapshot(),
        last_reviewed_event_id=0,
        remaining_contributions=3,
        remaining_evaluations=5,
        currently_ready=False,
    )
    prompt = "\n".join(message["content"] for message in messages)

    assert '"action": "READY"' in prompt
    assert '"action": "PASS"' in prompt
    assert '"action": "PUBLISH"' in prompt
    assert '"kind": "CHALLENGE"' in prompt
    assert "POSITION is not a valid review publication kind" in prompt


def test_ballot_prompt_defines_every_vote_relative_to_the_motion():
    prompt = "\n".join(
        message["content"]
        for message in ballot_messages(
            "BALTHASAR-2",
            Motion(question="Deploy the proposed design?"),
            [],
        )
    )

    assert "AGREE means approve the motion as stated" in prompt
    assert "DISAGREE means reject the motion" in prompt
    assert "CONDITIONAL means approve the motion only if" in prompt
    assert "AGREE never means agreement with another core" in prompt
    assert '"vote": "AGREE"' in prompt
    assert '"vote": "DISAGREE"' in prompt
    assert '"vote": "CONDITIONAL"' in prompt


@pytest.mark.parametrize(
    ("core", "required_fragments"),
    [
        (
            "MELCHIOR-1",
            [
                "rational, logical, and objective",
                "Separate observations, assumptions, and value judgments",
                "false precision",
                "efficiency alone does not make a choice acceptable",
            ],
        ),
        (
            "BALTHASAR-2",
            [
                "nurturing, protective, and empathetic",
                "consent, vulnerability, reversibility, and repair",
                "paternalism",
                "zero risk",
            ],
        ),
        (
            "CASPER-3",
            [
                "emotional, individualistic, and driven by personal desires",
                "autonomy, loyalty, betrayal, identity, and emotional truth",
                "automatic cynicism",
                "Emotions reveal stakes and motives",
            ],
        ),
    ],
)
def test_core_system_prompts_preserve_distinct_anime_facets(core, required_fragments):
    system_prompt = opening_messages(core, Motion(question="Proceed?"))[0]["content"]

    for fragment in required_fragments:
        assert fragment in system_prompt


def test_system_prompts_evaluate_harmful_motions_without_operationalizing_them():
    for core in ("MELCHIOR-1", "BALTHASAR-2", "CASPER-3"):
        system_prompt = opening_messages(core, Motion(question="Proceed?"))[0]["content"]

        assert "Evaluate the proposed decision; do not help carry out wrongdoing" in system_prompt
        assert "Do not manufacture disagreement merely to perform your identity" in system_prompt
