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


def test_refreshes_token_and_retries(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    write_auth_file(
        auth_path,
        {
            "tokens": {
                "access_token": "old_access",
                "refresh_token": "refresh_123",
                "account_id": "acct_1",
            }
        },
    )

    settings = build_settings(auth_path)
    app = create_app(settings)
    backend_body = (
        'data: {"type":"response.output_text.delta","delta":"Hello after refresh"}\n\n'
        'data: {"type":"response.completed","response":{"usage":{"input_tokens":4,"output_tokens":3,"total_tokens":7}}}\n\n'
        "data: [DONE]\n\n"
    )

    with respx.mock(assert_all_called=True) as respx_mock:
        backend_route = respx_mock.post(settings.backend_responses_url).mock(
            side_effect=[
                Response(401, text="expired"),
                Response(200, text=backend_body),
            ]
        )
        refresh_route = respx_mock.post(settings.oauth_token_url).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "account_id": "acct_1",
                },
            )
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
        data = response.json()
        assert data["choices"][0]["message"]["content"] == "Hello after refresh"
        assert backend_route.call_count == 2
        assert refresh_route.called

    refreshed = json.loads(auth_path.read_text(encoding="utf-8"))
    assert refreshed["tokens"]["access_token"] == "new_access"
    assert refreshed["tokens"]["refresh_token"] == "new_refresh"
    assert refreshed["last_refresh"]
