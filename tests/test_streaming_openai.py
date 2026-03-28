from __future__ import annotations

import json
from pathlib import Path

import respx
from fastapi.testclient import TestClient
from httpx import Response

from codex_openai_ollama_proxy.app import create_app
from codex_openai_ollama_proxy.core.config import Settings


def write_auth_file(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_settings(auth_path: Path) -> Settings:
    return Settings(
        port=8888,
        auth_path=auth_path,
        required_client_api_key=None,
        service_name="codex-openai-ollama-proxy",
        service_version="0.1.0",
    )


def test_openai_streaming_preserves_chunk_order(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    backend_body = (
        'data: {"type":"response.output_text.delta","delta":"Hel"}\n\n'
        'data: {"type":"response.output_text.delta","delta":"lo"}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}\n\n'
        "data: [DONE]\n\n"
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_body)
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 200
    body = response.text
    role_index = body.find('"role":"assistant"')
    first_delta_index = body.find('"content":"Hel"')
    second_delta_index = body.find('"content":"lo"')
    final_index = body.find('"finish_reason":"stop"')

    assert role_index != -1
    assert first_delta_index > role_index
    assert second_delta_index > first_delta_index
    assert final_index > second_delta_index
    assert '"total_tokens":6' in body
    assert "data: [DONE]" in body


def test_openai_streaming_emits_tool_call_deltas_before_done(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    backend_body = (
        'data: {"type":"response.output_item.added","item":{"id":"fc_1","type":"function_call","status":"in_progress","arguments":"","call_id":"call_1","name":"list_files"}}\n\n'
        'data: {"type":"response.function_call_arguments.delta","item_id":"fc_1","delta":"{\\"path\\""}\n\n'
        'data: {"type":"response.function_call_arguments.delta","item_id":"fc_1","delta":":\\".\\"}"}\n\n'
        'data: {"type":"response.output_item.done","item":{"id":"fc_1","type":"function_call","call_id":"call_1","name":"list_files","arguments":"{\\"path\\":\\".\\"}"}}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}\n\n'
        "data: [DONE]\n\n"
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_body)
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hello"}],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "list_files",
                                "parameters": {"type": "object"},
                            },
                        }
                    ],
                },
            )

    assert response.status_code == 200
    body = response.text
    assert body.find('"tool_calls":[{"index":0,"function":{"name":"list_files","arguments":""},"id":"call_1","type":"function"}]') != -1
    assert body.find('"tool_calls":[{"index":0,"function":{"arguments":"{\\"path\\""}}]') != -1
    assert body.find('"tool_calls":[{"index":0,"function":{"arguments":":\\".\\"}"}}]') != -1
    assert body.find('"finish_reason":"tool_calls"') > body.find('"tool_calls"')
    assert "data: [DONE]" in body
