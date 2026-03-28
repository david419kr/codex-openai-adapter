from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
import json
from typing import Any
from uuid import uuid4

from codex_openai_ollama_proxy.core.errors import EmptyBackendResponseError
from codex_openai_ollama_proxy.schemas.events import (
    StreamEvent,
    TextDeltaEvent,
    TextDoneEvent,
    ToolCallChunkEvent,
    UsageEvent,
)
from codex_openai_ollama_proxy.schemas.usage import Usage
from codex_openai_ollama_proxy.services.stream_state import StreamState
from codex_openai_ollama_proxy.services.usage_extraction import extract_usage_from_event


@dataclass(slots=True)
class FunctionCallState:
    item_id: str
    index: int
    tool_call_id: str
    name: str
    arguments: str = ""


class BackendEventParser:
    def __init__(self) -> None:
        self._function_calls: dict[str, FunctionCallState] = {}
        self._next_tool_index = 0

    def parse_event(self, event: dict[str, Any]) -> list[StreamEvent]:
        parsed_events: list[StreamEvent] = []

        parsed_usage = extract_usage_from_event(event)
        if parsed_usage is not None:
            parsed_events.append(UsageEvent(parsed_usage))

        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                parsed_events.append(TextDeltaEvent(delta))
            return parsed_events

        if event_type == "response.output_item.added":
            item = event.get("item")
            if isinstance(item, dict):
                tool_event = self._parse_function_call_added(item)
                if tool_event is not None:
                    parsed_events.append(tool_event)
            return parsed_events

        if event_type == "response.function_call_arguments.delta":
            item_id = event.get("item_id")
            delta = event.get("delta")
            if isinstance(item_id, str) and isinstance(delta, str):
                tool_event = self._parse_function_call_delta(item_id, delta)
                if tool_event is not None:
                    parsed_events.append(tool_event)
            return parsed_events

        if event_type == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict):
                tool_event = self._parse_function_call_done(item)
                if tool_event is not None:
                    parsed_events.append(tool_event)
                    return parsed_events

                content_array = item.get("content")
                if isinstance(content_array, list):
                    text_parts: list[str] = []
                    for content_item in content_array:
                        if isinstance(content_item, dict):
                            text = content_item.get("text")
                            if isinstance(text, str):
                                text_parts.append(text)
                    if text_parts:
                        parsed_events.append(TextDoneEvent("".join(text_parts)))

        return parsed_events

    def _parse_function_call_added(self, item: dict[str, Any]) -> ToolCallChunkEvent | None:
        if item.get("type") != "function_call":
            return None

        item_id = item.get("id")
        name = item.get("name")
        if not isinstance(item_id, str) or not isinstance(name, str):
            return None

        call_id = item.get("call_id") or item_id or f"call_{uuid4()}"
        if not isinstance(call_id, str):
            call_id = f"call_{uuid4()}"

        arguments = item.get("arguments")
        if not isinstance(arguments, str):
            arguments = ""

        state = FunctionCallState(
            item_id=item_id,
            index=self._next_tool_index,
            tool_call_id=call_id,
            name=name,
            arguments=arguments,
        )
        self._function_calls[item_id] = state
        self._next_tool_index += 1

        return ToolCallChunkEvent(
            item_id=item_id,
            index=state.index,
            tool_call_id=state.tool_call_id,
            name=state.name,
            arguments=state.arguments,
        )

    def _parse_function_call_delta(
        self, item_id: str, delta: str
    ) -> ToolCallChunkEvent | None:
        state = self._function_calls.get(item_id)
        if state is None:
            return None

        state.arguments += delta
        return ToolCallChunkEvent(
            item_id=item_id,
            index=state.index,
            tool_call_id=state.tool_call_id,
            name=None,
            arguments=state.arguments,
            arguments_delta=delta,
        )

    def _parse_function_call_done(self, item: dict[str, Any]) -> ToolCallChunkEvent | None:
        if item.get("type") != "function_call":
            return None

        item_id = item.get("id")
        name = item.get("name")
        if not isinstance(item_id, str) or not isinstance(name, str):
            return None

        call_id = item.get("call_id") or item_id or f"call_{uuid4()}"
        if not isinstance(call_id, str):
            call_id = f"call_{uuid4()}"

        arguments = item.get("arguments")
        if not isinstance(arguments, str):
            arguments = ""

        state = self._function_calls.get(item_id)
        if state is None:
            state = FunctionCallState(
                item_id=item_id,
                index=self._next_tool_index,
                tool_call_id=call_id,
                name=name,
                arguments=arguments,
            )
            self._function_calls[item_id] = state
            self._next_tool_index += 1
        else:
            state.tool_call_id = call_id
            state.name = name
            state.arguments = arguments

        return ToolCallChunkEvent(
            item_id=item_id,
            index=state.index,
            tool_call_id=state.tool_call_id,
            name=state.name,
            arguments=state.arguments,
            is_final=True,
        )


def iter_events_from_sse_lines(lines: Iterable[str]) -> list[StreamEvent]:
    parser = BackendEventParser()
    events: list[StreamEvent] = []
    for line in lines:
        if not line.startswith("data: "):
            continue
        json_data = line[6:]
        if json_data == "[DONE]":
            break
        try:
            payload = json.loads(json_data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.extend(parser.parse_event(payload))
    return events


async def stream_events_from_sse_lines(lines: AsyncIterator[str]) -> AsyncIterator[StreamEvent]:
    parser = BackendEventParser()
    async for line in lines:
        if not line.startswith("data: "):
            continue
        json_data = line[6:]
        if json_data == "[DONE]":
            break
        try:
            payload = json.loads(json_data)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        for event in parser.parse_event(payload):
            yield event


def parse_backend_sse_text(
    response_text: str,
) -> tuple[str, list[Any], Usage | None]:
    state = StreamState()
    for event in iter_events_from_sse_lines(response_text.splitlines()):
        state.apply(event)

    if not state.has_any_output:
        raise EmptyBackendResponseError(
            "Empty content and no tool calls returned from ChatGPT backend"
        )

    return state.text, list(state.tool_calls), state.usage
