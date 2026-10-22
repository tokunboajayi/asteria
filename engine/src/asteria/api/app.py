"""Asteria API: serves verified, pre-built artifacts. Read-only by design."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from asteria import __version__
from asteria.api.store import ArtifactError, OrbitStore, RocketStore, load_orbits, load_rockets
from asteria.config import paths, setting
from asteria.models import (
    CorrectionReport,
    Debrief,
    Fleet,
    FleetFingerprint,
    FlightDetail,
    GapMap,
    Health,
    NextBest,
    OrbitFleet,
    OrbitsStatus,
    SpaceWeatherSeries,
)

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ORBITS_GATED = (
    "Storm Ghost needs historical orbit element sets from Space-Track.org (US Space Force), "
    "which require a free account. No orbit artifacts have been built yet, so nothing is shown. "
    "Add SPACETRACK_USER and SPACETRACK_PASSWORD to .env.local in the Asteria folder, then run "
    "`asteria build-orbits`."
)


def _artifacts_root() -> Path:
    override = os.environ.get("ASTERIA_ARTIFACTS")
    return Path(override) if override else paths().rockets_artifacts


def _orbits_root() -> Path:
    override = os.environ.get("ASTERIA_ORBITS_ARTIFACTS")
    return Path(override) if override else paths().orbits_artifacts


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.rockets = None
    app.state.load_error = None
    try:
        app.state.rockets = load_rockets(_artifacts_root())
    except ArtifactError as exc:
        app.state.load_error = str(exc)
    app.state.orbits = None
    app.state.orbits_error = None
    if (_orbits_root() / "manifest.json").is_file():
        try:
            app.state.orbits = load_orbits(_orbits_root())
        except ArtifactError as exc:
            app.state.orbits_error = str(exc)
    yield


app = FastAPI(
    title="Asteria API",
    version=__version__,
    description="Ghost vs reality: RocketPy reconstructions against published flight logs.",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in setting("ASTERIA_WEB_ORIGINS", DEFAULT_ORIGINS).split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _rockets(request: Request) -> RocketStore:
    store: RocketStore | None = request.app.state.rockets
    if store is None:
        raise HTTPException(status_code=503, detail=request.app.state.load_error or "not loaded")
    return store


@app.get("/health", response_model=Health)
def health(request: Request) -> Health:
    store: RocketStore | None = request.app.state.rockets
    return Health(
        ok=store is not None,
        rocket_flights=len(store.fleet.flights) if store else 0,
        orbits_available=request.app.state.orbits is not None,
        engine_version=__version__,
    )


@app.get("/api/rockets/fleet", response_model=Fleet)
def fleet(request: Request) -> Fleet:
    return _rockets(request).fleet


@app.get("/api/rockets/flights/{flight_id}", response_model=FlightDetail)
def flight(flight_id: str, request: Request) -> FlightDetail:
    store = _rockets(request)
    if flight_id not in store.flights:
        raise HTTPException(status_code=404, detail="unknown flight")
    return store.flights[flight_id]


@app.get("/api/rockets/flights/{flight_id}/debrief", response_model=Debrief)
def flight_debrief(flight_id: str, request: Request) -> Debrief:
    store = _rockets(request)
    if flight_id not in store.debriefs:
        raise HTTPException(status_code=404, detail="unknown flight")
    return store.debriefs[flight_id]


@app.get("/api/rockets/gapmap", response_model=GapMap)
def gap_map(request: Request) -> GapMap:
    return _rockets(request).gapmap


@app.get("/api/rockets/correction", response_model=CorrectionReport)
def correction_report(request: Request) -> CorrectionReport:
    return _rockets(request).correction


@app.get("/api/rockets/nextbest", response_model=NextBest)
def next_best(request: Request) -> NextBest:
    return _rockets(request).nextbest


@app.get("/api/rockets/fingerprint", response_model=FleetFingerprint)
def fleet_fingerprint(request: Request) -> FleetFingerprint:
    """Exploratory: burn and coast accelerometer readings, real ÷ ghost, per flight."""
    return _rockets(request).fingerprint


@app.get("/api/rockets/manifest")
def manifest(request: Request) -> dict[str, object]:
    return _rockets(request).manifest


def _orbits(request: Request) -> OrbitStore:
    store: OrbitStore | None = request.app.state.orbits
    if store is None:
        raise HTTPException(status_code=503, detail=request.app.state.orbits_error or ORBITS_GATED)
    return store


@app.get("/api/orbits/status", response_model=OrbitsStatus)
def orbits_status(request: Request) -> OrbitsStatus:
    if request.app.state.orbits is not None:
        return OrbitsStatus(available=True, reason="Built from Space-Track history and NASA OMNI.")
    if request.app.state.orbits_error:
        return OrbitsStatus(
            available=False,
            reason=f"Orbit artifacts failed verification: {request.app.state.orbits_error}",
        )
    return OrbitsStatus(available=False, reason=ORBITS_GATED)


@app.get("/api/orbits/fleet", response_model=OrbitFleet)
def orbits_fleet(request: Request) -> OrbitFleet:
    return _orbits(request).fleet


@app.get("/api/orbits/spaceweather", response_model=SpaceWeatherSeries)
def orbits_spaceweather(request: Request) -> SpaceWeatherSeries:
    return _orbits(request).spaceweather


@app.get("/api/orbits/gapmap", response_model=GapMap)
def orbits_gapmap(request: Request) -> GapMap:
    return _orbits(request).gapmap
