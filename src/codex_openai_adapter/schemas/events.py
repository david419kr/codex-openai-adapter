from __future__ import annotations

from dataclasses import dataclass

from .usage import Usage


@dataclass(slots=True)
class TextDeltaEvent:
    text: str


@dataclass(slots=True)
class TextDoneEvent:
    text: str


@dataclass(slots=True)
class ToolCallChunkEvent:
    item_id: str
    index: int
    tool_call_id: str
    name: str | None
    arguments: str
    arguments_delta: str = ""
    is_final: bool = False


@dataclass(slots=True)
class UsageEvent:
    usage: Usage


@dataclass(slots=True)
class ErrorEvent:
    message: str


StreamEvent = TextDeltaEvent | TextDoneEvent | ToolCallChunkEvent | UsageEvent | ErrorEvent
