"""Paths and pinned source identifiers.

Everything Asteria reads from the outside world is pinned here, so a build is
reproducible and every artifact can say exactly what it was made from.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# RocketPy repository, release v1.13.0. The PyPI package `rocketpy==1.13.0`
# (pinned in pyproject.toml) is built from this same commit.
ROCKETPY_REPO_URL = "https://github.com/RocketPy-Team/RocketPy.git"
ROCKETPY_TAG = "v1.13.0"
ROCKETPY_COMMIT = "9bd6ad3af8f97bafa3201d4e70eba2877e66e040"
ROCKETPY_SPARSE_PATHS = ("docs/examples", "data")


@dataclass(frozen=True)
class Paths:
    """Filesystem layout for one Asteria home directory."""

    home: Path

    @property
    def cache(self) -> Path:
        return self.home / "cache"

    @property
    def rocketpy_checkout(self) -> Path:
        return self.cache / f"rocketpy-{ROCKETPY_COMMIT[:12]}"

    @property
    def era5_cache(self) -> Path:
        return self.cache / "era5"

    @property
    def gracefo_cache(self) -> Path:
        return self.cache / "gracefo"

    @property
    def artifacts(self) -> Path:
        return self.home / "artifacts"

    @property
    def rockets_artifacts(self) -> Path:
        return self.artifacts / "rockets"

    @property
    def orbits_artifacts(self) -> Path:
        return self.artifacts / "orbits"

    @property
    def omni_cache(self) -> Path:
        return self.cache / "omni"

    @property
    def spacetrack_cache(self) -> Path:
        return self.cache / "spacetrack"


REPO_ROOT = Path(__file__).resolve().parents[3]


def env_files() -> list[Path]:
    """Settings files, highest priority first; all git-ignored, never committed.

    `.env.local` at the repo root is the documented place. `.env` beside it, and the
    earlier per-folder `engine/.env.local` and `engine/.env`, are read too, so a key
    saved in any of them works. A blank value never hides a value set further down.
    """
    return [
        REPO_ROOT / ".env.local",
        REPO_ROOT / ".env",
        REPO_ROOT / "engine" / ".env.local",
        REPO_ROOT / "engine" / ".env",
    ]


def read_dotenv(path: Path) -> dict[str, str]:
    """KEY=value lines; blank lines and # comments ignored; surrounding quotes stripped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def file_setting(name: str, files: Sequence[Path]) -> str:
    """The first non-empty value of `name` in `files` (in order), else ""."""
    for path in files:
        value = read_dotenv(path).get(name, "")
        if value:
            return value
    return ""


def setting(name: str, default: str = "") -> str:
    """A setting: the process environment, then the settings files, then `default`."""
    return os.environ.get(name) or file_setting(name, env_files()) or default


def default_home() -> Path:
    """`ASTERIA_HOME` if set, else `<repo>/.asteria`."""
    home = setting("ASTERIA_HOME")
    if home:
        return Path(home).expanduser().resolve()
    return REPO_ROOT / ".asteria"


def paths() -> Paths:
    return Paths(default_home())
