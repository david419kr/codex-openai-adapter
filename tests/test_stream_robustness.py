from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from codex_openai_adapter.app import create_app
from codex_openai_adapter.core.config import Settings
from codex_openai_adapter.schemas.openai import ChatCompletionsRequest, ChatMessage
from codex_openai_adapter.services.model_catalog import ModelCatalogService
from codex_openai_adapter.services.proxy_service import ProxyService


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


def test_malformed_backend_event_is_ignored(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    backend_body = (
        'data: {"type":"response.output_text.delta","delta":"Hel"}\n\n'
        "data: {this is not json}\n\n"
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
    assert '"content":"Hel"' in response.text
    assert '"content":"lo"' in response.text
    assert "data: [DONE]" in response.text


class FakeBackendClient:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.closed = False

    async def send_responses_request(self, responses_req):  # pragma: no cover - not used here
        raise NotImplementedError

    async def stream_responses_request(self, responses_req):
        async def iterator():
            try:
                for line in self.lines:
                    yield line
            finally:
                self.closed = True

        return iterator()

    async def fetch_codex_model_slugs(self, client_version: str):  # noqa: ARG002
        return ["gpt-5.4", "gpt-5.3-codex"]


class SlowFakeBackendClient(FakeBackendClient):
    def __init__(self, lines: list[str], delay_seconds: float) -> None:
        super().__init__(lines)
        self.delay_seconds = delay_seconds

    async def stream_responses_request(self, responses_req):
        async def iterator():
            try:
                for line in self.lines:
                    await asyncio.sleep(self.delay_seconds)
                    yield line
            finally:
                self.closed = True

        return iterator()


@pytest.mark.asyncio
async def test_disconnect_stops_stream_and_closes_upstream(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "auth.json")
    backend_client = FakeBackendClient(
        [
            'data: {"type":"response.output_text.delta","delta":"Hel"}',
            'data: {"type":"response.output_text.delta","delta":"lo"}',
            'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}',
            "data: [DONE]",
        ]
    )
    model_catalog = ModelCatalogService(settings, backend_client)  # type: ignore[arg-type]
    service = ProxyService(settings, backend_client, model_catalog)  # type: ignore[arg-type]
    request = ChatCompletionsRequest(
        model="gpt-5.4",
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )

    checks = 0

    async def is_disconnected() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    chunks: list[str] = []
    stream = await service.stream_chat_completions(request, is_disconnected=is_disconnected)
    async for chunk in stream:
        chunks.append(chunk)

    assert any('"role":"assistant"' in chunk for chunk in chunks)
    assert any('"content":"Hel"' in chunk for chunk in chunks)
    assert not any("data: [DONE]" in chunk for chunk in chunks)
    assert backend_client.closed is True


@pytest.mark.asyncio
async def test_openai_stream_emits_idle_heartbeat(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "auth.json")
    settings.stream_idle_heartbeat_seconds = 0.01
    backend_client = SlowFakeBackendClient(
        [
            'data: {"type":"response.output_text.delta","delta":"Hel"}',
            'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}',
            "data: [DONE]",
        ],
        delay_seconds=0.03,
    )
    model_catalog = ModelCatalogService(settings, backend_client)  # type: ignore[arg-type]
    service = ProxyService(settings, backend_client, model_catalog)  # type: ignore[arg-type]
    request = ChatCompletionsRequest(
        model="gpt-5.4",
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )

    chunks: list[str] = []
    stream = await service.stream_chat_completions(request)
    async for chunk in stream:
        chunks.append(chunk)

    assert any(chunk == ": keep-alive\n\n" for chunk in chunks)
    assert any('"content":"Hel"' in chunk for chunk in chunks)
    assert any("data: [DONE]" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_ollama_stream_emits_idle_heartbeat(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "auth.json")
    settings.stream_idle_heartbeat_seconds = 0.01
    backend_client = SlowFakeBackendClient(
        [
            'data: {"type":"response.output_text.delta","delta":"Hel"}',
            'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":2,"total_tokens":6}}}',
            "data: [DONE]",
        ],
        delay_seconds=0.03,
    )
    model_catalog = ModelCatalogService(settings, backend_client)  # type: ignore[arg-type]
    service = ProxyService(settings, backend_client, model_catalog)  # type: ignore[arg-type]
    from codex_openai_adapter.schemas.ollama import OllamaGenerateRequest

    request = OllamaGenerateRequest(
        model="gpt-5.4:latest",
        prompt="hello",
        stream=True,
    )

    chunks: list[str] = []
    stream = await service.stream_ollama_generate(request)
    async for chunk in stream:
        chunks.append(chunk)

    assert any('"response":""' in chunk and '"done":false' in chunk for chunk in chunks[:-1])
    assert any('"response":"Hel"' in chunk for chunk in chunks)
    assert '"done":true' in chunks[-1]
