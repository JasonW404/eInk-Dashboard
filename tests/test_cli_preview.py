from __future__ import annotations

import sys

from PIL import Image

from inkpi import cli
from inkpi.config import InkPiConfig


def test_preview_mock_data_skips_live_collect(tmp_path, monkeypatch) -> None:
    class FakePage:
        page_id = "overview"

        def collect(self):
            raise AssertionError("live collect should not run")

        def render(self, snapshot):
            assert snapshot.github.user_monthly_commit_count == 50
            return Image.new("L", (800, 480), 255)

    output = tmp_path / "overview.png"
    monkeypatch.setattr(sys, "argv", ["inkpi-preview", "overview", "--mock-data", "--output", str(output)])
    monkeypatch.setattr(cli, "OverviewPage", lambda: FakePage())
    monkeypatch.setattr(cli, "load_config", lambda path=None: InkPiConfig())

    cli.preview_main()

    assert output.exists()
