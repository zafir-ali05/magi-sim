from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Literal, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from .models import CoreId, Generation, TokenUsage


T = TypeVar("T", bound=BaseModel)
ATTEMPT_LIMIT = 4


class DeepSeekError(RuntimeError):
    """A provider failure safe to expose to the public API."""


class _AttemptFailure(Exception):
    """Internal failure carrying only a sanitized explanation."""


def _account_usage(response: Any) -> TokenUsage:
    """Read aggregate usage, including private reasoning tokens, then discard it."""

    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage(0, 0, 0, 0)

    aggregate: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, field, 0)
        aggregate[field] = value if isinstance(value, int) else 0

    details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(details, "reasoning_tokens", 0)
    aggregate["reasoning_tokens"] = reasoning_tokens if isinstance(reasoning_tokens, int) else 0
    return TokenUsage(
        prompt_tokens=aggregate["prompt_tokens"],
        completion_tokens=aggregate["completion_tokens"],
        reasoning_tokens=aggregate["reasoning_tokens"],
        total_tokens=aggregate["total_tokens"],
    )


def _response_content(response: Any) -> str:
    try:
        choice = response.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason in {"length", "max_tokens"}:
            raise _AttemptFailure("provider response was truncated")
        content = getattr(choice.message, "content", None)
    except _AttemptFailure:
        raise
    except Exception:
        raise _AttemptFailure("provider returned no usable choice") from None

    if not isinstance(content, str) or not content.strip():
        raise _AttemptFailure("provider returned empty content")
    return content


def _parse_response(content: str, schema: type[T], core: CoreId) -> T:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        raise _AttemptFailure("provider returned invalid JSON") from None

    try:
        result = schema.model_validate(payload)
    except Exception:
        raise _AttemptFailure("provider returned data that failed schema validation") from None

    returned_core = getattr(result, "core", None)
    if returned_core != core:
        raise _AttemptFailure("returned core does not match requested identity")
    return result


def _repair_instruction(schema: type[T], core: CoreId, failure: str) -> str:
    contract = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    return (
        "RETRY: Your previous answer was rejected because "
        f"{failure}. Return exactly one JSON object for core {core}. "
        "Follow this JSON Schema exactly, include every required field, use only allowed "
        f"enum values, and include no additional fields: {contract}"
    )


async def ask_deepseek(
    core: CoreId,
    messages: list[dict[str, str]],
    schema: type[T],
    effort: Literal["high", "max"],
    max_tokens: int,
) -> Generation[T]:
    """Request and validate one public response from an independent MAGI core."""

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise DeepSeekError("DEEPSEEK_API_KEY is not configured")

    client = AsyncOpenAI(
        api_key=key,
        base_url="https://api.deepseek.com",
        max_retries=0,
    )
    usage_totals = TokenUsage(0, 0, 0, 0)
    failure = "provider request failed"
    request_messages = list(messages)

    for attempt in range(ATTEMPT_LIMIT):
        provider_failure = False
        try:
            response = await client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=request_messages,
                reasoning_effort=effort,
                extra_body={"thinking": {"type": "enabled"}},
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
            )
            usage_totals += _account_usage(response)
            result = _parse_response(_response_content(response), schema, core)
            return Generation(result, usage_totals)
        except _AttemptFailure as exc:
            failure = str(exc)
        except Exception:
            # SDK exception text can contain request metadata or secrets. Keep it
            # out of both retry diagnostics and the public exception.
            failure = "provider request failed"
            provider_failure = True

        if attempt + 1 >= ATTEMPT_LIMIT:
            raise DeepSeekError(
                f"DeepSeek request failed after {ATTEMPT_LIMIT} attempts: {failure}"
            ) from None

        if provider_failure:
            await asyncio.sleep(0.25 * (2**attempt))
        request_messages = [
            *messages,
            {
                "role": "user",
                "content": _repair_instruction(schema, core, failure),
            },
        ]
