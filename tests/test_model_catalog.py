from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from codex_openai_adapter.app import create_app
from codex_openai_adapter.core.config import Settings
from codex_openai_adapter.services.model_catalog import ModelCatalogService


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


class FakeCatalogBackendClient:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def fetch_codex_model_slugs(self, client_version: str) -> list[str]:  # noqa: ARG002
        self.calls += 1
        if not self._responses:
            raise RuntimeError("no response configured")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return list(response)


@pytest.mark.asyncio
async def test_model_catalog_uses_last_known_good_cache_on_fetch_failure(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "auth.json")
    backend_client = FakeCatalogBackendClient(
        [
            ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"],
            RuntimeError("backend down"),
        ]
    )
    clock = Clock(1000.0)
    catalog = ModelCatalogService(settings, backend_client, time_fn=clock.now)  # type: ignore[arg-type]

    assert await catalog.get_base_models() == ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]

    clock.set_time(2000.0)
    assert await catalog.get_base_models() == ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex"]
    assert backend_client.calls == 2


@pytest.mark.asyncio
async def test_model_catalog_uses_static_fallback_on_cold_start_failure(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "auth.json")
    backend_client = FakeCatalogBackendClient([RuntimeError("backend down")])
    catalog = ModelCatalogService(settings, backend_client)  # type: ignore[arg-type]

    assert await catalog.get_base_models() == ["gpt-5.4", "gpt-5.3-codex"]


def test_models_and_tags_routes_expose_dynamic_models(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    catalog_body = {
        "models": [
            {"slug": "gpt-5.4", "display_name": "gpt-5.4"},
            {"slug": "gpt-5.4-mini", "display_name": "GPT-5.4-Mini"},
            {"slug": "gpt-5.3-codex", "display_name": "gpt-5.3-codex"},
        ]
    }

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(settings.backend_models_url).mock(return_value=Response(200, json=catalog_body))
        with TestClient(app) as client:
            models_response = client.get("/v1/models")
            tags_response = client.get("/api/tags")

    assert models_response.status_code == 200
    model_ids = [item["id"] for item in models_response.json()["data"]]
    assert "gpt-5.4-mini" in model_ids
    assert "gpt-5.4-mini-high" in model_ids

    assert tags_response.status_code == 200
    tag_names = [item["name"] for item in tags_response.json()["models"]]
    assert "gpt-5.4-mini" in tag_names
    assert "gpt-5.4-mini-xhigh" in tag_names


def test_model_catalog_request_does_not_advertise_brotli(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(auth_path, {"OPENAI_API_KEY": "backend_key"})
    settings = build_settings(auth_path)
    app = create_app(settings)

    catalog_body = {"models": [{"slug": "gpt-5.4"}]}

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.get(settings.backend_models_url).mock(
            return_value=Response(200, json=catalog_body)
        )
        with TestClient(app) as client:
            response = client.get("/v1/models")

    assert response.status_code == 200
    assert "br" not in route.calls.last.request.headers["accept-encoding"]


class Clock:
    def __init__(self, current: float) -> None:
        self.current = current

    def now(self) -> float:
        return self.current

    def set_time(self, value: float) -> None:
        self.current = value
