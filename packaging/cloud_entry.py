"""Standalone InkPi cloud executable entrypoint."""

from __future__ import annotations

import argparse
import logging
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="InkPi cloud control plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--database-url", default=os.getenv("INKPI_DATABASE_URL"))
    parser.add_argument("--web-dist", required=True)
    parser.add_argument("--render-base-url", default=os.getenv("INKPI_RENDER_BASE_URL"))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    import uvicorn

    from inkpi.api import create_app

    render_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    render_base_url = args.render_base_url or f"http://{render_host}:{args.port}"
    uvicorn.run(
        create_app(
            args.database_url,
            web_dist=args.web_dist,
            render_base_url=render_base_url,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
