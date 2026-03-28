from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

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
