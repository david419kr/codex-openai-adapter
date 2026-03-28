from codex_openai_ollama_proxy.schemas.openai import ChatMessage, ChatMessageToolCall, ChatMessageToolFunction
from codex_openai_ollama_proxy.services.content_conversion import (
    convert_messages_to_input,
    parse_chat_content_items,
)


def test_parse_image_url_content() -> None:
    items = parse_chat_content_items(
        [
            {"type": "text", "text": "Describe this image"},
            {"type": "image_url", "image_url": {"url": "https://example.com/cat.png", "detail": "high"}},
        ],
        is_assistant=False,
    )

    assert {"type": "input_text", "text": "Describe this image"} in items
    assert {
        "type": "input_image",
        "image_url": "https://example.com/cat.png",
        "detail": "high",
    } in items


def test_parse_base64_image_content() -> None:
    items = parse_chat_content_items(
        [{"type": "input_image", "image_base64": "QUJD", "mime_type": "image/jpeg"}],
        is_assistant=False,
    )

    assert items == [{"type": "input_image", "image_url": "data:image/jpeg;base64,QUJD"}]


def test_convert_messages_to_input_infers_tool_call_id() -> None:
    messages = [
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ChatMessageToolCall(
                    id="call_from_assistant",
                    type="function",
                    function=ChatMessageToolFunction(name="list_dir", arguments={"path": "."}),
                )
            ],
        ),
        ChatMessage(role="tool", content="[]"),
    ]

    input_items, instructions = convert_messages_to_input(messages)

    assert any(
        item["type"] == "function_call_output" and item["call_id"] == "call_from_assistant"
        for item in input_items
    )
    assert instructions
