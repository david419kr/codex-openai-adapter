from __future__ import annotations

import asyncio
from contextlib import suppress
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from codex_openai_ollama_proxy.core.config import DEFAULT_SYSTEM_INSTRUCTIONS, Settings
from codex_openai_ollama_proxy.core.debug_trace import log_debug_event
from codex_openai_ollama_proxy.core.errors import EmptyBackendResponseError
from codex_openai_ollama_proxy.schemas.backend import ResponsesApiRequest
from codex_openai_ollama_proxy.schemas.events import (
    TextDeltaEvent,
    TextDoneEvent,
    ToolCallChunkEvent,
)
from codex_openai_ollama_proxy.schemas.ollama import OllamaChatRequest, OllamaGenerateRequest
from codex_openai_ollama_proxy.schemas.openai import (
    ChatCompletionsRequest,
    ChatCompletionsResponse,
    ChatMessage,
    ChatResponseMessage,
    Choice,
)
from codex_openai_ollama_proxy.schemas.usage import Usage
from codex_openai_ollama_proxy.services.backend_client import BackendClient
from codex_openai_ollama_proxy.services.content_conversion import convert_messages_to_input
from codex_openai_ollama_proxy.services.event_parser import (
    parse_backend_sse_text,
    stream_events_from_sse_lines,
)
from codex_openai_ollama_proxy.services.model_catalog import ModelCatalogService
from codex_openai_ollama_proxy.services.model_resolution import (
    normalize_ollama_think,
    resolve_model_and_reasoning,
    resolve_temperature,
)
from codex_openai_ollama_proxy.services.stream_state import StreamState
from codex_openai_ollama_proxy.services.tool_conversion import (
    convert_chat_tools_to_responses,
    convert_tool_choice,
)


