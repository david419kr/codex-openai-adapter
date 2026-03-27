from __future__ import annotations

from typing import Any

MODEL_CODEX = "gpt-5.3-codex"
MODEL_GENERAL = "gpt-5.4"
SUPPORTED_BASE_MODELS = (MODEL_GENERAL, MODEL_CODEX)
REASONING_EFFORTS = ("low", "medium", "high", "xhigh")
GPT54_REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh")
OLLAMA_THINK_EFFORTS = ("none", "low", "medium", "high", "xhigh")


def normalize_reasoning_effort(effort: str | None) -> str | None:
    if effort is None:
        return None
    normalized = effort.strip().lower()
    return normalized or None


def normalize_ollama_think(think: bool | str | None) -> str | None:
    if think is None:
        return None
    if think is True:
        return "medium"
    if think is False:
        return "none"
    normalized = normalize_reasoning_effort(think)
    if normalized == "true":
        return "medium"
    if normalized == "false":
        return "none"
    if normalized in OLLAMA_THINK_EFFORTS:
        return normalized
    return None


def supported_reasoning_efforts(model: str) -> tuple[str, ...]:
    if model == MODEL_GENERAL:
        return GPT54_REASONING_EFFORTS
    if model == MODEL_CODEX:
        return REASONING_EFFORTS
    return REASONING_EFFORTS


def normalize_reasoning_effort_for_model(model: str, effort: str | None) -> str | None:
    normalized = normalize_reasoning_effort(effort)
    if normalized is None:
        return None
    return normalized if normalized in supported_reasoning_efforts(model) else None


def extract_reasoning_effort_from_value(reasoning: Any) -> str | None:
    if isinstance(reasoning, str):
        return normalize_reasoning_effort(reasoning)
    if isinstance(reasoning, dict):
        effort = reasoning.get("effort")
        if isinstance(effort, str):
            return normalize_reasoning_effort(effort)
    return None


def resolve_model_alias(model: str) -> tuple[str, str | None]:
    for base_model in SUPPORTED_BASE_MODELS:
        if model == base_model:
            return base_model, None
        prefix = f"{base_model}-"
        if model.startswith(prefix):
            effort = model.removeprefix(prefix)
            normalized = normalize_reasoning_effort_for_model(base_model, effort)
            if normalized is not None:
                return base_model, normalized
    return model, None


def merge_reasoning(reasoning: Any, selected_effort: str | None) -> Any:
    if isinstance(reasoning, dict):
        merged = dict(reasoning)
        merged.pop("effort", None)
        if selected_effort is not None:
            merged["effort"] = selected_effort
        return merged or None

    if selected_effort is None:
        return None

    return {"effort": selected_effort}


def resolve_model_and_reasoning(
    model: str,
    reasoning: Any,
    reasoning_effort: str | None,
) -> tuple[str, Any]:
    backend_model, model_effort = resolve_model_alias(model)
    requested_effort = (
        normalize_reasoning_effort_for_model(backend_model, reasoning_effort)
        or normalize_reasoning_effort_for_model(
            backend_model, extract_reasoning_effort_from_value(reasoning)
        )
        or model_effort
    )
    merged_reasoning = merge_reasoning(reasoning, requested_effort)
    return backend_model, merged_reasoning


def effective_reasoning_is_none(
    request_model: str,
    backend_model: str,
    reasoning: Any,
) -> bool:
    if request_model != MODEL_GENERAL or backend_model != MODEL_GENERAL:
        return False
    return (extract_reasoning_effort_from_value(reasoning) or "none") == "none"


def resolve_temperature(
    request_model: str,
    backend_model: str,
    reasoning: Any,
    temperature: float | None,
) -> float | None:
    if not effective_reasoning_is_none(request_model, backend_model, reasoning):
        return None
    return temperature


def exposed_model_list() -> list[str]:
    models: list[str] = []
    for base_model in SUPPORTED_BASE_MODELS:
        models.append(base_model)
        models.extend(f"{base_model}-{effort}" for effort in REASONING_EFFORTS)
    return models
