from __future__ import annotations

from fastapi import APIRouter, Depends

from codex_openai_ollama_proxy.api.deps import get_settings
from codex_openai_ollama_proxy.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}
