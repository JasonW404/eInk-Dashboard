from __future__ import annotations

import os

from PIL import Image

from inkpi.config import DashboardConfig, InkPiConfig, PageConfig, load_config, save_config
from inkpi.dashboard.controller import DashboardController


class FakePage:
    def __init__(self, page_id: str) -> None:
        self.page_id = page_id
        self.name = page_id.title()

    def collect(self):
        return self.page_id

    def render(self, snapshot):
        return Image.new("L", (800, 480), 255 if snapshot == "one" else 0)


def test_config_round_trip_is_atomic_and_validated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("inkpi.config._load_dotenv_file", lambda *a, **kw: None)
    monkeypatch.delenv("EINK_GITHUB_API_KEY", raising=False)
    monkeypatch.delenv("EINK_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("EINK_WEATHER_API_KEY", raising=False)

    path = tmp_path / "config.json"
    config = InkPiConfig(
        dashboard=DashboardConfig(
            rotation_interval_seconds=30,
            pages=[PageConfig("one"), PageConfig("two", False)],
        )
    )

    save_config(config, path)

    assert load_config(path) == config
    assert list(tmp_path.iterdir()) == [path]


def test_dashboard_rejects_disabling_last_page(tmp_path) -> None:
    config = InkPiConfig(
        dashboard=DashboardConfig(rotation_interval_seconds=30, pages=[PageConfig("one")])
    )
    controller = DashboardController([FakePage("one")], config, str(tmp_path / "config.json"))

    result = controller.set_page_enabled("one", False)

    assert not result.accepted
    assert result.error_code == "last_enabled_page"


def test_dashboard_enable_disable_is_idempotent_and_persisted(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = InkPiConfig(
        dashboard=DashboardConfig(
            rotation_interval_seconds=30,
            pages=[PageConfig("one"), PageConfig("two")],
        )
    )
    controller = DashboardController([FakePage("one"), FakePage("two")], config, str(path))

    first = controller.set_page_enabled("two", False)
    second = controller.set_page_enabled("two", False)

    assert first.accepted and second.accepted
    assert [page.enabled for page in controller.get_pages()] == [True, False]
    assert [page.enabled for page in load_config(path).dashboard.pages] == [True, False]


def test_dashboard_advances_after_page_failure(tmp_path) -> None:
    class BrokenPage(FakePage):
        def collect(self):
            raise RuntimeError("broken")

    config = InkPiConfig(
        dashboard=DashboardConfig(
            rotation_interval_seconds=30,
            pages=[PageConfig("broken"), PageConfig("two")],
        )
    )
    controller = DashboardController(
        [BrokenPage("broken"), FakePage("two")],
        config,
        str(tmp_path / "config.json"),
    )

    try:
        controller.render_next()
    except RuntimeError:
        pass

    page_id, _ = controller.render_next()
    assert page_id == "two"
