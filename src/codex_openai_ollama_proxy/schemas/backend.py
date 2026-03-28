from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponsesApiRequest(BaseModel):
    model: str
    instructions: str
    input: list[dict[str, Any]]
    tools: list[Any] = Field(default_factory=list)
    tool_choice: Any = "auto"
    parallel_tool_calls: bool = False
    temperature: float | None = None
    reasoning: Any | None = None
    store: bool = False
    stream: bool = True
    include: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")