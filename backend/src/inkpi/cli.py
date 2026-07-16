"""Command-line entrypoints for InkPi services and diagnostics."""

from __future__ import annotations

import argparse
import logging
import os

from inkpi.config import load_config
from inkpi.display.service import run_display_service


def display_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi e-ink display owner")
    parser.add_argument(
        "--api-url",
        default=os.getenv("INKPI_API_URL", "http://127.0.0.1:8080"),
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
    _logging()
    try:
        run_display_service(
            api_url=args.api_url,
            poll_interval_seconds=args.poll_seconds,
            debounce_seconds=args.debounce_seconds,
        )
    except KeyboardInterrupt:
        return


def api_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi persistent application API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--database-url", default=os.getenv("INKPI_DATABASE_URL"))
    parser.add_argument("--web-dist", help="Built InkPi Web directory (defaults to frontend/dist)")
    parser.add_argument("--render-base-url", default=os.getenv("INKPI_RENDER_BASE_URL"))
    args = parser.parse_args()
    _logging()

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


def host_agent_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi optional Ubuntu host agent")
    parser.add_argument("--api-url", default=os.getenv("INKPI_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--name", default=os.getenv("INKPI_AGENT_NAME", "ubuntu-host"))
    parser.add_argument(
        "--credentials",
        default=os.getenv("INKPI_AGENT_CREDENTIALS", "~/.config/inkpi/host-agent.json"),
    )
    parser.add_argument("--config")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    _logging()

    from inkpi.host_agent.client import HostAgentClient
    from inkpi.host_agent.collectors import CodexCollector, GitHubCollector
    from inkpi.host_agent.runner import HostAgentRunner

    config = load_config(args.config)
    client = HostAgentClient(
        args.api_url,
        args.name,
        args.credentials,
        enrollment_token=os.getenv("INKPI_AGENT_ENROLLMENT_TOKEN"),
    )
    runner = HostAgentRunner(
        client,
        [
            CodexCollector(config.scheduler.codex_interval_seconds),
            GitHubCollector(config, config.scheduler.github_interval_seconds),
        ],
    )
    try:
        runner.run_once() if args.once else runner.run_forever()
    except KeyboardInterrupt:
        runner.stop()
    finally:
        client.close()


def network_helper_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi privileged NetworkManager helper")
    parser.add_argument(
        "--socket",
        default=os.getenv("INKPI_NETWORK_HELPER_SOCKET", "/run/inkpi-network-helper/helper.sock"),
    )
    args = parser.parse_args()
    _logging()

    from inkpi.network.privileged import helper_main

    try:
        helper_main(args.socket)
    except KeyboardInterrupt:
        return


def _logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
