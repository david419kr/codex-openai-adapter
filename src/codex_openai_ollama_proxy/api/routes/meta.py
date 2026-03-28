from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from codex_openai_ollama_proxy.api.deps import get_settings
from codex_openai_ollama_proxy.core.config import Settings

router = APIRouter(tags=["meta"])


@router.get("/api/version")
def api_version(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"version": settings.service_version}


@router.get("/chat-test", include_in_schema=False)
@router.get("/chat-test.html", include_in_schema=False)
def chat_test(settings: Settings = Depends(get_settings)) -> FileResponse:
    return FileResponse(settings.project_root / "tests" / "chat-test.html")
