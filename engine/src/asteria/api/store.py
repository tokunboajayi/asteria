"""Read-only, verified view of a built artifacts directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asteria.models import CorrectionReport, Debrief, Fleet, FlightDetail, GapMap, NextBest
from asteria.provenance import sha256_file


class ArtifactError(RuntimeError):
    """Artifacts are missing, unreadable, or do not match their manifest."""


@dataclass(frozen=True)
class RocketStore:
    fleet: Fleet
    flights: dict[str, FlightDetail]
    debriefs: dict[str, Debrief]
    gapmap: GapMap
    correction: CorrectionReport
    nextbest: NextBest
    manifest: dict[str, object]


def _verified(root: Path) -> dict[str, object]:
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


def load_rockets(root: Path) -> RocketStore:
    manifest = _verified(root)

    def read(rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8")

    fleet = Fleet.model_validate_json(read("fleet.json"))
    flights = {
        f.id: FlightDetail.model_validate_json(read(f"flights/{f.id}.json")) for f in fleet.flights
    }
    debriefs = {f.id: Debrief.model_validate_json(read(f"debriefs/{f.id}.json")) for f in fleet.flights}
    return RocketStore(
        fleet=fleet,
        flights=flights,
        debriefs=debriefs,
        gapmap=GapMap.model_validate_json(read("gapmap.json")),
        correction=CorrectionReport.model_validate_json(read("correction.json")),
        nextbest=NextBest.model_validate_json(read("nextbest.json")),
        manifest=manifest,
    )
