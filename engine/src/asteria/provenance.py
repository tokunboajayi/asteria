"""File hashing and provenance records."""

from __future__ import annotations

import hashlib
from pathlib import Path

from asteria.models import SourceFile

_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def source_file(root: Path, relative: str) -> SourceFile:
    """Record a source file by its path relative to `root` and its SHA-256."""
    full = (root / relative).resolve()
    if not full.is_relative_to(root.resolve()):
        raise ValueError(f"{relative!r} escapes the source root")
    if not full.is_file():
        raise FileNotFoundError(full)
    return SourceFile(path=relative, sha256=sha256_file(full), bytes=full.stat().st_size)
