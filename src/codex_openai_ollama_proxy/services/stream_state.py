from __future__ import annotations

from dataclasses import dataclass, field

from codex_openai_ollama_proxy.schemas.events import (
    StreamEvent,
    TextDeltaEvent,
    TextDoneEvent,
    ToolCallChunkEvent,
    UsageEvent,
)
from codex_openai_ollama_proxy.schemas.openai import ChatToolCall, ChatToolFunction
from codex_openai_ollama_proxy.schemas.usage import Usage


@dataclass(slots=True)
class ToolCallSnapshot:
    item_id: str
    index: int
    tool_call_id: str
    name: str = ""
    arguments: str = ""
    saw_stream_chunk: bool = False

    def to_chat_tool_call(self) -> ChatToolCall:
        return ChatToolCall(
            id=self.tool_call_id,
            type="function",
            function=ChatToolFunction(name=self.name, arguments=self.arguments),
        )


@dataclass(slots=True)
class StreamState:
    text: str = ""
    usage: Usage | None = None
    saw_text_delta: bool = False
    _tool_calls_by_item: dict[str, ToolCallSnapshot] = field(default_factory=dict)

    def apply(self, event: StreamEvent) -> bool:
        if isinstance(event, TextDeltaEvent):
            self.text += event.text
            self.saw_text_delta = True
            return True

        if isinstance(event, TextDoneEvent):
            if self.saw_text_delta:
                return False
            self.text += event.text
            return True

        if isinstance(event, ToolCallChunkEvent):
            snapshot = self._tool_calls_by_item.get(event.item_id)
            if snapshot is None:
                snapshot = ToolCallSnapshot(
                    item_id=event.item_id,
                    index=event.index,
                    tool_call_id=event.tool_call_id,
                )
                self._tool_calls_by_item[event.item_id] = snapshot

            snapshot.index = event.index
            snapshot.tool_call_id = event.tool_call_id
            if event.name is not None:
                snapshot.name = event.name
            snapshot.arguments = event.arguments

            if event.is_final and snapshot.saw_stream_chunk:
                return False

            snapshot.saw_stream_chunk = True
            return True

        if isinstance(event, UsageEvent):
            self.usage = event.usage
            return False

        return False

    @property
    def tool_calls(self) -> list[ChatToolCall]:
        snapshots = sorted(self._tool_calls_by_item.values(), key=lambda snapshot: snapshot.index)
        return [snapshot.to_chat_tool_call() for snapshot in snapshots]

    @property
    def has_any_output(self) -> bool:
        return bool(self.text or self._tool_calls_by_item)

    @property
    def finish_reason(self) -> str:
        return "tool_calls" if self._tool_calls_by_item else "stop"
