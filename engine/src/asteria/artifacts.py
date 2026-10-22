"""Writing and verifying a built artifacts directory (`manifest.json` + hashed JSON files)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from asteria.models import Model
from asteria.provenance import sha256_file


class IntegrityError(RuntimeError):
    """A build gate failed: the inputs do not support publishing artifacts."""


class ArtifactError(RuntimeError):
    """Artifacts are missing, unreadable, or do not match their manifest."""


def verified(root: Path) -> dict[str, object]:
    """The manifest of `root`, after re-hashing every file it lists."""
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ArtifactError(f"no manifest at {manifest_path}; run `asteria build`")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ArtifactError("manifest lists no files")
    for rel, digest in files.items():
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ArtifactError(f"manifest entry {rel!r} is not a file under {root}")
        if sha256_file(path) != digest:
            raise ArtifactError(f"{rel} does not match its manifest hash")
    return dict(manifest)


def publish(out_dir: Path, models: Mapping[str, Model], manifest: dict[str, Any]) -> Path:
    """Write `models` (relative path to model) plus a manifest into a staging directory, then swap.

    The previous `out_dir` is only removed once the new one is complete, and is moved
    aside rather than deleted first, so a crash never leaves no artifacts at all.
    """
    staging = out_dir.with_name(out_dir.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    for rel, model in models.items():
        path = staging / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(), encoding="utf-8")
    manifest["files"] = {
        p.relative_to(staging).as_posix(): sha256_file(p) for p in sorted(staging.rglob("*.json"))
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    old = out_dir.with_name(out_dir.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if out_dir.exists():
        out_dir.rename(old)
    staging.rename(out_dir)
    shutil.rmtree(old, ignore_errors=True)
    return out_dir
