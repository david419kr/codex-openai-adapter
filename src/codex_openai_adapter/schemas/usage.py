from __future__ import annotations

from pydantic import BaseModel


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int