class ProxyService:
    def __init__(
        self,
        settings: Settings,
        backend_client: BackendClient,
        model_catalog: ModelCatalogService,
    ) -> None:
        self._settings = settings
        self._backend_client = backend_client
        self._model_catalog = model_catalog

    async def proxy_chat_completions(
        self, chat_req: ChatCompletionsRequest
    ) -> ChatCompletionsResponse:
        requested_model = chat_req.model
        responses_req = await self.convert_chat_to_responses(chat_req)
        if not responses_req.input:
            raise ValueError("No non-system input message found (input is empty)")

        response_text = await self._backend_client.send_responses_request(responses_req)
        response_content, response_tool_calls, usage = parse_backend_sse_text(response_text)

        finish_reason = "stop" if not response_tool_calls else "tool_calls"
        return ChatCompletionsResponse(
            id=f"chatcmpl-{uuid4()}",
            object="chat.completion",
            created=int(datetime.now(UTC).timestamp()),
            model=requested_model,
            choices=[
                Choice(
                    index=0,
                    message=ChatResponseMessage(
                        role="assistant",
                        content=response_content,
                        tool_calls=response_tool_calls or None,
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=usage or Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    async def stream_chat_completions(
        self,
        chat_req: ChatCompletionsRequest,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        from codex_openai_ollama_proxy.services.streaming_formatter import OpenAIStreamFormatter

        requested_model = chat_req.model
        responses_req = await self.convert_chat_to_responses(chat_req)
        if not responses_req.input:
            raise ValueError("No non-system input message found (input is empty)")

        formatter = OpenAIStreamFormatter(requested_model)
        state = StreamState()

        async def iterator() -> AsyncIterator[str]:
            disconnected = False
            if is_disconnected is not None and await is_disconnected():
                return
            yield formatter.role_chunk()
            lines = await self._backend_client.stream_responses_request(responses_req)
            async for event in stream_events_with_idle_heartbeat(
                stream_events_from_sse_lines(lines),
                self._settings.stream_idle_heartbeat_seconds,
            ):
                if event is HEARTBEAT_SENTINEL:
                    if is_disconnected is not None and await is_disconnected():
                        disconnected = True
                        await maybe_aclose_async_iterator(lines)
                        break
                    yield formatter.heartbeat_chunk()
                    continue
                if is_disconnected is not None and await is_disconnected():
                    disconnected = True
                    await maybe_aclose_async_iterator(lines)
                    break
                emit = state.apply(event)
                if isinstance(event, TextDeltaEvent) and emit:
                    yield formatter.content_chunk(event.text)
                elif isinstance(event, TextDoneEvent) and emit:
                    yield formatter.content_chunk(event.text)
                elif isinstance(event, ToolCallChunkEvent) and emit:
                    yield formatter.tool_call_chunk(event)

            if disconnected:
                return

            if not state.has_any_output:
                raise EmptyBackendResponseError(
                    "Empty content and no tool calls returned from ChatGPT backend"
                )

            yield formatter.final_chunk(state.finish_reason, state.usage)
            yield formatter.done_chunk()

        return iterator()

    async def convert_chat_to_responses(
        self, chat_req: ChatCompletionsRequest
    ) -> ResponsesApiRequest:
        base_models = await self._model_catalog.get_base_models_for_request(chat_req.model)
        backend_model, reasoning = resolve_model_and_reasoning(
            chat_req.model,
            chat_req.reasoning,
            chat_req.reasoning_effort,
            base_models,
        )
        temperature = resolve_temperature(
            chat_req.model,
            backend_model,
            reasoning,
            chat_req.temperature,
        )
        converted_tools = convert_chat_tools_to_responses(chat_req.tools)
        converted_tool_choice = convert_tool_choice(chat_req.tool_choice)
        input_items, instructions = convert_messages_to_input(
            chat_req.messages,
            default_instructions=DEFAULT_SYSTEM_INSTRUCTIONS,
        )

        responses_request = ResponsesApiRequest(
            model=backend_model,
            instructions=instructions,
            input=input_items,
            tools=converted_tools,
            tool_choice=converted_tool_choice,
            parallel_tool_calls=False,
            temperature=temperature,
            reasoning=reasoning,
            store=False,
            stream=True,
            include=[],
        )
        log_debug_event("transformed_backend_request", payload=responses_request)
        return responses_request

    async def open_responses_passthrough(
        self,
        request_body: bytes,
        incoming_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return await self._backend_client.open_responses_passthrough(
            request_body,
            incoming_headers=incoming_headers,
        )

    async def proxy_ollama_chat(self, request: OllamaChatRequest) -> ChatCompletionsResponse:
        chat_request = self._build_chat_request_from_ollama(
            model=request.model,
            messages=request.messages,
            prompt=request.prompt,
            system=request.system,
            stream=request.stream,
            think=request.think,
            tools=getattr(request, "tools", None),
            tool_choice=getattr(request, "tool_choice", None),
        )
        return await self.proxy_chat_completions(chat_request)

    async def stream_ollama_chat(
        self,
        request: OllamaChatRequest,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        return await self._stream_ollama(
            request,
            mode="chat",
            is_disconnected=is_disconnected,
        )

    async def stream_ollama_generate(
        self,
        request: OllamaGenerateRequest,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        return await self._stream_ollama(
            request,
            mode="generate",
            is_disconnected=is_disconnected,
        )

    async def _stream_ollama(
        self,
        request: OllamaChatRequest | OllamaGenerateRequest,
        *,
        mode: str,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        from codex_openai_ollama_proxy.services.streaming_formatter import OllamaStreamFormatter

        chat_request = self._build_chat_request_from_ollama(
            model=request.model,
            messages=request.messages,
            prompt=request.prompt,
            system=request.system,
            stream=request.stream,
            think=request.think,
            tools=getattr(request, "tools", None),
            tool_choice=getattr(request, "tool_choice", None),
        )
        requested_model = normalize_ollama_model(request.model)
        responses_req = await self.convert_chat_to_responses(chat_request)
        if not responses_req.input:
            raise ValueError("No non-system input message found (input is empty)")

        formatter = OllamaStreamFormatter(requested_model, mode=mode)
        state = StreamState()

        async def iterator() -> AsyncIterator[str]:
            disconnected = False
            if is_disconnected is not None and await is_disconnected():
                return
            lines = await self._backend_client.stream_responses_request(responses_req)
            async for event in stream_events_with_idle_heartbeat(
                stream_events_from_sse_lines(lines),
                self._settings.stream_idle_heartbeat_seconds,
            ):
                if event is HEARTBEAT_SENTINEL:
                    if is_disconnected is not None and await is_disconnected():
                        disconnected = True
                        await maybe_aclose_async_iterator(lines)
                        break
                    yield formatter.heartbeat_chunk()
                    continue
                if is_disconnected is not None and await is_disconnected():
                    disconnected = True
                    await maybe_aclose_async_iterator(lines)
                    break
                emit = state.apply(event)
                if isinstance(event, TextDeltaEvent) and emit:
                    yield formatter.content_chunk(event.text)
                elif isinstance(event, TextDoneEvent) and emit:
                    yield formatter.content_chunk(event.text)
                elif isinstance(event, ToolCallChunkEvent) and emit and mode == "chat":
                    yield formatter.tool_call_snapshot_chunk(state.tool_calls)

            if disconnected:
                return

            if not state.has_any_output:
                raise EmptyBackendResponseError(
                    "Empty content and no tool calls returned from ChatGPT backend"
                )

            if mode == "chat" and state.tool_calls:
                yield formatter.tool_calls_chunk(state.tool_calls)

            yield formatter.final_chunk(state.usage)

        return iterator()

    async def proxy_ollama_generate(
        self, request: OllamaGenerateRequest
    ) -> ChatCompletionsResponse:
        chat_request = self._build_chat_request_from_ollama(
            model=request.model,
            messages=request.messages,
            prompt=request.prompt,
            system=request.system,
            stream=request.stream,
            think=request.think,
            tools=None,
            tool_choice=None,
        )
        return await self.proxy_chat_completions(chat_request)

    def _build_chat_request_from_ollama(
        self,
        *,
        model: str,
        messages: list[ChatMessage] | None,
        prompt: str | None,
        system: str | None,
        stream: bool | None,
        think: bool | str | None,
        tools: list[Any] | None,
        tool_choice: Any | None,
    ) -> ChatCompletionsRequest:
        normalized_model = normalize_ollama_model(model)
        resolved_messages = list(messages or [])

        if system and system.strip():
            resolved_messages.insert(
                0,
                ChatMessage(role="system", content=system),
            )

        if not has_non_system_message(resolved_messages):
            if not prompt or not prompt.strip():
                raise ValueError("missing prompt or messages")
            resolved_messages.append(ChatMessage(role="user", content=prompt))

        return ChatCompletionsRequest(
            model=normalized_model,
            messages=resolved_messages,
            temperature=None,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            reasoning=None,
            reasoning_effort=normalize_ollama_think(think),
        )


def normalize_ollama_model(model: str) -> str:
    return model[:-7] if model.endswith(":latest") else model


def has_non_system_message(messages: list[ChatMessage]) -> bool:
    return any(message.role.lower() != "system" for message in messages)


async def maybe_aclose_async_iterator(iterator: object) -> None:
    aclose = getattr(iterator, "aclose", None)
    if callable(aclose):
        await aclose()


HEARTBEAT_SENTINEL = object()


async def stream_events_with_idle_heartbeat(
    events: AsyncIterator[Any],
    interval_seconds: float,
) -> AsyncIterator[Any]:
    if interval_seconds <= 0:
        async for event in events:
            yield event
        return

    pending: asyncio.Task[Any] | None = asyncio.create_task(anext(events))
    try:
        while pending is not None:
            done, _ = await asyncio.wait({pending}, timeout=interval_seconds)
            if not done:
                yield HEARTBEAT_SENTINEL
                continue

            try:
                event = pending.result()
            except StopAsyncIteration:
                break

            yield event
            pending = asyncio.create_task(anext(events))
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
