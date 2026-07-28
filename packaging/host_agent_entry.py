"""Standalone InkPi HostAgent executable entrypoint."""

from __future__ import annotations

import argparse
import logging
import os

from inkpi.config import load_config
from inkpi.host_agent.client import HostAgentClient
from inkpi.host_agent.collectors import CodexCollector, GitHubCollector
from inkpi.host_agent.runner import HostAgentRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="InkPi cloud HostAgent")
    parser.add_argument("--api-url", default=os.getenv("INKPI_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--name", default=os.getenv("INKPI_AGENT_NAME", "inkpi-cloud"))
    parser.add_argument(
        "--credentials",
        default=os.getenv("INKPI_AGENT_CREDENTIALS", "~/.config/inkpi/host-agent.json"),
    )
    parser.add_argument("--config")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
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


if __name__ == "__main__":
    main()
