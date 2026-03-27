from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from codex_openai_adapter.core.errors import AuthenticationRefreshError
from codex_openai_adapter.schemas.auth import AuthData, TokenRefreshResponse


class AuthStore:
    def __init__(self, auth_path: Path):
        self._auth_path = auth_path.expanduser()
        self._lock = asyncio.Lock()
        self._cached: AuthData | None = None

    @property
    def auth_path(self) -> Path:
        return self._auth_path

    async def snapshot(self) -> AuthData:
        async with self._lock:
            current = await self._load_locked()
            return current.model_copy(deep=True)

    async def refresh_access_token_if_needed(
        self,
        previous_access_token: str,
        client: httpx.AsyncClient,
        oauth_token_url: str,
        codex_client_id: str,
    ) -> AuthData:
        async with self._lock:
            current = await self._load_locked()
            tokens = current.tokens
            if tokens is None:
                raise AuthenticationRefreshError("No token auth configured in auth.json")
            if tokens.access_token != previous_access_token:
                return current.model_copy(deep=True)
            if not tokens.refresh_token:
                raise AuthenticationRefreshError("refresh_token missing in auth.json")

            refresh_token = tokens.refresh_token
            fallback_account_id = tokens.account_id

            response = await client.post(
                oauth_token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": codex_client_id,
                },
            )

            if response.is_error:
                raise AuthenticationRefreshError(
                    f"Codex OAuth refresh failed {response.status_code}: {response.text}"
                )

            payload = TokenRefreshResponse.model_validate(response.json())
            next_access_token = (payload.access_token or "").strip()
            if not next_access_token:
                raise AuthenticationRefreshError(
                    "Codex OAuth refresh response missing access_token"
                )

            next_refresh_token = (payload.refresh_token or refresh_token).strip() or refresh_token
            next_account_id = (payload.account_id or fallback_account_id).strip() or fallback_account_id

            data = current.model_dump(by_alias=True, exclude_none=False)
            tokens_data = data.setdefault("tokens", {})
            tokens_data["access_token"] = next_access_token
            tokens_data["account_id"] = next_account_id
            tokens_data["refresh_token"] = next_refresh_token
            if payload.id_token and payload.id_token.strip():
                tokens_data["id_token"] = payload.id_token.strip()
            data["last_refresh"] = datetime.now(UTC).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            )

            updated = AuthData.model_validate(data)
            await self._persist_locked(updated)
            return updated.model_copy(deep=True)

    async def _load_locked(self) -> AuthData:
        if self._cached is None:
            self._cached = await asyncio.to_thread(self._read_from_disk)
        return self._cached

    def _read_from_disk(self) -> AuthData:
        try:
            content = self._auth_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AuthenticationRefreshError(
                f"Failed to read auth.json at {self._auth_path}"
            ) from exc

        try:
            return AuthData.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationRefreshError(
                f"Failed to parse auth.json at {self._auth_path}"
            ) from exc

    async def _persist_locked(self, auth_data: AuthData) -> None:
        await asyncio.to_thread(self._write_to_disk, auth_data)
        self._cached = auth_data

    def _write_to_disk(self, auth_data: AuthData) -> None:
        payload = auth_data.model_dump_json(
            by_alias=True,
            exclude_none=False,
            indent=2,
        ) + "\n"

        self._auth_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=self._auth_path.name + ".",
            suffix=".tmp",
            dir=self._auth_path.parent,
            text=True,
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temp_name, self._auth_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
