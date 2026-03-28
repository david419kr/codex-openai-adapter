from __future__ import annotations

from collections.abc import Mapping

from fastapi.responses import JSONResponse

from .config import Settings


def extract_incoming_api_key(headers: Mapping[str, str]) -> str | None:
    raw = (
        headers.get("authorization")
        or headers.get("x-api-key")
        or headers.get("api-key")
    )
    if not raw:
        return None

    normalized = raw.strip()
    if not normalized:
        return None
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()
    return normalized or None


def unauthorized_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        headers={
            "Access-Control-Allow-Origin": "*",
        },
        content={
            "error": {
                "message": message,
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        },
    )


def is_public_path(path: str, settings: Settings) -> bool:
    return path in settings.public_paths
