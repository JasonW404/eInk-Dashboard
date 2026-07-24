"""Command-line entrypoints for InkPi services and diagnostics."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from inkpi.admin.auth import AdminAuthPolicy
from inkpi.admin.server import DEFAULT_ADMIN_HOST, DEFAULT_ADMIN_PORT, run_admin_service
from inkpi.config import load_config
from inkpi.core import DEFAULT_CORE_SOCKET, run_core_service
from inkpi.dashboard.controller import DashboardController
from inkpi.dashboard.pages.overview import OverviewPage
from inkpi.dashboard.preview_data import make_mock_overview_snapshot
from inkpi.display.service import DEFAULT_SOCKET, run_display_service
from inkpi.ipc import request


def display_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi e-ink display owner")
    parser.add_argument("--socket", default=str(DEFAULT_SOCKET))
    args = parser.parse_args()
    _logging()
    try:
        run_display_service(args.socket)
    except KeyboardInterrupt:
        return


def core_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi core orchestrator")
    parser.add_argument("--socket", default=str(DEFAULT_CORE_SOCKET))
    parser.add_argument("--display-socket", default=str(DEFAULT_SOCKET))
    parser.add_argument("--config")
    args = parser.parse_args()
    _logging()
    try:
        run_core_service(args.socket, config_path=args.config, display_socket=args.display_socket)
    except KeyboardInterrupt:
        return


def admin_main() -> None:
    parser = argparse.ArgumentParser(description="InkPi local admin web portal")
    parser.add_argument("--host", default=DEFAULT_ADMIN_HOST)
    parser.add_argument("--port", default=DEFAULT_ADMIN_PORT, type=int)
    parser.add_argument("--core-socket", default=str(DEFAULT_CORE_SOCKET))
    parser.add_argument(
        "--admin-token",
        help="Token required for mutation routes. Defaults to INKPI_ADMIN_TOKEN.",
    )
    args = parser.parse_args()
    _logging()
    auth_policy = AdminAuthPolicy(args.admin_token) if args.admin_token else None
    try:
        run_admin_service(
            host=args.host,
            port=args.port,
            core_socket=args.core_socket,
            auth_policy=auth_policy,
        )
    except KeyboardInterrupt:
        return


def control_main() -> None:
    parser = argparse.ArgumentParser(description="Control a running InkPi core service")
    parser.add_argument("--socket", default=str(DEFAULT_CORE_SOCKET))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("pages")
    page = subparsers.add_parser("page")
    page.add_argument("page_id")
    page.add_argument("state", choices=["enable", "disable"])
    args = parser.parse_args()
    if args.command == "status":
        print(request(args.socket, "get_core_status"))
    elif args.command == "pages":
        print(request(args.socket, "get_pages"))
    else:
        print(
            request(
                args.socket,
                "set_page_enabled",
                {"page_id": args.page_id, "enabled": args.state == "enable"},
            )
        )


def preview_main() -> None:
    parser = argparse.ArgumentParser(description="Render an InkPi page preview")
    parser.add_argument("page", choices=["overview"], default="overview", nargs="?")
    parser.add_argument("--output")
    parser.add_argument("--config")
    parser.add_argument(
        "--mock-data",
        action="store_true",
        help="Render with static mock data instead of live collectors.",
    )
    parser.add_argument(
        "--eink-preview",
        action="store_true",
        help="Apply 4-gray e-ink dithering to preview output.",
    )
    args = parser.parse_args()
    _logging()
    pages = [OverviewPage()]
    controller = DashboardController(pages, load_config(args.config))
    page = next(item for item in pages if item.page_id == args.page)
    snapshot = make_mock_overview_snapshot() if args.mock_data else page.collect()
    image = page.render(snapshot)
    if args.eink_preview:
        from inkpi.ui.eink_preview import eink_dither

        image = eink_dither(image)
    output = Path(args.output or f"{args.page}-preview.png")
    image.save(output)
    print(output.resolve())


def _logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
