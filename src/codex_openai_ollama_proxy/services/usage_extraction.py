from __future__ import annotations

from typing import Any

from codex_openai_ollama_proxy.schemas.usage import Usage


def parse_token_count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value) if value.is_integer() or value.is_finite() else None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def usage_from_object(obj: dict[str, Any]) -> Usage | None:
    def pick(*keys: str) -> int | None:
        for key in keys:
            value = parse_token_count(obj.get(key))
            if value is not None:
                return value
        return None

    prompt = pick("prompt_tokens", "input_tokens", "input_text_tokens", "prompt_token_count")
    completion = pick(
        "completion_tokens",
        "output_tokens",
        "output_text_tokens",
        "completion_token_count",
    )
    total = pick("total_tokens", "total_token_count")

    if prompt is None and completion is None and total is None:
        return None

    prompt_tokens = max(prompt if prompt is not None else (total - completion if total is not None and completion is not None else 0), 0)
    completion_tokens = max(completion if completion is not None else (total - prompt if total is not None and prompt is not None else 0), 0)
    total_tokens = max(total if total is not None else prompt_tokens + completion_tokens, 0)

    return Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def find_usage_in_value(value: Any, depth: int) -> Usage | None:
    if depth == 0:
        return None

    if isinstance(value, dict):
        usage_value = value.get("usage")
        if isinstance(usage_value, dict):
            usage = usage_from_object(usage_value)
            if usage is not None:
                return usage

        for child in value.values():
            usage = find_usage_in_value(child, depth - 1)
            if usage is not None:
                return usage
        return None

    if isinstance(value, list):
        for child in value:
            usage = find_usage_in_value(child, depth - 1)
            if usage is not None:
                return usage
        return None

    return None


def extract_usage_from_event(event: dict[str, Any]) -> Usage | None:
    candidates = [
        event.get("usage"),
        event.get("response", {}).get("usage") if isinstance(event.get("response"), dict) else None,
        event.get("item", {}).get("usage") if isinstance(event.get("item"), dict) else None,
        (
            event.get("response", {}).get("metadata", {}).get("usage")
            if isinstance(event.get("response"), dict)
            and isinstance(event.get("response", {}).get("metadata"), dict)
            else None
        ),
    ]

    for candidate in candidates:
        if isinstance(candidate, dict):
            usage = usage_from_object(candidate)
            if usage is not None:
                return usage

    return find_usage_in_value(event, 5)
