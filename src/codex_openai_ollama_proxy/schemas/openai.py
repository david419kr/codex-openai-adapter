from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .usage import Usage


class ChatMessageToolFunction(BaseModel):
    name: str
    arguments: Any = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ChatMessageToolCall(BaseModel):
    id: str | None = None
    call_type: str | None = Field(default=None, alias="type")
    function: ChatMessageToolFunction

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ChatMessage(BaseModel):
    role: str
    content: Any = None
    tool_call_id: str | None = None
    tool_calls: list[ChatMessageToolCall] | None = None

    model_config = ConfigDict(extra="allow")


class ChatCompletionsRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    stream: bool | None = None
    tools: list[Any] | None = None
    tool_choice: Any | None = None
    reasoning: Any | None = None
    reasoning_effort: str | None = Field(
        default=None,
        validation_alias=AliasChoices("reasoning_effort", "reasoningEffort"),
    )

    model_config = ConfigDict(extra="allow")


class ChatToolFunction(BaseModel):
    name: str
    arguments: str


class ChatToolCall(BaseModel):
    id: str
    call_type: str = Field(alias="type")
    function: ChatToolFunction

    model_config = ConfigDict(populate_by_name=True)


class ChatResponseMessage(BaseModel):
    role: str
    content: str
    tool_calls: list[ChatToolCall] | None = None


class Choice(BaseModel):
    index: int
    message: ChatResponseMessage
    finish_reason: str | None = None


class ChatCompletionsResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[Choice]
    usage: Usage | None = None
