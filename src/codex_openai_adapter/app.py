from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.health import router as health_router
from .api.routes.meta import router as meta_router
from .api.routes.models import router as models_router
from .api.routes.openai import router as openai_router
from .api.routes.ollama import router as ollama_router
from .core.config import Settings
from .core.logging import configure_logging
from .core.security import is_public_path, unauthorized_response
from .services.auth_store import AuthStore
from .services.backend_client import BackendClient
from .services.model_catalog import ModelCatalogService
from .services.proxy_service import ProxyService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_sources()
    configure_logging(debug=resolved_settings.debug, project_root=resolved_settings.project_root)
    auth_store = AuthStore(resolved_settings.auth_path)
    backend_client = BackendClient(resolved_settings, auth_store)
    model_catalog = ModelCatalogService(resolved_settings, backend_client)
    proxy_service = ProxyService(resolved_settings, backend_client, model_catalog)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = resolved_settings
        app.state.auth_store = auth_store
        app.state.backend_client = backend_client
        app.state.model_catalog = model_catalog
        app.state.proxy_service = proxy_service

        try:
            yield
        finally:
            await backend_client.aclose()

    app = FastAPI(
        title="codex-openai-adapter",
        version=resolved_settings.service_version,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.auth_store = auth_store
    app.state.backend_client = backend_client
    app.state.model_catalog = model_catalog
    app.state.proxy_service = proxy_service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_private_network=True,
        allow_headers=[
            "authorization",
            "content-type",
            "accept",
            "accept-encoding",
            "x-stainless-arch",
            "x-stainless-lang",
            "x-stainless-os",
            "x-stainless-package-version",
            "x-stainless-retry-count",
            "x-stainless-runtime",
            "x-stainless-runtime-version",
            "x-stainless-timeout",
            "x-api-key",
            "api-key",
        ],
    )

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):  # type: ignore[override]
        required_api_key = resolved_settings.required_client_api_key
        if (
            required_api_key
            and request.method != "OPTIONS"
            and not is_public_path(request.url.path, resolved_settings)
        ):
            from .core.security import extract_incoming_api_key

            provided_api_key = extract_incoming_api_key(request.headers)
            if provided_api_key != required_api_key:
                return unauthorized_response(
                    "Invalid or missing API key. Set Authorization: Bearer <API_KEY> to access this proxy."
                )

        response = await call_next(request)
        if request.headers.get("access-control-request-private-network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    @app.options("/{full_path:path}", include_in_schema=False)
    async def preflight_handler(full_path: str) -> Response:  # noqa: ARG001
        return Response(status_code=204)

    app.include_router(health_router)
    app.include_router(models_router)
    app.include_router(meta_router)
    app.include_router(ollama_router)
    app.include_router(openai_router)

    return app
