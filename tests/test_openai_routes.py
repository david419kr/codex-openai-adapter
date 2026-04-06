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


def build_settings(
    auth_path: Path,
    *,
    debug: bool = False,
    project_root: Path | None = None,
) -> Settings:
    return Settings(
        port=8888,
        auth_path=auth_path,
        required_client_api_key=None,
        debug=debug,
        project_root=project_root or Path.cwd(),
        service_name="codex-openai-ollama-proxy",
        service_version="0.1.0",
    )


def backend_sse_body() -> str:
    return (
        'data: {"type":"response.output_text.delta","delta":"Hello world"}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":5,"output_tokens":2,"total_tokens":7}}}\n\n'
        "data: [DONE]\n\n"
    )


def test_openai_chat_completions_route(tmp_path: Path) -> None:
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
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "gpt-5.4"
    assert payload["choices"][0]["message"]["content"] == "Hello world"
    assert payload["usage"]["total_tokens"] == 7
    assert route.calls.last.request.headers["authorization"] == "Bearer backend_key"


def test_openai_streaming_route_returns_sse(tmp_path: Path) -> None:
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
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: [DONE]" in response.text


def test_openai_responses_passthrough_route_preserves_json_body_and_headers(
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    request_body = '{\n  "model": "gpt-5.4",\n  "input": "hello"\n}'
    response_body = '{"id":"resp_123","object":"response","status":"completed"}'

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(
                200,
                text=response_body,
                headers={
                    "content-type": "application/json; charset=utf-8",
                    "x-request-id": "req_123",
                },
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/responses",
                content=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "OpenAI-Beta": "responses=v1",
                    "X-Stainless-Arch": "x64",
                    "User-Agent": "OpenAI/Python 1.0",
                },
            )

    assert response.status_code == 200
    assert response.text == response_body
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-request-id"] == "req_123"
    assert route.calls.last.request.content == request_body.encode("utf-8")
    assert route.calls.last.request.headers["authorization"] == "Bearer backend_key"
    assert route.calls.last.request.headers["accept"] == "application/json"
    assert route.calls.last.request.headers["openai-beta"] == "responses=v1"
    assert route.calls.last.request.headers["x-stainless-arch"] == "x64"
    assert route.calls.last.request.headers["user-agent"] == "OpenAI/Python 1.0"


def test_openai_responses_passthrough_route_preserves_sse_stream(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    backend_body = (
        'data: {"type":"response.output_text.delta","delta":"Hello"}\n\n'
        "data: [DONE]\n\n"
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(
                200,
                text=backend_body,
                headers={"content-type": "text/event-stream; charset=utf-8"},
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/responses",
                content='{"model":"gpt-5.4","input":"hello","stream":true}',
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text == backend_body
    assert route.calls.last.request.content == b'{"model":"gpt-5.4","input":"hello","stream":true}'


def test_openai_responses_passthrough_route_preserves_backend_error(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    response_body = '{"error":{"message":"backend exploded","type":"invalid_request_error"}}'

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(
                400,
                text=response_body,
                headers={"content-type": "application/json"},
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/responses",
                content='{"model":"gpt-5.4","input":"hello"}',
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 400
    assert response.text == response_body
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_openai_non_streaming_backend_error_maps_to_openai_error(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(502, text="backend exploded")
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 502
    payload = response.json()
    assert payload["error"]["type"] == "proxy_error"
    assert "backend exploded" in payload["error"]["message"]


def test_openai_streaming_backend_error_maps_to_sse_error(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(502, text="backend exploded")
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
    assert "Proxy error:" in response.text
    assert "backend exploded" in response.text
    assert "data: [DONE]" in response.text


def test_debug_logging_writes_trace_file_for_backend_endpoint(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path, debug=True, project_root=tmp_path)
    app = create_app(settings)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.post(settings.backend_responses_url).mock(
            return_value=Response(200, text=backend_sse_body())
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.4",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

    assert response.status_code == 200

    log_path = tmp_path / "logs" / "debug.log"
    assert log_path.exists()

    events = [json.loads(line)["event"] for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert "incoming_request" in events
    assert "transformed_backend_request" in events
    assert "backend_request" in events
    assert "backend_response" in events
    assert "client_response" in events
