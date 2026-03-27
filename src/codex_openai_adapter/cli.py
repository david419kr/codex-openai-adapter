from __future__ import annotations

import sys

import uvicorn

from .app import create_app
from .core.config import Settings


def main(argv: list[str] | None = None) -> None:
    settings = Settings.from_sources(cli_args=argv if argv is not None else sys.argv[1:])
    app = create_app(settings)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
