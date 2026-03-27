from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

DEFAULT_PORT = 8888
DEFAULT_AUTH_PATH = "~/.codex/auth.json"
DEFAULT_BACKEND_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
DEFAULT_STREAM_IDLE_HEARTBEAT_SECONDS = 15.0
OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are a helpful AI assistant. Provide clear, accurate, and concise responses "
    "to user questions and requests."
)


def trim_matching_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {"\"", "'"}:
        return trimmed[1:-1]
    return trimmed


def normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def normalize_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


def load_dotenv_file(dotenv_path: Path | None = None) -> None:
    dotenv = dotenv_path or Path.cwd() / ".env"
    if not dotenv.exists():
        return

    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = trim_matching_quotes(value)


def expand_auth_path(value: str) -> Path:
    return Path(value).expanduser()


@dataclass(slots=True)
class Settings:
    port: int
    auth_path: Path
    required_client_api_key: str | None
    debug: bool = False
    stream_idle_heartbeat_seconds: float = DEFAULT_STREAM_IDLE_HEARTBEAT_SECONDS
    project_root: Path = field(default_factory=Path.cwd)
    backend_responses_url: str = DEFAULT_BACKEND_RESPONSES_URL
    oauth_token_url: str = DEFAULT_OAUTH_TOKEN_URL
    codex_client_id: str = OPENAI_CODEX_CLIENT_ID
    service_name: str = "codex-openai-proxy"
    service_version: str = "0.0.0-proxy"
    public_paths: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"/health", "/api/tags", "/chat-test", "/chat-test.html"}
        )
    )

    @classmethod
    def from_sources(
        cls,
        cli_args: Sequence[str] | None = None,
        cwd: Path | None = None,
    ) -> "Settings":
        load_dotenv_file((cwd or Path.cwd()) / ".env")

        parser = argparse.ArgumentParser(prog="codex-openai-adapter")
        parser.add_argument("-p", "--port", dest="port")
        parser.add_argument("--auth-path", dest="auth_path")
        args = parser.parse_args(list(cli_args) if cli_args is not None else None)

        port = int(args.port or os.getenv("PORT") or DEFAULT_PORT)
        auth_path = expand_auth_path(
            args.auth_path or os.getenv("CODEX_AUTH_PATH") or DEFAULT_AUTH_PATH
        )
        required_client_api_key = normalize_optional(os.getenv("API_KEY"))
        debug = normalize_bool(os.getenv("DEBUG"))
        stream_idle_heartbeat_seconds = normalize_float(
            os.getenv("STREAM_IDLE_HEARTBEAT_SECONDS"),
            DEFAULT_STREAM_IDLE_HEARTBEAT_SECONDS,
        )
        backend_responses_url = (
            os.getenv("CODEX_BACKEND_RESPONSES_URL") or DEFAULT_BACKEND_RESPONSES_URL
        )
        oauth_token_url = os.getenv("CODEX_OAUTH_TOKEN_URL") or DEFAULT_OAUTH_TOKEN_URL

        return cls(
            port=port,
            auth_path=auth_path,
            required_client_api_key=required_client_api_key,
            debug=debug,
            stream_idle_heartbeat_seconds=stream_idle_heartbeat_seconds,
            project_root=(cwd or Path.cwd()),
            backend_responses_url=backend_responses_url,
            oauth_token_url=oauth_token_url,
        )
