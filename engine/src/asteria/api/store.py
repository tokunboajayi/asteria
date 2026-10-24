"""Read-only, verified view of a built artifacts directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asteria.artifacts import verified
from asteria.models import (
    CorrectionReport,
    Debrief,
    Fleet,
    FleetFingerprint,
    FlightDetail,
    GapMap,
    NextBest,
    OrbitFleet,
    SpaceWeatherSeries,
)


@dataclass(frozen=True)
class RocketStore:
    fleet: Fleet
    flights: dict[str, FlightDetail]
    debriefs: dict[str, Debrief]
    gapmap: GapMap
    correction: CorrectionReport
    nextbest: NextBest
    fingerprint: FleetFingerprint
    manifest: dict[str, object]


def load_rockets(root: Path) -> RocketStore:
    manifest = verified(root)

    def read(rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8")

    fleet = Fleet.model_validate_json(read("fleet.json"))
    flights = {
        f.id: FlightDetail.model_validate_json(read(f"flights/{f.id}.json")) for f in fleet.flights
    }
    debriefs = {
        f.id: Debrief.model_validate_json(read(f"debriefs/{f.id}.json")) for f in fleet.flights
    }
    return RocketStore(
        fleet=fleet,
        flights=flights,
        debriefs=debriefs,
        gapmap=GapMap.model_validate_json(read("gapmap.json")),
        correction=CorrectionReport.model_validate_json(read("correction.json")),
        nextbest=NextBest.model_validate_json(read("nextbest.json")),
        fingerprint=FleetFingerprint.model_validate_json(read("fingerprint.json")),
        manifest=manifest,
    )


@dataclass(frozen=True)
class OrbitStore:
    fleet: OrbitFleet
    spaceweather: SpaceWeatherSeries
    gapmap: GapMap
    manifest: dict[str, object]


def load_orbits(root: Path) -> OrbitStore:
    manifest = verified(root)

    def read(rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8")

    return OrbitStore(
        fleet=OrbitFleet.model_validate_json(read("fleet.json")),
        spaceweather=SpaceWeatherSeries.model_validate_json(read("spaceweather.json")),
        gapmap=GapMap.model_validate_json(read("gapmap.json")),
        manifest=manifest,
    )
