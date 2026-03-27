from __future__ import annotations

from fastapi import APIRouter

from codex_openai_adapter.services.model_resolution import exposed_model_list

router = APIRouter(tags=["models"])


def _models_payload() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "created": 1687882411,
                "owned_by": "openai",
            }
            for model in exposed_model_list()
        ],
    }


@router.get("/models")
@router.get("/v1/models")
def models() -> dict[str, object]:
    return _models_payload()
