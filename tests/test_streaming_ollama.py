from __future__ import annotations

import json
from pathlib import Path

import respx
from fastapi.testclient import TestClient
from httpx import Response

from codex_openai_adapter.app import create_app
from codex_openai_adapter.core.config import Settings


def write_auth_file(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_settings(auth_path: Path) -> Settings:
    return Settings(
        port=8888,
        auth_path=auth_path,
        required_client_api_key=None,
        service_name="codex-openai-adapter",
        service_version="0.1.0",
    )


def test_ollama_streaming_emits_multiple_ndjson_chunks(tmp_path: Path) -> None:
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
                "/api/generate",
                json={"model": "gpt-5.4:latest", "prompt": "hello", "stream": True},
            )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]

    assert len(lines) >= 3
    assert '"response":"Hel"' in lines[0]
    assert '"response":"lo"' in lines[1]
    assert '"done":true' in lines[-1]


def test_ollama_chat_streaming_emits_tool_calls_chunk(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    backend_body = (
        'data: {"type":"response.output_item.done","item":{"type":"function_call","id":"fc_1","call_id":"call_1","name":"list_files","arguments":"{\\"path\\":\\".\\",\\"recursive\\":false}"}}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}\n\n'
        "data: [DONE]\n\n"
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_body)
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "gpt-5.4:latest",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "list_files",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                },
                            },
                        }
                    ],
                },
            )

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]

    assert any('"tool_calls"' in line for line in lines)
    assert any('"name":"list_files"' in line for line in lines)
    assert '"done":true' in lines[-1]


def test_ollama_chat_streaming_emits_incremental_tool_call_snapshots(tmp_path: Path) -> None:
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
                "/api/chat",
                json={
                    "model": "gpt-5.4:latest",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
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
    lines = [line for line in response.text.splitlines() if line.strip()]

    tool_lines = [line for line in lines if '"tool_calls"' in line]
    assert len(tool_lines) >= 2
    assert any('"arguments":{}' in line for line in tool_lines)
    assert any('"arguments":"{\\"path\\""' in line for line in tool_lines)
    assert any('"arguments":{"path":"."}' in line for line in tool_lines)
    assert '"done":true' in lines[-1]
