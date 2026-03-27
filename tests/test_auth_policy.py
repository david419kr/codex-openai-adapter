from pathlib import Path

from fastapi.testclient import TestClient

from codex_openai_adapter.app import create_app
from codex_openai_adapter.core.config import Settings


def build_settings(required_api_key: str | None) -> Settings:
    return Settings(
        port=8888,
        auth_path=Path.home() / ".codex" / "auth.json",
        required_client_api_key=required_api_key,
        backend_models_url="http://127.0.0.1:9/backend-api/codex/models",
        service_name="codex-openai-adapter",
        service_version="0.1.0",
    )


def test_public_paths_remain_open_when_api_key_is_required() -> None:
    client = TestClient(create_app(build_settings("32123")))

    assert client.get("/health").status_code == 200
    assert client.get("/api/tags").status_code == 200
    assert client.get("/chat-test").status_code == 200
    assert client.get("/chat-test.html").status_code == 200


def test_protected_paths_require_api_key_when_configured() -> None:
    client = TestClient(create_app(build_settings("32123")))

    assert client.get("/models").status_code == 401
    assert client.get("/api/version").status_code == 401

    authorized = client.get("/models", headers={"Authorization": "Bearer 32123"})
    assert authorized.status_code == 200


def test_unauthorized_response_still_includes_cors_headers() -> None:
    client = TestClient(create_app(build_settings("32123")))

    response = client.get("/v1/models", headers={"Origin": "http://localhost:5500"})

    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "*"


def test_all_paths_open_when_api_key_not_configured() -> None:
    client = TestClient(create_app(build_settings(None)))

    assert client.get("/models").status_code == 200
    assert client.get("/api/version").status_code == 200


def test_options_preflight_is_allowed_for_protected_route() -> None:
    client = TestClient(create_app(build_settings("32123")))

    response = client.options(
        "/v1/models",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code in {200, 204}
    assert "access-control-allow-origin" in response.headers


def test_private_network_preflight_header_is_allowed() -> None:
    client = TestClient(create_app(build_settings(None)))

    response = client.options(
        "/v1/models",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-private-network") == "true"


def test_chat_test_page_is_served_from_same_origin() -> None:
    client = TestClient(create_app(build_settings(None)))

    response = client.get("/chat-test")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
