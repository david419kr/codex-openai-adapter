from codex_openai_ollama_proxy.services.tool_conversion import (
    convert_chat_tools_to_responses,
    convert_tool_choice,
    normalize_function_arguments,
)


def test_convert_chat_tools_to_responses() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read file contents",
                "parameters": {"type": "object"},
            },
        }
    ]

    converted = convert_chat_tools_to_responses(tools)

    assert converted == [
        {
            "type": "function",
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {"type": "object"},
        }
    ]


def test_convert_tool_choice() -> None:
    tool_choice = {"type": "function", "function": {"name": "read_file"}}
    assert convert_tool_choice(tool_choice) == {"type": "function", "name": "read_file"}


def test_normalize_function_arguments() -> None:
    assert normalize_function_arguments(None) == "{}"
    assert normalize_function_arguments({"path": "README.md"}) == '{"path":"README.md"}'
