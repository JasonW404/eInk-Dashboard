"""Standalone InkPi Raspberry Pi display executable entrypoint."""

from __future__ import annotations

import argparse
import logging
import os

from inkpi.display.service import run_display_service


def main() -> None:
    parser = argparse.ArgumentParser(description="InkPi e-ink display client")
    parser.add_argument(
        "--api-url", default=os.getenv("INKPI_API_URL", "http://127.0.0.1:8080")
    )
    parser.add_argument(
        "--poll-seconds",
        default=float(os.getenv("INKPI_DISPLAY_POLL_SECONDS", "2")),
        type=float,
    )
    parser.add_argument(
        "--debounce-seconds",
        default=float(os.getenv("INKPI_DISPLAY_DEBOUNCE_SECONDS", "1")),
        type=float,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        run_display_service(
            api_url=args.api_url,
            poll_interval_seconds=args.poll_seconds,
            debounce_seconds=args.debounce_seconds,
        )
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
