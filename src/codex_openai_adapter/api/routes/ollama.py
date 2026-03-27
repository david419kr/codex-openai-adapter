from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from codex_openai_adapter.api.deps import get_proxy_service, get_settings
from codex_openai_adapter.core.config import Settings
from codex_openai_adapter.core.debug_trace import (
    finish_debug_request,
    log_debug_event,
    start_debug_request,
)
from codex_openai_adapter.core.errors import ollama_error_response
from codex_openai_adapter.schemas.ollama import OllamaChatRequest, OllamaGenerateRequest
from codex_openai_adapter.services.model_resolution import exposed_model_list
from codex_openai_adapter.services.proxy_service import ProxyService
from codex_openai_adapter.services.streaming_formatter import build_ollama_error_ndjson
from codex_openai_adapter.services.tool_conversion import convert_chat_tool_calls_to_ollama

router = APIRouter(tags=["ollama"])


@router.get("/api/tags")
def ollama_tags(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "models": [
            {
                "name": model,
                "model": model,
                "modified_at": "1970-01-01T00:00:00.000Z",
                "size": 0,
                "digest": "",
                "details": {
                    "parent_model": "",
                    "format": "proxy",
                    "family": "gpt",
                    "families": ["gpt"],
                    "parameter_size": "unknown",
                    "quantization_level": "unknown",
                },
            }
            for model in exposed_model_list()
        ]
    }


@router.post("/api/chat")
async def ollama_chat(
    request: OllamaChatRequest,
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
                    async for chunk in await proxy_service.stream_ollama_chat(
                        request,
                        is_disconnected=raw_request.is_disconnected,
                    ):
                        emitted_chunks.append(chunk)
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    chunk = build_ollama_error_ndjson(f"proxy error: {exc}")
                    emitted_chunks.append(chunk)
                    yield chunk
            finally:
                log_debug_event(
                    "client_response",
                    status_code=200,
                    media_type="application/x-ndjson",
                    body="".join(emitted_chunks),
                )
                finish_debug_request(debug_tokens)

        return StreamingResponse(
            stream_with_error_fallback(),
            media_type="application/x-ndjson",
        )

    try:
        response = await proxy_service.proxy_ollama_chat(request)
    except Exception as exc:  # noqa: BLE001
        error_response = ollama_error_response(exc)
        log_debug_event(
            "client_response",
            status_code=error_response.status_code,
            media_type="application/json",
            body=error_response.body,
        )
        finish_debug_request(debug_tokens)
        return error_response

    content = response.choices[0].message.content
    payload = {
        "model": response.model,
        "created_at": "1970-01-01T00:00:00.000Z",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": response.usage.prompt_tokens if response.usage else 0,
        "prompt_eval_duration": 0,
        "eval_count": response.usage.completion_tokens if response.usage else 0,
        "eval_duration": 0,
    }
    if response.choices[0].message.tool_calls:
        payload["message"]["tool_calls"] = convert_chat_tool_calls_to_ollama(
            response.choices[0].message.tool_calls
        )
    log_debug_event(
        "client_response",
        status_code=200,
        media_type="application/json",
        body=payload,
    )
    finish_debug_request(debug_tokens)
    return JSONResponse(content=payload)


@router.post("/api/generate")
async def ollama_generate(
    request: OllamaGenerateRequest,
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
                    async for chunk in await proxy_service.stream_ollama_generate(
                        request,
                        is_disconnected=raw_request.is_disconnected,
                    ):
                        emitted_chunks.append(chunk)
                        yield chunk
                except Exception as exc:  # noqa: BLE001
                    chunk = build_ollama_error_ndjson(f"proxy error: {exc}")
                    emitted_chunks.append(chunk)
                    yield chunk
            finally:
                log_debug_event(
                    "client_response",
                    status_code=200,
                    media_type="application/x-ndjson",
                    body="".join(emitted_chunks),
                )
                finish_debug_request(debug_tokens)

        return StreamingResponse(
            stream_with_error_fallback(),
            media_type="application/x-ndjson",
        )

    try:
        response = await proxy_service.proxy_ollama_generate(request)
    except Exception as exc:  # noqa: BLE001
        error_response = ollama_error_response(exc)
        log_debug_event(
            "client_response",
            status_code=error_response.status_code,
            media_type="application/json",
            body=error_response.body,
        )
        finish_debug_request(debug_tokens)
        return error_response

    content = response.choices[0].message.content
    payload = {
        "model": response.model,
        "created_at": "1970-01-01T00:00:00.000Z",
        "response": content,
        "done": True,
        "done_reason": "stop",
        "context": [],
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": response.usage.prompt_tokens if response.usage else 0,
        "prompt_eval_duration": 0,
        "eval_count": response.usage.completion_tokens if response.usage else 0,
        "eval_duration": 0,
    }
    log_debug_event(
        "client_response",
        status_code=200,
        media_type="application/json",
        body=payload,
    )
    finish_debug_request(debug_tokens)
    return JSONResponse(content=payload)
