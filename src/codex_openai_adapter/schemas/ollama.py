from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from .openai import ChatMessage


def validate_ollama_think(value: Any) -> bool | str | None:
    if value is None:
        return None
    if value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "false":
            return False
        if normalized == "true":
            return True
        if normalized in {"none", "low", "medium", "high", "xhigh"}:
            return normalized
    raise ValueError("think must be one of: true, false, none, low, medium, high, xhigh")


class OllamaChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage] | None = None
    prompt: str | None = None
    system: str | None = None
    stream: bool | None = None
    think: bool | str | None = None
    tools: list[Any] | None = None
    tool_choice: Any | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("think", mode="before")
    @classmethod
    def _validate_think(cls, value: Any) -> bool | str | None:
        return validate_ollama_think(value)


class OllamaGenerateRequest(BaseModel):
    model: str
    prompt: str | None = None
    system: str | None = None
    stream: bool | None = None
    messages: list[ChatMessage] | None = None
    think: bool | str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("think", mode="before")
    @classmethod
    def _validate_think(cls, value: Any) -> bool | str | None:
        return validate_ollama_think(value)
