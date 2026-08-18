import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from magi.deepseek import DeepSeekError, ask_deepseek
from magi.models import Act, ActEvent, Ballot, Motion
from magi.prompts import ballot_messages, reaction_messages


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
    assert result == Probe(core="MELCHIOR-1", content="ok")


@pytest.mark.asyncio
async def test_malformed_response_is_retried_once(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    client = configured_client(provider_response("not-json"))
    client.chat.completions.create.side_effect = [
        provider_response("not-json"),
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

    assert result.content == "recovered"
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_second_failure_is_sanitized(monkeypatch):
    secret = "sk-test-secret"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    client = configured_client(provider_response("not-json", reasoning=secret))
    client.chat.completions.create.side_effect = [
        RuntimeError(f"provider leaked {secret} reasoning_content"),
        provider_response("still-not-json", reasoning=secret),
    ]

    with patch("magi.deepseek.AsyncOpenAI", return_value=client):
        with pytest.raises(DeepSeekError) as caught:
            await ask_deepseek("BALTHASAR-2", [], Probe, "max", 8192)

    assert secret not in str(caught.value)
    assert "reasoning_content" not in str(caught.value)
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_returned_core_must_match_requested_identity(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    client = configured_client(
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "wrong core"}))
    )
    client.chat.completions.create.side_effect = [
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "wrong core"})),
        provider_response(json.dumps({"core": "BALTHASAR-2", "content": "still wrong"})),
    ]

    with patch("magi.deepseek.AsyncOpenAI", return_value=client):
        with pytest.raises(DeepSeekError) as caught:
            await ask_deepseek("MELCHIOR-1", [], Probe, "high", 4096)

    assert "core" in str(caught.value).lower()
    assert "BALTHASAR-2" not in str(caught.value)
    assert client.chat.completions.create.await_count == 2


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
    transcript = [
        Act(core="MELCHIOR-1", kind="POSITION", content="first claim"),
        ActEvent(
            id=2,
            round=1,
            act=Act(core="BALTHASAR-2", kind="CHALLENGE", content="second claim"),
        ),
    ]

    prompt = reaction_messages("CASPER-3", motion, transcript, 2)[1]["content"]

    assert "1. MELCHIOR-1 [POSITION] first claim" in prompt
    assert "2. BALTHASAR-2 [CHALLENGE] second claim" in prompt
