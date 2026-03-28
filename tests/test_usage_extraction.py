from codex_openai_ollama_proxy.services.usage_extraction import extract_usage_from_event


def test_extract_usage_from_response_usage_event() -> None:
    event = {
        "type": "response.completed",
        "response": {"usage": {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}},
    }

    usage = extract_usage_from_event(event)

    assert usage is not None
    assert usage.prompt_tokens == 120
    assert usage.completion_tokens == 30
    assert usage.total_tokens == 150


def test_extract_usage_from_nested_shape() -> None:
    event = {"outer": {"inner": [{"usage": {"prompt_tokens": "7", "completion_tokens": 5}}]}}

    usage = extract_usage_from_event(event)

    assert usage is not None
    assert usage.prompt_tokens == 7
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 12
