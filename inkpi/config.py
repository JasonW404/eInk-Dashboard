"""Validated, atomically persisted InkPi configuration.

Unified configuration system combining:
- Dashboard and display settings (persisted to JSON)
- Data source settings (persisted to JSON, secrets from env vars only)

Secrets (API keys, tokens) are never written to the config file.
They are read from environment variables at runtime.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _parse_extra_repos(raw: str) -> list[str]:
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


def _load_dotenv_file(path: str = ".env") -> None:
    """Load key-value pairs from .env into process environment.

    Existing environment variables are not overwritten.
    """

    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class PageConfig:
    id: str
    enabled: bool = True


@dataclass(frozen=True)
class DashboardConfig:
    rotation_interval_seconds: int = 300
    pages: list[PageConfig] = field(
        default_factory=lambda: [PageConfig("overview")]
    )


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
        """Return config with API key loaded from environment."""
        api_key = (
            os.getenv("EINK_GITHUB_API_KEY")
            or os.getenv("EINK_GITHUB_TOKEN")
            or ""
        )
        return GitHubConfig(
            username=self.username,
            organization=self.organization,
            commit_email=self.commit_email,
            extra_repos=self.extra_repos,
            api_key=api_key,
        )


@dataclass(frozen=True)
class WeatherConfig:
    location: str = "上海"
    timezone: str = "Asia/Shanghai"
    provider: str = "open-meteo"
    api_key: str = ""

    def with_secrets(self) -> WeatherConfig:
        """Return config with API key loaded from environment."""
        api_key = os.getenv("EINK_WEATHER_API_KEY", "")
        return WeatherConfig(
            location=self.location,
            timezone=self.timezone,
            provider=self.provider,
            api_key=api_key,
        )


@dataclass(frozen=True)
class KnowledgeCardConfig:
    local_file: str = "data/cards.json"
    remote_enabled: bool = False
    remote_url: str = ""


@dataclass(frozen=True)
class SchedulerConfig:
    system_interval_seconds: float = 30.0
    system_timeout_seconds: float = 10.0
    weather_interval_seconds: float = 3600.0
    weather_timeout_seconds: float = 30.0
    github_interval_seconds: float = 21600.0
    github_timeout_seconds: float = 180.0
    codex_interval_seconds: float = 300.0
    codex_timeout_seconds: float = 30.0
    codex_rpc_timeout_seconds: float = 20.0


@dataclass(frozen=True)
class AdaptersConfig:
    weather_timeout_seconds: int = 8
    github_timeout_seconds: int = 12
    knowledge_card_timeout_seconds: int = 8


@dataclass(frozen=True)
class InkPiConfig:
    schema_version: int = 1
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    knowledge_card: KnowledgeCardConfig = field(default_factory=KnowledgeCardConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    adapters: AdaptersConfig = field(default_factory=AdaptersConfig)


class ConfigError(ValueError):
    """Raised when persisted InkPi configuration is invalid."""


def default_config_path() -> Path:
    """Return the configured state path."""

    return Path(os.getenv("INKPI_CONFIG", "~/.config/inkpi/config.json")).expanduser()


def load_config(path: str | Path | None = None) -> InkPiConfig:
    """Load configuration from JSON file and overlay secrets from environment."""

    _load_dotenv_file()

    target = Path(path).expanduser() if path else default_config_path()
    if not target.exists():
        config = InkPiConfig()
    else:
        config = parse_config(json.loads(target.read_text(encoding="utf-8")))

    return InkPiConfig(
        schema_version=config.schema_version,
        dashboard=config.dashboard,
        display=config.display,
        github=config.github.with_secrets(),
        weather=config.weather.with_secrets(),
        knowledge_card=config.knowledge_card,
        scheduler=config.scheduler,
        adapters=config.adapters,
    )


def parse_config(raw: dict[str, Any]) -> InkPiConfig:
    """Validate a raw configuration payload."""

    if raw.get("schema_version", 1) != 1:
        raise ConfigError("unsupported schema_version")

    dashboard_raw = raw.get("dashboard") or {}
    pages = [
        PageConfig(id=str(item["id"]), enabled=bool(item.get("enabled", True)))
        for item in dashboard_raw.get("pages", [{"id": "overview"}])
    ]
    if not pages or not any(page.enabled for page in pages):
        raise ConfigError("at least one dashboard page must be enabled")
    if len({page.id for page in pages}) != len(pages):
        raise ConfigError("dashboard page ids must be unique")

    rotation = int(dashboard_raw.get("rotation_interval_seconds", 300))
    if rotation < 10:
        raise ConfigError("rotation_interval_seconds must be at least 10")

    display_raw = raw.get("display") or {}
    max_partial = int(display_raw.get("max_partial_refreshes", 50))
    if not 0 <= max_partial <= 200:
        raise ConfigError("max_partial_refreshes must be between 0 and 200")

    policy = str(display_raw.get("policy", "longevity"))
    if policy != "longevity":
        raise ConfigError("only the longevity display policy is currently supported")

    meaningful = float(display_raw.get("meaningful_change_ratio", 0.0005))
    partial = float(display_raw.get("partial_change_ratio", 0.12))
    if not 0 <= meaningful < partial <= 1:
        raise ConfigError("display change ratios are invalid")

    region_repair = int(display_raw.get("region_repair_threshold", 30))
    if not 1 <= region_repair <= 200:
        raise ConfigError("region_repair_threshold must be between 1 and 200")

    region_padding = int(display_raw.get("region_padding", 8))
    if not 0 <= region_padding <= 64:
        raise ConfigError("region_padding must be between 0 and 64")

    orientation = str(display_raw.get("orientation", "landscape"))
    valid_orientations = {"landscape", "landscape-reverse", "vertical", "vertical-reverse"}
    if orientation not in valid_orientations:
        raise ConfigError(f"orientation must be one of {valid_orientations}")

    github_raw = raw.get("github") or {}
    github_username = str(github_raw.get("username", GitHubConfig.username))
    github_org = str(github_raw.get("organization", GitHubConfig.organization))
    github_email = str(github_raw.get("commit_email", ""))
    github_repos = github_raw.get("extra_repos", [])
    if not isinstance(github_repos, list):
        github_repos = []

    weather_raw = raw.get("weather") or {}
    weather_location = str(weather_raw.get("location", WeatherConfig.location))
    weather_tz = str(weather_raw.get("timezone", WeatherConfig.timezone))
    weather_provider = str(weather_raw.get("provider", WeatherConfig.provider))

    card_raw = raw.get("knowledge_card") or {}
    card_file = str(card_raw.get("local_file", KnowledgeCardConfig.local_file))
    card_remote_enabled = bool(card_raw.get("remote_enabled", False))
    card_remote_url = str(card_raw.get("remote_url", ""))

    scheduler_raw = raw.get("scheduler") or {}
    scheduler = SchedulerConfig(
        system_interval_seconds=float(scheduler_raw.get("system_interval_seconds", 30.0)),
        system_timeout_seconds=float(scheduler_raw.get("system_timeout_seconds", 10.0)),
        weather_interval_seconds=float(scheduler_raw.get("weather_interval_seconds", 3600.0)),
        weather_timeout_seconds=float(scheduler_raw.get("weather_timeout_seconds", 30.0)),
        github_interval_seconds=float(scheduler_raw.get("github_interval_seconds", 21600.0)),
        github_timeout_seconds=float(scheduler_raw.get("github_timeout_seconds", 180.0)),
        codex_interval_seconds=float(scheduler_raw.get("codex_interval_seconds", 300.0)),
        codex_timeout_seconds=float(scheduler_raw.get("codex_timeout_seconds", 30.0)),
        codex_rpc_timeout_seconds=float(scheduler_raw.get("codex_rpc_timeout_seconds", 20.0)),
    )

    adapters_raw = raw.get("adapters") or {}
    adapters = AdaptersConfig(
        weather_timeout_seconds=int(adapters_raw.get("weather_timeout_seconds", 8)),
        github_timeout_seconds=int(adapters_raw.get("github_timeout_seconds", 12)),
        knowledge_card_timeout_seconds=int(adapters_raw.get("knowledge_card_timeout_seconds", 8)),
    )

    return InkPiConfig(
        dashboard=DashboardConfig(rotation_interval_seconds=rotation, pages=pages),
        display=DisplayConfig(
            policy=policy,
            max_partial_refreshes=max_partial,
            meaningful_change_ratio=meaningful,
            partial_change_ratio=partial,
            region_repair_threshold=region_repair,
            region_padding=region_padding,
            orientation=orientation,
        ),
        github=GitHubConfig(
            username=github_username,
            organization=github_org,
            commit_email=github_email,
            extra_repos=github_repos,
        ),
        weather=WeatherConfig(
            location=weather_location,
            timezone=weather_tz,
            provider=weather_provider,
        ),
        knowledge_card=KnowledgeCardConfig(
            local_file=card_file,
            remote_enabled=card_remote_enabled,
            remote_url=card_remote_url,
        ),
        scheduler=scheduler,
        adapters=adapters,
    )


def save_config(config: InkPiConfig, path: str | Path | None = None) -> None:
    """Atomically persist validated configuration (excluding secrets)."""

    validated = parse_config(asdict(config))
    target = Path(path).expanduser() if path else default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    config_dict = asdict(validated)
    config_dict["github"].pop("api_key", None)
    config_dict["weather"].pop("api_key", None)

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, delete=False
    ) as temporary:
        json.dump(config_dict, temporary, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.chmod(0o600)
    temporary_path.replace(target)
