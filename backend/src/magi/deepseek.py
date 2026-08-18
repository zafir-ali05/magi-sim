from __future__ import annotations

import json
import os
from typing import Any, Literal, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from .models import CoreId


T = TypeVar("T", bound=BaseModel)


class DeepSeekError(RuntimeError):
    """A provider failure safe to expose to the public API."""


class DeepSeekConfigurationError(DeepSeekError):
    """A missing or invalid provider configuration."""


class _AttemptFailure(Exception):
    """Internal failure carrying only a sanitized explanation."""


def _account_usage(response: Any) -> dict[str, int]:
    """Read aggregate usage, including private reasoning tokens, then discard it."""

    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
        }

    aggregate: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, field, 0)
        aggregate[field] = value if isinstance(value, int) else 0

    details = getattr(usage, "completion_tokens_details", None)
    reasoning_tokens = getattr(details, "reasoning_tokens", 0)
    aggregate["reasoning_tokens"] = reasoning_tokens if isinstance(reasoning_tokens, int) else 0
    return aggregate


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


async def ask_deepseek(
    core: CoreId,
    messages: list[dict[str, str]],
    schema: type[T],
    effort: Literal["high", "max"],
    max_tokens: int,
) -> T:
    """Request and validate one public response from an independent MAGI core."""

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise DeepSeekConfigurationError("DEEPSEEK_API_KEY is not configured")

    client = AsyncOpenAI(api_key=key, base_url="https://api.deepseek.com")
    usage_totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }
    failure = "provider request failed"

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=messages,
                reasoning_effort=effort,
                extra_body={"thinking": {"type": "enabled"}},
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
            )
            for field, value in _account_usage(response).items():
                usage_totals[field] += value
            result = _parse_response(_response_content(response), schema, core)
            return result
        except _AttemptFailure as exc:
            failure = str(exc)
        except Exception:
            # SDK exception text can contain request metadata or secrets. Keep it
            # out of both retry diagnostics and the public exception.
            failure = "provider request failed"

        if attempt == 0:
            continue

        # Keep aggregate usage local to this invocation; reasoning content is
        # deliberately never copied into an exception, model, log, or prompt.
        _ = usage_totals
        raise DeepSeekError(f"DeepSeek request failed after one retry: {failure}") from None

    raise DeepSeekError("DeepSeek request failed after one retry") from None
