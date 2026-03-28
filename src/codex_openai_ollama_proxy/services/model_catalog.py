from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence

from codex_openai_ollama_proxy.core.config import Settings
from codex_openai_ollama_proxy.core.debug_trace import log_debug_event
from codex_openai_ollama_proxy.services.backend_client import BackendClient
from codex_openai_ollama_proxy.services.model_resolution import (
    FALLBACK_BASE_MODELS,
    exposed_model_list,
    is_known_model,
)

LOGGER = logging.getLogger(__name__)


class ModelCatalogService:
    def __init__(
        self,
        settings: Settings,
        backend_client: BackendClient,
        *,
        time_fn: Callable[[], float] | None = None,
        fallback_base_models: Sequence[str] = FALLBACK_BASE_MODELS,
    ) -> None:
        self._settings = settings
        self._backend_client = backend_client
        self._time_fn = time_fn or time.monotonic
        self._fallback_base_models = list(fallback_base_models)
        self._cached_base_models: list[str] | None = None
        self._cache_expires_at = 0.0
        self._lock = asyncio.Lock()

    def cached_or_fallback_base_models(self) -> list[str]:
        if self._cached_base_models:
            return list(self._cached_base_models)
        return list(self._fallback_base_models)

    async def get_base_models(self) -> list[str]:
        if self._cached_base_models and self._time_fn() < self._cache_expires_at:
            return list(self._cached_base_models)

        async with self._lock:
            if self._cached_base_models and self._time_fn() < self._cache_expires_at:
                return list(self._cached_base_models)
            return await self._refresh_or_fallback_locked()

    async def get_base_models_for_request(self, request_model: str) -> list[str]:
        cached_models = self.cached_or_fallback_base_models()
        if is_known_model(request_model, cached_models):
            return cached_models
        return await self.get_base_models()

    async def get_exposed_models(self) -> list[str]:
        base_models = await self.get_base_models()
        return exposed_model_list(base_models)

    async def _refresh_or_fallback_locked(self) -> list[str]:
        try:
            base_models = await self._backend_client.fetch_codex_model_slugs(
                client_version=self._settings.backend_models_client_version
            )
        except Exception as exc:  # noqa: BLE001
            if self._cached_base_models:
                LOGGER.warning(
                    "Model catalog refresh failed; using cached model catalog: %s",
                    exc,
                )
                log_debug_event(
                    "model_catalog_fetch",
                    status="cached_fallback",
                    error=str(exc),
                    base_models=self._cached_base_models,
                )
                return list(self._cached_base_models)

            LOGGER.warning(
                "Model catalog refresh failed; using static fallback models: %s",
                exc,
            )
            log_debug_event(
                "model_catalog_fetch",
                status="static_fallback",
                error=str(exc),
                base_models=self._fallback_base_models,
            )
            return list(self._fallback_base_models)

        self._cached_base_models = base_models
        self._cache_expires_at = self._time_fn() + self._settings.model_catalog_ttl_seconds
        log_debug_event(
            "model_catalog_fetch",
            status="success",
            base_models=base_models,
            client_version=self._settings.backend_models_client_version,
        )
        return list(base_models)
