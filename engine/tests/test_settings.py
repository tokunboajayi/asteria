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


def test_files_are_read_in_priority_order(repo: Path) -> None:
    (repo / "engine" / ".env.local").write_text("ASTERIA_TEST_KEY=legacy\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "legacy"
    (repo / ".env").write_text("ASTERIA_TEST_KEY=root-env\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "root-env"
    (repo / ".env.local").write_text("ASTERIA_TEST_KEY=root-local\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "root-local"


def test_blank_value_in_a_higher_file_does_not_hide_a_lower_one(repo: Path) -> None:
    (repo / ".env.local").write_text("ASTERIA_TEST_KEY=\n", encoding="utf-8")
    (repo / ".env").write_text("ASTERIA_TEST_KEY=saved\n", encoding="utf-8")
    assert config.setting("ASTERIA_TEST_KEY") == "saved"


def test_missing_setting_falls_back_to_default(repo: Path) -> None:
    assert config.setting("ASTERIA_TEST_KEY", "default") == "default"


def test_ready_is_503_when_rocket_artifacts_do_not_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ASTERIA_ARTIFACTS", str(tmp_path / "missing"))
    monkeypatch.setenv("ASTERIA_ORBITS_ARTIFACTS", str(tmp_path / "missing-orbits"))
    from asteria.api.app import app

    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200 and h.json()["ok"] is False and h.json()["detail"]
        assert client.get("/ready").status_code == 503
