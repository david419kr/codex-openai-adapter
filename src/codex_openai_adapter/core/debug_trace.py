from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

DEBUG_LOGGER_NAME = "codex_openai_adapter.debug_trace"

_request_id_var: ContextVar[str | None] = ContextVar("debug_request_id", default=None)
_endpoint_var: ContextVar[str | None] = ContextVar("debug_endpoint", default=None)


def _normalize_debug_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _normalize_debug_value(value.model_dump(by_alias=True, exclude_none=True))

    if isinstance(value, dict):
        return {str(key): _normalize_debug_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize_debug_value(item) for item in value]

    if isinstance(value, bytes):
        try:
            return _normalize_debug_value(value.decode("utf-8"))
        except UnicodeDecodeError:
            return value.hex()

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return value
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value

    if value is None or isinstance(value, bool | int | float):
        return value

    return str(value)


def start_debug_request(endpoint: str, request_payload: Any) -> tuple[str, str]:
    request_id = uuid4().hex
    _request_id_var.set(request_id)
    _endpoint_var.set(endpoint)
    log_debug_event("incoming_request", payload=request_payload)
    return request_id, endpoint


def finish_debug_request(tokens: tuple[str, str] | None = None) -> None:  # noqa: ARG001
    _endpoint_var.set(None)
    _request_id_var.set(None)


def log_debug_event(event: str, **payload: Any) -> None:
    logger = logging.getLogger(DEBUG_LOGGER_NAME)
    if not logger.handlers:
        return

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": _request_id_var.get(),
        "endpoint": _endpoint_var.get(),
        "event": event,
        **{key: _normalize_debug_value(value) for key, value in payload.items()},
    }
    logger.info(json.dumps(entry, ensure_ascii=False))
