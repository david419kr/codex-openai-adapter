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


def backend_sse_body() -> str:
    return (
        'data: {"type":"response.output_text.delta","delta":"Hello from ollama"}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8}}}\n\n'
        "data: [DONE]\n\n"
    )


def backend_tool_call_body() -> str:
    return (
        'data: {"type":"response.output_item.done","item":{"type":"function_call","id":"fc_1","call_id":"call_1","name":"list_files","arguments":"{\\"path\\":\\".\\",\\"recursive\\":false}"}}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8}}}\n\n'
        "data: [DONE]\n\n"
    )


def test_ollama_chat_route(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "gpt-5.4:latest",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "gpt-5.4"
    assert payload["message"]["content"] == "Hello from ollama"


def test_ollama_chat_route_forwards_tools_and_returns_tool_calls(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    request_tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        }
    ]

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_tool_call_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                    "tools": request_tools,
                },
            )

    assert response.status_code == 200
    payload = response.json()
    backend_payload = json.loads(route.calls.last.request.content.decode("utf-8"))

    assert backend_payload["tools"][0]["type"] == "function"
    assert backend_payload["tools"][0]["name"] == "list_files"
    assert payload["message"]["content"] == ""
    assert payload["message"]["tool_calls"][0]["type"] == "function"
    assert payload["message"]["tool_calls"][0]["function"]["name"] == "list_files"
    assert payload["message"]["tool_calls"][0]["function"]["arguments"] == {
        "path": ".",
        "recursive": False,
    }


def test_ollama_chat_think_false_maps_to_none_reasoning(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                    "think": False,
                },
            )

    assert response.status_code == 200
    backend_payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert backend_payload["reasoning"] == {"effort": "none"}


def test_ollama_generate_think_xhigh_maps_to_backend_reasoning(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/generate",
                json={
                    "model": "gpt-5.3-codex",
                    "prompt": "hello",
                    "think": "xhigh",
                },
            )

    assert response.status_code == 200
    backend_payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert backend_payload["reasoning"] == {"effort": "xhigh"}


def test_ollama_chat_think_true_maps_to_medium_reasoning(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                    "think": True,
                },
            )

    assert response.status_code == 200
    backend_payload = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert backend_payload["reasoning"] == {"effort": "medium"}


def test_ollama_generate_route_streaming(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/generate",
                json={
                    "model": "gpt-5.4:latest",
                    "prompt": "hello",
                    "stream": True,
                },
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert '"done":true' in response.text


def test_ollama_non_streaming_validation_error_maps_to_ollama_error(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/generate",
            json={"model": "gpt-5.4:latest"},
        )

    assert response.status_code == 400
    assert "missing prompt or messages" in response.json()["error"]


def test_ollama_streaming_validation_error_maps_to_ndjson_error(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/generate",
            json={"model": "gpt-5.4:latest", "stream": True},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert '"error":"proxy error: missing prompt or messages"' in response.text


def test_ollama_invalid_think_value_rejected(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hello"}],
                "think": "invalid",
            },
        )

    assert response.status_code == 422
    assert "think must be one of" in response.text
