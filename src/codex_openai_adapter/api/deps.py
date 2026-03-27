from __future__ import annotations

from fastapi import Request

from codex_openai_adapter.core.config import Settings
from codex_openai_adapter.services.model_catalog import ModelCatalogService
from codex_openai_adapter.services.proxy_service import ProxyService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_proxy_service(request: Request) -> ProxyService:
    return request.app.state.proxy_service


def get_model_catalog(request: Request) -> ModelCatalogService:
    return request.app.state.model_catalog
