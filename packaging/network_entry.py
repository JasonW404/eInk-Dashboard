"""Standalone InkPi Raspberry Pi network executable entrypoint."""

from __future__ import annotations

import argparse
import logging
import os

from inkpi.network.service import run_network_service


def main() -> None:
    parser = argparse.ArgumentParser(description="InkPi Pi network client")
    parser.add_argument("--api-url", default=os.getenv("INKPI_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument(
        "--poll-seconds",
        default=float(os.getenv("INKPI_NETWORK_POLL_SECONDS", "5")),
        type=float,
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        run_network_service(args.api_url, poll_seconds=args.poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
