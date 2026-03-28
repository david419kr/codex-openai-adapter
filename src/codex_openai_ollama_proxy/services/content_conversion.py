from __future__ import annotations

from collections import deque
from typing import Any

from codex_openai_ollama_proxy.core.config import DEFAULT_SYSTEM_INSTRUCTIONS
from codex_openai_ollama_proxy.schemas.openai import ChatMessage
from codex_openai_ollama_proxy.services.tool_conversion import (
    assistant_tool_calls_to_input,
    tool_message_to_output,
)


def extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        collected: list[str] = []
        for value in content:
            if isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str):
                    collected.append(text)
            elif isinstance(value, str):
                collected.append(value)
        return " ".join(collected)
    if content is None:
        return ""
    return str(content)


def _text_item(text: str, is_assistant: bool) -> dict[str, Any] | None:
    if not text.strip():
        return None
    return {
        "type": "output_text" if is_assistant else "input_text",
        "text": text,
    }


def _parse_image_part(part: dict[str, Any]) -> dict[str, Any] | None:
    image_url_obj = part.get("image_url") if isinstance(part.get("image_url"), dict) else None

    detail = part.get("detail")
    if not isinstance(detail, str) and image_url_obj is not None:
        nested_detail = image_url_obj.get("detail")
        detail = nested_detail if isinstance(nested_detail, str) else None

    image_url = part.get("image_url") if isinstance(part.get("image_url"), str) else None
    if image_url is None and image_url_obj is not None:
        nested_url = image_url_obj.get("url")
        image_url = nested_url if isinstance(nested_url, str) else None
    if image_url is None:
        for key in ("url", "image"):
            value = part.get(key)
            if isinstance(value, str):
                image_url = value
                break

    file_id = part.get("file_id") if isinstance(part.get("file_id"), str) else None

    image_base64 = part.get("image_base64")
    if image_url is None and isinstance(image_base64, str):
        mime_type = part.get("mime_type") if isinstance(part.get("mime_type"), str) else "image/png"
        image_url = f"data:{mime_type};base64,{image_base64}"

    if image_url is None and file_id is None:
        return None

    payload: dict[str, Any] = {"type": "input_image"}
    if image_url is not None:
        payload["image_url"] = image_url
    if file_id is not None:
        payload["file_id"] = file_id
    if isinstance(detail, str):
        payload["detail"] = detail
    return payload


def parse_chat_content_items(content: Any, is_assistant: bool) -> list[dict[str, Any]]:
    if isinstance(content, str):
        item = _text_item(content, is_assistant)
        return [item] if item else []

    if isinstance(content, list):
        items: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, str):
                item = _text_item(part, is_assistant)
                if item:
                    items.append(item)
                continue

            if isinstance(part, dict):
                part_type = part.get("type") if isinstance(part.get("type"), str) else ""
                is_image_part = part_type in {"image_url", "input_image", "image"} or any(
                    key in part for key in ("image_url", "image_base64", "file_id")
                )
                if not is_assistant and is_image_part:
                    image_item = _parse_image_part(part)
                    if image_item is not None:
                        items.append(image_item)
                        continue

                text = part.get("text")
                if not isinstance(text, str):
                    content_value = part.get("content")
                    text = content_value if isinstance(content_value, str) else None
                if text is not None:
                    item = _text_item(text, is_assistant)
                    if item:
                        items.append(item)
                    continue

                fallback = extract_content_text(part)
                item = _text_item(fallback, is_assistant)
                if item:
                    items.append(item)
                continue

            fallback = extract_content_text(part)
            item = _text_item(fallback, is_assistant)
            if item:
                items.append(item)
        return items

    if content is None:
        return []

    item = _text_item(str(content), is_assistant)
    return [item] if item else []


def convert_messages_to_input(
    messages: list[ChatMessage],
    default_instructions: str = DEFAULT_SYSTEM_INSTRUCTIONS,
) -> tuple[list[dict[str, Any]], str]:
    input_items: list[dict[str, Any]] = []
    system_instructions: list[str] = []
    pending_tool_call_ids: deque[str] = deque()

    for message in messages:
        role = message.role
        content_text = extract_content_text(message.content)

        if role.lower() == "system":
            if content_text.strip():
                system_instructions.append(content_text)
            continue

        if role.lower() == "assistant":
            assistant_content = parse_chat_content_items(message.content, is_assistant=True)
            if assistant_content:
                input_items.append(
                    {
                        "type": "message",
                        "id": None,
                        "role": role,
                        "content": assistant_content,
                    }
                )
            input_items.extend(
                assistant_tool_calls_to_input(message.tool_calls, pending_tool_call_ids)
            )
            continue

        if role.lower() == "tool":
            input_items.append(
                tool_message_to_output(message, pending_tool_call_ids, content_text)
            )
            continue

        message_content = parse_chat_content_items(message.content, is_assistant=False)
        if message_content:
            input_items.append(
                {
                    "type": "message",
                    "id": None,
                    "role": role,
                    "content": message_content,
                }
            )

    instructions = (
        "\n\n".join(system_instructions) if system_instructions else default_instructions
    )
    return input_items, instructions
