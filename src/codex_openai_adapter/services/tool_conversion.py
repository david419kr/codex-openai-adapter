from __future__ import annotations

from collections import deque
import json
from typing import Any
from uuid import uuid4

from codex_openai_adapter.schemas.openai import ChatMessage, ChatMessageToolCall


def normalize_function_arguments(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments
    if arguments is None:
        return "{}"
    return json.dumps(arguments, separators=(",", ":"))


def parse_function_arguments(arguments: str) -> Any:
    stripped = arguments.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return arguments


def convert_chat_tool_call_to_ollama(tool_call: Any, *, index: int | None = None) -> dict[str, Any]:
    function_payload = {
        "name": tool_call.function.name,
        "arguments": parse_function_arguments(tool_call.function.arguments),
    }
    if index is not None:
        function_payload["index"] = index

    payload: dict[str, Any] = {
        "type": "function",
        "function": function_payload,
    }
    if tool_call.id is not None:
        payload["id"] = tool_call.id
    return payload


def convert_chat_tool_calls_to_ollama(tool_calls: list[Any] | None) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return None
    return [
        convert_chat_tool_call_to_ollama(tool_call, index=index)
        for index, tool_call in enumerate(tool_calls)
    ]


def convert_chat_tools_to_responses(tools: list[Any] | None) -> list[Any]:
    converted_tools: list[Any] = []
    for tool in tools or []:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            converted_tools.append(tool)
            continue

        function_obj = tool.get("function") if isinstance(tool.get("function"), dict) else None
        name = (function_obj or {}).get("name") or tool.get("name")
        if name is None:
            converted_tools.append(tool)
            continue

        converted: dict[str, Any] = {"type": "function", "name": name}
        description = (function_obj or {}).get("description") or tool.get("description")
        parameters = (function_obj or {}).get("parameters") or tool.get("parameters")
        strict = (function_obj or {}).get("strict") or tool.get("strict")
        if description is not None:
            converted["description"] = description
        if parameters is not None:
            converted["parameters"] = parameters
        if strict is not None:
            converted["strict"] = strict
        converted_tools.append(converted)

    return converted_tools


def convert_tool_choice(tool_choice: Any) -> Any:
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        name = tool_choice.get("name")
        function_obj = tool_choice.get("function")
        if name is None and isinstance(function_obj, dict):
            name = function_obj.get("name")
        if name is not None:
            return {"type": "function", "name": name}
    return tool_choice if tool_choice is not None else "auto"


def assistant_tool_calls_to_input(
    tool_calls: list[ChatMessageToolCall] | None,
    pending_ids: deque[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool_call in tool_calls or []:
        if tool_call.call_type and tool_call.call_type.lower() != "function":
            continue
        call_id = tool_call.id or f"call_{uuid4()}"
        pending_ids.append(call_id)
        items.append(
            {
                "type": "function_call",
                "id": None,
                "call_id": call_id,
                "name": tool_call.function.name,
                "arguments": normalize_function_arguments(tool_call.function.arguments),
            }
        )
    return items


def tool_message_to_output(
    message: ChatMessage,
    pending_ids: deque[str],
    output: str,
) -> dict[str, Any]:
    call_id = message.tool_call_id or (pending_ids.popleft() if pending_ids else None)
    if call_id is None:
        call_id = f"call_{uuid4()}"
    return {"type": "function_call_output", "call_id": call_id, "output": output}
