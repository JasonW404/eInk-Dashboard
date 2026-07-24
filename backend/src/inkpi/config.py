"""Minimal v1 runtime configuration with environment-only secrets."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any


def _load_dotenv_file(path: str = ".env") -> None:
    target = Path(path)
    if not target.exists():
        return
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class DisplayConfig:
    policy: str = "longevity"
    max_partial_refreshes: int = 50
    meaningful_change_ratio: float = 0.0005
    partial_change_ratio: float = 0.12
    region_repair_threshold: int = 30
    region_padding: int = 8
    orientation: str = "landscape"


@dataclass(frozen=True)
class GitHubConfig:
    username: str = "JasonW404"
    organization: str = "ModelEngine-Group"
    commit_email: str = ""
    extra_repos: list[str] = field(default_factory=list)
    api_key: str = ""

    def with_secrets(self) -> GitHubConfig:
        return GitHubConfig(
            username=self.username,
            organization=self.organization,
            commit_email=self.commit_email,
            extra_repos=self.extra_repos,
            api_key=os.getenv("EINK_GITHUB_API_KEY") or os.getenv("EINK_GITHUB_TOKEN") or "",
        )


@dataclass(frozen=True)
class SchedulerConfig:
    github_interval_seconds: float = 21600.0
    codex_interval_seconds: float = 300.0
    codex_rpc_timeout_seconds: float = 20.0


@dataclass(frozen=True)
class AdaptersConfig:
    github_timeout_seconds: int = 12


@dataclass(frozen=True)
class InkPiConfig:
    schema_version: int = 1
    display: DisplayConfig = field(default_factory=DisplayConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    adapters: AdaptersConfig = field(default_factory=AdaptersConfig)


class ConfigError(ValueError):
    """Raised when persisted InkPi configuration is invalid."""


def default_config_path() -> Path:
    return Path(os.getenv("INKPI_CONFIG", "~/.config/inkpi/config.json")).expanduser()


def load_config(path: str | Path | None = None) -> InkPiConfig:
    _load_dotenv_file()
    target = Path(path).expanduser() if path else default_config_path()
    config = parse_config(json.loads(target.read_text(encoding="utf-8"))) if target.exists() else InkPiConfig()
    return InkPiConfig(
        schema_version=config.schema_version,
        display=config.display,
        github=config.github.with_secrets(),
        scheduler=config.scheduler,
        adapters=config.adapters,
    )


def parse_config(raw: dict[str, Any]) -> InkPiConfig:
    if raw.get("schema_version", 1) != 1:
        raise ConfigError("unsupported schema_version")

    display_raw = raw.get("display") or {}
    display = DisplayConfig(
        policy=str(display_raw.get("policy", "longevity")),
        max_partial_refreshes=int(display_raw.get("max_partial_refreshes", 50)),
        meaningful_change_ratio=float(display_raw.get("meaningful_change_ratio", 0.0005)),
        partial_change_ratio=float(display_raw.get("partial_change_ratio", 0.12)),
        region_repair_threshold=int(display_raw.get("region_repair_threshold", 30)),
        region_padding=int(display_raw.get("region_padding", 8)),
        orientation=str(display_raw.get("orientation", "landscape")),
    )
    _validate_display(display)

    github_raw = raw.get("github") or {}
    extra_repos = github_raw.get("extra_repos", [])
    if not isinstance(extra_repos, list):
        extra_repos = []
    github = GitHubConfig(
        username=str(github_raw.get("username", GitHubConfig.username)),
        organization=str(github_raw.get("organization", GitHubConfig.organization)),
        commit_email=str(github_raw.get("commit_email", "")),
        extra_repos=[str(item) for item in extra_repos],
    )

    scheduler_raw = raw.get("scheduler") or {}
    scheduler = SchedulerConfig(
        github_interval_seconds=float(scheduler_raw.get("github_interval_seconds", 21600.0)),
        codex_interval_seconds=float(scheduler_raw.get("codex_interval_seconds", 300.0)),
        codex_rpc_timeout_seconds=float(scheduler_raw.get("codex_rpc_timeout_seconds", 20.0)),
    )
    adapters_raw = raw.get("adapters") or {}
    adapters = AdaptersConfig(
        github_timeout_seconds=int(adapters_raw.get("github_timeout_seconds", 12)),
    )
    return InkPiConfig(display=display, github=github, scheduler=scheduler, adapters=adapters)


def _validate_display(config: DisplayConfig) -> None:
    if config.policy != "longevity":
        raise ConfigError("only the longevity display policy is currently supported")
    if not 0 <= config.max_partial_refreshes <= 200:
        raise ConfigError("max_partial_refreshes must be between 0 and 200")
    if not 0 <= config.meaningful_change_ratio < config.partial_change_ratio <= 1:
        raise ConfigError("display change ratios are invalid")
    if not 1 <= config.region_repair_threshold <= 200:
        raise ConfigError("region_repair_threshold must be between 1 and 200")
    if not 0 <= config.region_padding <= 64:
        raise ConfigError("region_padding must be between 0 and 64")
    valid_orientations = {"landscape", "landscape-reverse", "vertical", "vertical-reverse"}
    if config.orientation not in valid_orientations:
        raise ConfigError(f"orientation must be one of {valid_orientations}")
