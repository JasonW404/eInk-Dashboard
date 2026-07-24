from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inkpi.config import GitHubConfig, InkPiConfig


def make_config(
    *,
    github_username: str = "tester",
    github_org: str = "test-org",
    github_token: str = "token",
) -> InkPiConfig:
    return InkPiConfig(
        github=GitHubConfig(
            username=github_username,
            organization=github_org,
            api_key=github_token,
        ),
    )
