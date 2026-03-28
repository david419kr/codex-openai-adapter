from __future__ import annotations

from fastapi import APIRouter, Depends

from codex_openai_ollama_proxy.api.deps import get_model_catalog
from codex_openai_ollama_proxy.services.model_catalog import ModelCatalogService

router = APIRouter(tags=["models"])


def _models_payload(models: list[str]) -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "created": 1687882411,
                "owned_by": "openai",
            }
            for model in models
        ],
    }


@router.get("/models")
@router.get("/v1/models")
async def models(
    model_catalog: ModelCatalogService = Depends(get_model_catalog),
) -> dict[str, object]:
    return _models_payload(await model_catalog.get_exposed_models())
