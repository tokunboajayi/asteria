"""Fetch the pinned RocketPy repository (notebooks + published data).

Uses a partial, sparse git checkout of exactly one commit and refuses to
proceed if the checked-out commit is not the pinned one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from asteria.config import ROCKETPY_COMMIT, ROCKETPY_REPO_URL, ROCKETPY_SPARSE_PATHS


class SourceIntegrityError(RuntimeError):
    """The local checkout is not the pinned commit."""


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def head_commit(checkout: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=checkout)


def verify(checkout: Path) -> None:
    """Raise unless `checkout` is a clean checkout of the pinned commit."""
    if not (checkout / ".git").exists():
        raise SourceIntegrityError(f"{checkout} is not a git checkout")
    commit = head_commit(checkout)
    if commit != ROCKETPY_COMMIT:
        raise SourceIntegrityError(f"expected {ROCKETPY_COMMIT}, found {commit}")
    dirty = _git(["status", "--porcelain", "--untracked-files=no"], cwd=checkout)
    if dirty:
        raise SourceIntegrityError(f"checkout has local modifications:\n{dirty}")


def ensure_checkout(checkout: Path) -> Path:
    """Return a verified checkout at `checkout`, fetching it if needed."""
    if checkout.exists():
        try:
            verify(checkout)
            return checkout
        except (SourceIntegrityError, subprocess.CalledProcessError):
            shutil.rmtree(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    tmp = checkout.with_name(checkout.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    _git(["init", "-q", str(tmp)])
    _git(["config", "core.autocrlf", "false"], cwd=tmp)
    _git(["config", "core.eol", "lf"], cwd=tmp)
    _git(["remote", "add", "origin", ROCKETPY_REPO_URL], cwd=tmp)
    _git(["sparse-checkout", "set", *ROCKETPY_SPARSE_PATHS], cwd=tmp)
    _git(["fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ROCKETPY_COMMIT], cwd=tmp)
    _git(["checkout", "-q", "FETCH_HEAD"], cwd=tmp)
    verify(tmp)
    tmp.rename(checkout)
    return checkout
