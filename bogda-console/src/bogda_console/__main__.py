from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

import uvicorn

from bogda_console.app import PROJECT_ROOT, create_app
from bogda_console.config import Settings


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bogda Console")
    parser.add_argument("--api-only", action="store_true", help="serve the development BFF on loopback 3102")
    args = parser.parse_args(argv)
    settings = Settings.from_env(os.environ)
    if args.api_only:
        app = create_app(settings)
        host, port = settings.bff_host, settings.bff_port
    else:
        app = create_app(settings, frontend_dist=PROJECT_ROOT / "frontend" / "dist")
        host, port = settings.public_host, settings.public_port
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
