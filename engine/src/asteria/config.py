"""Paths and pinned source identifiers.

Everything Asteria reads from the outside world is pinned here, so a build is
reproducible and every artifact can say exactly what it was made from.
"""

from __future__ import annotations

import os
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
    def artifacts(self) -> Path:
        return self.home / "artifacts"

    @property
    def rockets_artifacts(self) -> Path:
        return self.artifacts / "rockets"


def default_home() -> Path:
    """`ASTERIA_HOME` if set, else `<repo>/.asteria`."""
    env = os.environ.get("ASTERIA_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[3] / ".asteria"


def paths() -> Paths:
    return Paths(default_home())
