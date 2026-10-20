from __future__ import annotations

from pathlib import Path

import pytest

from asteria.config import paths


@pytest.fixture(scope="session")
def checkout() -> Path:
    """The pinned RocketPy checkout; tests that need it skip if it is absent."""
    root = paths().rocketpy_checkout
    if not (root / "docs" / "examples").is_dir():
        pytest.skip("pinned RocketPy checkout not fetched (run `asteria fetch`)")
    return root


@pytest.fixture
def csv_file(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Write a small TEST-ONLY CSV fixture and return its directory and name."""

    def write(name: str, text: str) -> tuple[Path, str]:
        (tmp_path / name).write_text(text, encoding="utf-8")
        return tmp_path, name

    return write
