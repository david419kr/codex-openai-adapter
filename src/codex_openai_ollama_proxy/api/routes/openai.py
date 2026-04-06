from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from codex_openai_ollama_proxy.api.deps import get_proxy_service
from codex_openai_ollama_proxy.core.debug_trace import (
    finish_debug_request,
    log_debug_event,
    start_debug_request,
)
from codex_openai_ollama_proxy.core.errors import openai_error_response
from codex_openai_ollama_proxy.schemas.openai import ChatCompletionsRequest
from codex_openai_ollama_proxy.services.proxy_service import ProxyService
from codex_openai_ollama_proxy.services.streaming_formatter import build_openai_error_sse

router = APIRouter(tags=["openai"])

PASSTHROUGH_RESPONSE_EXCLUDED_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _split_passthrough_response_headers(
    headers: dict[str, str],
) -> tuple[str | None, dict[str, str]]:
    media_type: str | None = None
    forwarded_headers: dict[str, str] = {}
    for name, value in headers.items():
        normalized_name = name.lower()
        if normalized_name == "content-type":
            media_type = value
            continue
        if normalized_name in PASSTHROUGH_RESPONSE_EXCLUDED_HEADERS:
            continue
        forwarded_headers[name] = value
    return media_type, forwarded_headers


def _is_sse_media_type(media_type: str | None) -> bool:
    if media_type is None:
        return False
    return media_type.split(";", 1)[0].strip().lower() == "text/event-stream"


@router.post("/chat/completions")
@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionsRequest,
    raw_request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    debug_tokens = start_debug_request(
        raw_request.url.path,
        request.model_dump(by_alias=True, exclude_none=True),
    )

    if request.stream:
        async def stream_with_error_fallback():
            emitted_chunks: list[str] = []
            try:
                try:
                    async for chunk in await proxy_service.stream_chat_completions(
                        request,
                        is_disconnected=raw_request.is_disconnected,
                    ):
                        emitted_chunks.append(chunk)
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    chunk = build_openai_error_sse(request.model, f"Proxy error: {exc}")
                    emitted_chunks.append(chunk)
                    yield chunk
            finally:
                log_debug_event(
                    "client_response",
                    status_code=200,
                    media_type="text/event-stream",
                    body="".join(emitted_chunks),
                )
                finish_debug_request(debug_tokens)

        return StreamingResponse(
            stream_with_error_fallback(),
            media_type="text/event-stream",
            headers={
                "cache-control": "no-cache",
                "connection": "keep-alive",
            },
        )

    try:
        response = await proxy_service.proxy_chat_completions(request)
    except Exception as exc:  # noqa: BLE001
        error_response = openai_error_response(exc)
        log_debug_event(
            "client_response",
            status_code=error_response.status_code,
            media_type="application/json",
            body=error_response.body,
        )
        finish_debug_request(debug_tokens)
        return error_response

    payload = response.model_dump(by_alias=True, exclude_none=True)
    log_debug_event(
        "client_response",
        status_code=200,
        media_type="application/json",
        body=payload,
    )
    finish_debug_request(debug_tokens)
    return JSONResponse(content=payload)


@router.post("/responses")
@router.post("/v1/responses")
async def responses_passthrough(
    raw_request: Request,
    proxy_service: ProxyService = Depends(get_proxy_service),
):
    request_body = await raw_request.body()
    debug_tokens = start_debug_request(raw_request.url.path, request_body)

    try:
        backend_response = await proxy_service.open_responses_passthrough(
            request_body,
            incoming_headers=raw_request.headers,
        )
    except Exception as exc:  # noqa: BLE001
        error_response = openai_error_response(exc)
        log_debug_event(
            "client_response",
            status_code=error_response.status_code,
            media_type="application/json",
            body=error_response.body,
        )
        finish_debug_request(debug_tokens)
        return error_response

    media_type, response_headers = _split_passthrough_response_headers(
        dict(backend_response.headers)
    )

    if _is_sse_media_type(media_type):

        async def stream_passthrough():
            emitted_chunks: list[bytes] = []
            try:
                async for chunk in backend_response.aiter_raw():
                    if await raw_request.is_disconnected():
                        break
                    emitted_chunks.append(chunk)
                    yield chunk
            finally:
                body = b"".join(emitted_chunks)
                log_debug_event(
                    "backend_response_stream",
                    status_code=backend_response.status_code,
                    body=body,
                )
                log_debug_event(
                    "client_response",
                    status_code=backend_response.status_code,
                    media_type=media_type or "text/event-stream",
                    body=body,
                )
                finish_debug_request(debug_tokens)
                await backend_response.aclose()

        return StreamingResponse(
            stream_passthrough(),
            status_code=backend_response.status_code,
            media_type=media_type,
            headers=response_headers,
        )

    body = b""
    try:
        body = await backend_response.aread()
    finally:
        await backend_response.aclose()

    log_debug_event(
        "backend_response",
        status_code=backend_response.status_code,
        body=body,
    )
    log_debug_event(
        "client_response",
        status_code=backend_response.status_code,
        media_type=media_type or "application/octet-stream",
        body=body,
    )
    finish_debug_request(debug_tokens)

    return Response(
        content=body,
        status_code=backend_response.status_code,
        media_type=media_type,
        headers=response_headers,
    )
