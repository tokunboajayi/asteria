from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from asteria import cli
from asteria.api.app import app
from asteria.artifacts import ArtifactError, publish, verified
from asteria.models import Quote
from asteria.provenance import sha256_file


def _built(root: Path) -> Path:
    publish(root, {"a.json": Quote(value_m=1.0, quote="1 m")}, {"generated_at": "t"})
    return root


def test_publish_then_verified_round_trips(tmp_path: Path) -> None:
    root = _built(tmp_path / "out")
    assert list(verified(root)["files"]) == ["a.json"]  # type: ignore[call-overload]


def test_publish_replaces_previous_output_and_leaves_no_leftovers(tmp_path: Path) -> None:
    root = _built(tmp_path / "out")
    publish(root, {"b.json": Quote(value_m=2.0, quote="2 m")}, {})
    assert sorted(p.name for p in root.iterdir()) == ["b.json", "manifest.json"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"]


def test_verified_rejects_a_changed_file(tmp_path: Path) -> None:
    root = _built(tmp_path / "out")
    (root / "a.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactError, match="manifest hash"):
        verified(root)


def test_verified_rejects_a_path_outside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "out"
    root.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text("{}", encoding="utf-8")
    manifest = {"files": {"../secret.json": sha256_file(outside)}}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ArtifactError, match="not a file under"):
        verified(root)


def test_server_starts_and_reports_503_when_artifacts_are_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("ASTERIA_ARTIFACTS", str(tmp_path))
    monkeypatch.setenv("ASTERIA_ORBITS_ARTIFACTS", str(tmp_path / "none"))
    with TestClient(app) as client:
        assert client.get("/health").json()["ok"] is False
        assert client.get("/api/rockets/fleet").status_code == 503


def test_cli_verify_reports_instead_of_crashing_when_nothing_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ASTERIA_HOME", str(tmp_path))
    assert cli.main(["verify"]) == 1
    assert "asteria fetch" in capsys.readouterr().err
