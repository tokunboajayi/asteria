"""The settings file: one .env.local at the repo root, environment wins over the file."""

from pathlib import Path

import pytest

from asteria import config


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "engine").mkdir()
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("ASTERIA_TEST_KEY", raising=False)
    return tmp_path


def test_root_file_is_read(repo: Path) -> None:
    text = '# comment\n\nASTERIA_TEST_KEY="from root"\n'
    (repo / ".env.local").write_text(text, encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "from root"


def test_environment_wins_over_file(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / ".env.local").write_text("ASTERIA_TEST_KEY=file\n", encoding="utf-8")
    monkeypatch.setenv("ASTERIA_TEST_KEY", "env")
    assert config.setting("ASTERIA_TEST_KEY") == "env"


def test_legacy_engine_file_used_only_without_root_file(repo: Path) -> None:
    (repo / "engine" / ".env.local").write_text("ASTERIA_TEST_KEY=legacy\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "legacy"
    (repo / ".env.local").write_text("ASTERIA_TEST_KEY=root\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "root"


def test_missing_setting_falls_back_to_default(repo: Path) -> None:
    assert config.setting("ASTERIA_TEST_KEY", "default") == "default"
