from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TokenData(BaseModel):
    access_token: str
    account_id: str
    refresh_token: str | None = None

    model_config = ConfigDict(extra="allow")


class AuthData(BaseModel):
    api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    tokens: TokenData | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TokenRefreshResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    account_id: str | None = None
    id_token: str | None = None

    model_config = ConfigDict(extra="allow")


JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None