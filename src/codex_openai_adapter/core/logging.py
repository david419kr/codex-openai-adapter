from __future__ import annotations

import logging
from pathlib import Path

from codex_openai_adapter.core.debug_trace import DEBUG_LOGGER_NAME


def configure_logging(*, debug: bool = False, project_root: Path | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

    debug_logger = logging.getLogger(DEBUG_LOGGER_NAME)
    for handler in list(debug_logger.handlers):
        handler.close()
        debug_logger.removeHandler(handler)
    debug_logger.propagate = False

    if debug and project_root is not None:
        log_path = project_root / "logs" / "debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        debug_logger.setLevel(logging.INFO)
        debug_logger.addHandler(handler)


logger = logging.getLogger("codex_openai_adapter")
