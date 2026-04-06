from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from uuid import uuid4

import httpx

from codex_openai_ollama_proxy.core.config import Settings
from codex_openai_ollama_proxy.core.debug_trace import log_debug_event
from codex_openai_ollama_proxy.core.errors import BackendHTTPError
from codex_openai_ollama_proxy.schemas.auth import AuthData
from codex_openai_ollama_proxy.schemas.backend import ResponsesApiRequest
from codex_openai_ollama_proxy.services.auth_store import AuthStore

PASSTHROUGH_REQUEST_HEADER_NAMES = {
    "accept",
    "accept-encoding",
    "accept-language",
    "content-type",
    "idempotency-key",
    "user-agent",
}
PASSTHROUGH_REQUEST_HEADER_PREFIXES = ("openai-", "x-stainless-")


class BackendClient:
    def __init__(
        self,
        settings: Settings,
        auth_store: AuthStore,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._auth_store = auth_store
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            },
            follow_redirects=True,
            timeout=httpx.Timeout(300.0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send_responses_request(self, responses_req: ResponsesApiRequest) -> str:
        auth_snapshot = await self._auth_store.snapshot()
        response = await self._send(responses_req, auth_snapshot)

        if (
            response.status_code in {401, 403}
            and auth_snapshot.tokens is not None
            and auth_snapshot.tokens.refresh_token
        ):
            previous_access_token = auth_snapshot.tokens.access_token
            auth_snapshot = await self._auth_store.refresh_access_token_if_needed(
                previous_access_token=previous_access_token,
                client=self._client,
                oauth_token_url=self._settings.oauth_token_url,
                codex_client_id=self._settings.codex_client_id,
            )
            response = await self._send(responses_req, auth_snapshot)

        if response.is_error:
            log_debug_event(
                "backend_response",
                status_code=response.status_code,
                body=response.text,
            )
            raise BackendHTTPError(response.status_code, response.text)

        log_debug_event(
            "backend_response",
            status_code=response.status_code,
            body=response.text,
        )
        return response.text

    async def stream_responses_request(
        self, responses_req: ResponsesApiRequest
    ) -> AsyncIterator[str]:
        auth_snapshot = await self._auth_store.snapshot()
        response = await self._send_streaming(responses_req, auth_snapshot)

        if (
            response.status_code in {401, 403}
            and auth_snapshot.tokens is not None
            and auth_snapshot.tokens.refresh_token
        ):
            await response.aclose()
            previous_access_token = auth_snapshot.tokens.access_token
            auth_snapshot = await self._auth_store.refresh_access_token_if_needed(
                previous_access_token=previous_access_token,
                client=self._client,
                oauth_token_url=self._settings.oauth_token_url,
                codex_client_id=self._settings.codex_client_id,
            )
            response = await self._send_streaming(responses_req, auth_snapshot)

        if response.is_error:
            body = await response.aread()
            await response.aclose()
            log_debug_event(
                "backend_response_stream",
                status_code=response.status_code,
                body=body.decode("utf-8", errors="replace"),
            )
            raise BackendHTTPError(response.status_code, body.decode("utf-8", errors="replace"))

        async def iterator() -> AsyncIterator[str]:
            collected_lines: list[str] = []
            try:
                async for line in response.aiter_lines():
                    collected_lines.append(line)
                    yield line
            finally:
                log_debug_event(
                    "backend_response_stream",
                    status_code=response.status_code,
                    body="\n".join(collected_lines),
                )
                await response.aclose()

        return iterator()

    async def open_responses_passthrough(
        self,
        request_body: bytes,
        incoming_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        auth_snapshot = await self._auth_store.snapshot()
        response = await self._send_raw_streaming(
            request_body,
            auth_snapshot,
            incoming_headers=incoming_headers,
        )

        if (
            response.status_code in {401, 403}
            and auth_snapshot.tokens is not None
            and auth_snapshot.tokens.refresh_token
        ):
            await response.aclose()
            previous_access_token = auth_snapshot.tokens.access_token
            auth_snapshot = await self._auth_store.refresh_access_token_if_needed(
                previous_access_token=previous_access_token,
                client=self._client,
                oauth_token_url=self._settings.oauth_token_url,
                codex_client_id=self._settings.codex_client_id,
            )
            response = await self._send_raw_streaming(
                request_body,
                auth_snapshot,
                incoming_headers=incoming_headers,
            )

        return response

    async def fetch_codex_model_slugs(self, client_version: str) -> list[str]:
        auth_snapshot = await self._auth_store.snapshot()
        response = await self._send_model_catalog_request(client_version, auth_snapshot)

        if (
            response.status_code in {401, 403}
            and auth_snapshot.tokens is not None
            and auth_snapshot.tokens.refresh_token
        ):
            previous_access_token = auth_snapshot.tokens.access_token
            auth_snapshot = await self._auth_store.refresh_access_token_if_needed(
                previous_access_token=previous_access_token,
                client=self._client,
                oauth_token_url=self._settings.oauth_token_url,
                codex_client_id=self._settings.codex_client_id,
            )
            response = await self._send_model_catalog_request(client_version, auth_snapshot)

        if response.is_error:
            log_debug_event(
                "backend_model_catalog_response",
                status_code=response.status_code,
                body=response.text,
            )
            raise BackendHTTPError(response.status_code, response.text)

        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise BackendHTTPError(response.status_code, "Invalid model catalog response")

        slugs: list[str] = []
        seen: set[str] = set()
        for model in models:
            slug = model.get("slug") if isinstance(model, dict) else None
            if not isinstance(slug, str) or not slug or slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)

        if not slugs:
            raise BackendHTTPError(response.status_code, "Empty model catalog response")

        log_debug_event(
            "backend_model_catalog_response",
            status_code=response.status_code,
            slugs=slugs,
            client_version=client_version,
        )
        return slugs

    async def _send(
        self,
        responses_req: ResponsesApiRequest,
        auth_data: AuthData,
    ) -> httpx.Response:
        headers = self._build_responses_headers(auth_data)

        log_debug_event(
            "backend_request",
            method="POST",
            url=self._settings.backend_responses_url,
            payload=responses_req,
        )
        return await self._client.post(
            self._settings.backend_responses_url,
            headers=headers,
            json=responses_req.model_dump(by_alias=True, exclude_none=True),
        )

    async def _send_streaming(
        self,
        responses_req: ResponsesApiRequest,
        auth_data: AuthData,
    ) -> httpx.Response:
        headers = self._build_responses_headers(auth_data)

        request = self._client.build_request(
            "POST",
            self._settings.backend_responses_url,
            headers=headers,
            json=responses_req.model_dump(by_alias=True, exclude_none=True),
        )
        log_debug_event(
            "backend_request",
            method="POST",
            url=self._settings.backend_responses_url,
            payload=responses_req,
        )
        return await self._client.send(request, stream=True)

    async def _send_raw_streaming(
        self,
        request_body: bytes,
        auth_data: AuthData,
        *,
        incoming_headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        headers = self._build_responses_headers(
            auth_data,
            incoming_headers=incoming_headers,
        )

        request = self._client.build_request(
            "POST",
            self._settings.backend_responses_url,
            headers=headers,
            content=request_body,
        )
        log_debug_event(
            "backend_request",
            method="POST",
            url=self._settings.backend_responses_url,
            payload=request_body,
        )
        return await self._client.send(request, stream=True)

    async def _send_model_catalog_request(
        self,
        client_version: str,
        auth_data: AuthData,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
            "OpenAI-Beta": "responses=experimental",
            "originator": "codex_cli_rs",
            "session_id": str(uuid4()),
        }

        if auth_data.tokens is not None:
            headers["Authorization"] = f"Bearer {auth_data.tokens.access_token}"
            headers["chatgpt-account-id"] = auth_data.tokens.account_id
        elif auth_data.api_key:
            headers["Authorization"] = f"Bearer {auth_data.api_key}"

        log_debug_event(
            "backend_model_catalog_request",
            method="GET",
            url=self._settings.backend_models_url,
            client_version=client_version,
        )
        return await self._client.get(
            self._settings.backend_models_url,
            headers=headers,
            params={"client_version": client_version},
            timeout=20.0,
        )

    def _build_responses_headers(
        self,
        auth_data: AuthData,
        *,
        incoming_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://chatgpt.com/",
            "Origin": "https://chatgpt.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
            "OpenAI-Beta": "responses=experimental",
            "originator": "codex_cli_rs",
            "session_id": str(uuid4()),
        }
        for name, value in self._filter_passthrough_headers(incoming_headers).items():
            existing_name = next(
                (key for key in headers if key.lower() == name.lower()),
                name,
            )
            headers[existing_name] = value

        if auth_data.tokens is not None:
            headers["Authorization"] = f"Bearer {auth_data.tokens.access_token}"
            headers["chatgpt-account-id"] = auth_data.tokens.account_id
        elif auth_data.api_key:
            headers["Authorization"] = f"Bearer {auth_data.api_key}"

        return headers

    def _filter_passthrough_headers(
        self,
        incoming_headers: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if incoming_headers is None:
            return {}

        forwarded_headers: dict[str, str] = {}
        for name, value in incoming_headers.items():
            normalized_name = name.lower()
            if normalized_name in {"authorization", "api-key", "x-api-key"}:
                continue
            if normalized_name in PASSTHROUGH_REQUEST_HEADER_NAMES or normalized_name.startswith(
                PASSTHROUGH_REQUEST_HEADER_PREFIXES
            ):
                forwarded_headers[name] = value

        return forwarded_headers
