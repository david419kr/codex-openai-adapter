from __future__ import annotations

from fastapi.responses import JSONResponse


class ProxyError(Exception):
    """Base exception for proxy failures."""


class BackendHTTPError(ProxyError):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"ChatGPT backend error {status_code}: {body}")


class AuthenticationRefreshError(ProxyError):
    """Raised when refresh_token based renewal fails."""


class EmptyBackendResponseError(ProxyError):
    """Raised when backend emits no text and no tool calls."""


def status_code_for_error(exc: Exception) -> int:
    if isinstance(exc, BackendHTTPError):
        return exc.status_code
    if isinstance(exc, ValueError):
        return 400
    if isinstance(exc, AuthenticationRefreshError):
        return 502
    if isinstance(exc, EmptyBackendResponseError):
        return 502
    if isinstance(exc, ProxyError):
        return 500
    return 500


def openai_error_response(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status_code_for_error(exc),
        headers={
            "Access-Control-Allow-Origin": "*",
        },
        content={
            "error": {
                "message": f"Proxy error: {exc}",
                "type": "proxy_error",
                "code": "internal_error",
            }
        },
    )


def ollama_error_response(exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status_code_for_error(exc),
        headers={
            "Access-Control-Allow-Origin": "*",
        },
        content={"error": f"proxy error: {exc}"},
    )
