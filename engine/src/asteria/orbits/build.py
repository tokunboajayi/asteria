"""Build the Orbits (Storm Ghost) artifacts from Space-Track history and NASA OMNI.

Integrity gates that stop the build:
* an object in the catalog returns no element sets at all;
* an element set's NORAD id is not one that was asked for;
* SGP4 reports an error for any state used.
An object with no element set before the storm is kept, with a written
reason, and draws nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np

from asteria import __version__
from asteria.artifacts import IntegrityError, publish
from asteria.config import Paths
from asteria.core import gapmap
from asteria.models import (
    DensityReport,
    Ephemerides,
    GapSeries,
    Model,
    OmniSource,
    OrbitFleet,
    OrbitObjectSummary,
    OrbitProvenance,
    SpaceWeatherSeries,
    StormInfo,
)
from asteria.orbits import (
    catalog,
    decay,
    density,
    ephemeris,
    ghost,
    spacetrack,
    spaceweather,
)

OMNI_SOURCE = "NASA GSFC SPDF OMNI2 hourly (omni2_YYYY.dat)"


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _series(
    sets: Sequence[ghost.ElementSet],
    start: datetime,
    hours: Sequence[spaceweather.Hour],
) -> GapSeries | None:
    base = ghost.base_set(sets, start)
    if base is None:
        return None
    points, stop = ghost.gaps(
        sets, base, timedelta(days=catalog.FOLLOW_DAYS), catalog.MANEUVER_RISE_M
    )
    return GapSeries(
        base_epoch=_iso(base.epoch),
        base_mean_altitude_km=round(base.mean_altitude_km, 3),
        epochs=[_iso(p.epoch) for p in points],
        days=[round(p.days, 5) for p in points],
        radial_km=[round(p.radial_km, 4) for p in points],
        in_track_km=[round(p.in_track_km, 4) for p in points],
        cross_track_km=[round(p.cross_track_km, 4) for p in points],
        max_kp=[spaceweather.max_kp(hours, base.epoch, p.epoch) for p in points],
        ghost_lat=[round(p.ghost_lat, 5) for p in points],
        ghost_lon=[round(p.ghost_lon, 5) for p in points],
        ghost_alt_km=[round(p.ghost_alt_km, 3) for p in points],
        tracked_lat=[round(p.tracked_lat, 5) for p in points],
        tracked_lon=[round(p.tracked_lon, 5) for p in points],
        tracked_alt_km=[round(p.tracked_alt_km, 3) for p in points],
        stopped_by_maneuver_at=_iso(stop) if stop else None,
    )


def _gap_samples(objects: Sequence[OrbitObjectSummary]) -> list[gapmap.FlightSamples]:
    """One sample per tracked epoch, storm and quiet alike: (max Kp, base altitude, km/day)."""
    out = []
    for o in objects:
        xs: list[float] = []
        ys: list[float] = []
        vs: list[float] = []
        for s in (o.storm, o.quiet):
            if s is None:
                continue
            for days, it, kp in zip(s.days, s.in_track_km, s.max_kp, strict=True):
                if kp is None or days <= 0:
                    continue
                xs.append(kp)
                ys.append(s.base_mean_altitude_km)
                vs.append(it / days)
        if xs:
            out.append(
                gapmap.FlightSamples(str(o.norad_id), np.array(xs), np.array(ys), np.array(vs))
            )
    return out


def build(paths: Paths, env_files: Sequence[Path]) -> Path:
    onset = catalog.STORM_ONSET
    follow = timedelta(days=catalog.FOLLOW_DAYS)
    start = onset - timedelta(days=catalog.HISTORY_LOOKBACK_DAYS)
    end = onset + follow + timedelta(days=1)

    # F10.7's 81-day centred mean reaches 40 days beyond the window on either side.
    f107a_reach = timedelta(days=density.F107A_DAYS // 2 + 1)
    years = list(range((start - f107a_reach).year, (end + f107a_reach).year + 1))
    omni_files = [spaceweather.fetch_year(paths.omni_cache, y) for y in years]
    hours = spaceweather.load(omni_files)
    quiet = spaceweather.quiet_window(hours, onset, catalog.FOLLOW_DAYS, catalog.QUIET_MAX_KP)

    ids = [o.norad_id for o in catalog.OBJECTS]
    history = spacetrack.fetch_history(paths.spacetrack_cache, ids, start, end, env_files)
    by_id: dict[int, list[ghost.ElementSet]] = {i: [] for i in ids}
    for record in ghost.latest_issue_per_epoch(history.records):
        es = ghost.from_record(record)
        if es.norad_id not in by_id:
            raise IntegrityError(
                f"Space-Track returned NORAD {es.norad_id}, which was not requested"
            )
        by_id[es.norad_id].append(es)

    summaries = []
    ephemerides = []
    densities = []
    decays = []
    indices = density.Indices(hours)
    quiet_ap = indices.quiet_ap(*quiet) if quiet else None
    for obj in catalog.OBJECTS:
        sets = sorted(by_id[obj.norad_id], key=lambda s: s.epoch)
        if not sets:
            raise IntegrityError(f"no element sets for {obj.norad_id} ({obj.name}) in the window")
        storm = _series(sets, onset, hours)
        quiet_series = _series(sets, quiet[0], hours) if quiet else None
        reason = (
            None if storm else "No element set before the storm onset in the downloaded window."
        )
        if storm is not None:
            base = ghost.base_set(sets, onset)
            assert base is not None  # storm exists only when a base set does
            arc_start = _parse(storm.epochs[-1]) if storm.epochs else onset
            ephemerides.append(
                ephemeris.build_object(
                    obj.norad_id, obj.name, sets, base, onset, onset + follow, arc_start, _iso
                )
            )
            if quiet is not None and quiet_ap is not None:
                densities.append(
                    density.object_density(
                        obj.norad_id,
                        obj.name,
                        sets,
                        indices,
                        quiet_ap,
                        max(onset - timedelta(days=1), base.epoch),
                        onset + follow,
                        _iso,
                    )
                )
                decays.append(
                    decay.object_decay(
                        obj.norad_id,
                        obj.name,
                        sets,
                        catalog.MANEUVER_RISE_M,
                        quiet,
                        (onset, onset + follow),
                        indices,
                        _iso,
                    )
                )
        summaries.append(
            OrbitObjectSummary(
                norad_id=obj.norad_id,
                name=obj.name,
                note=obj.note,
                element_sets=len(sets),
                storm=storm,
                quiet=quiet_series,
                excluded_reason=reason,
            )
        )

    window_hours = spaceweather.window(
        hours,
        (quiet[0] if quiet else onset) - timedelta(days=1),
        onset + follow + timedelta(days=1),
    )
    storm_hours = spaceweather.window(hours, onset, onset + follow)
    kps = [h.kp for h in storm_hours if h.kp is not None]
    dsts = [h.dst_nt for h in storm_hours if h.dst_nt is not None]
    generated = _iso(datetime.now(UTC))
    provenance = OrbitProvenance(
        spacetrack_query=history.query_url,
        spacetrack_sha256=history.sha256,
        spacetrack_downloaded_at=history.downloaded_at,
        omni=[
            OmniSource(url=f.url, sha256=f.sha256, downloaded_at=f.downloaded_at)
            for f in omni_files
        ],
        sgp4_version=version("sgp4"),
        engine_version=__version__,
        generated_at=generated,
    )
    fleet = OrbitFleet(
        storm=StormInfo(
            name=catalog.STORM_NAME,
            onset=_iso(onset),
            follow_days=catalog.FOLLOW_DAYS,
            quiet_start=_iso(quiet[0]) if quiet else None,
            quiet_end=_iso(quiet[1]) if quiet else None,
            quiet_max_kp=catalog.QUIET_MAX_KP,
            maneuver_rise_m=catalog.MANEUVER_RISE_M,
            peak_kp=max(kps) if kps else None,
            min_dst_nt=min(dsts) if dsts else None,
        ),
        objects=summaries,
        provenance=provenance,
    )
    weather = SpaceWeatherSeries(
        source=OMNI_SOURCE,
        times=[_iso(h.time) for h in window_hours],
        kp=[h.kp for h in window_hours],
        dst_nt=[h.dst_nt for h in window_hours],
        ap_nt=[h.ap_nt for h in window_hours],
        f107_sfu=[h.f107_sfu for h in window_hours],
    )
    gap = gapmap.build(
        _gap_samples(summaries),
        catalog.KP_EDGES,
        catalog.ALT_EDGES,
        quantity="In-track gap rate (tracked − ghost) per day",
        unit="km/day",
        coordinates="Highest hourly Kp since the ghost's epoch, and the object's mean altitude",
        x_label="Max Kp since ghost epoch",
        y_label="Mean altitude, km",
        caveats=[
            "Tracked positions are orbit fits to tracking data (Space-Track element sets), "
            "not direct measurements.",
            f"Ghosts stop at the first maneuver (mean semi-major axis rising more than "
            f"{catalog.MANEUVER_RISE_M:g} m between element sets).",
        ],
        min_flights=catalog.MIN_OBJECTS_PER_CELL,
    )

    manifest = {"generated_at": generated, "engine_version": __version__}
    models: dict[str, Model] = {
        "fleet.json": fleet,
        "spaceweather.json": weather,
        "gapmap.json": gap,
        "ephemeris.json": Ephemerides(frame="TEME", objects=ephemerides),
    }
    if quiet_ap is not None:
        models["density.json"] = DensityReport(
            model=density.MODEL,
            method=density.METHOD,
            quiet_ap=round(quiet_ap, 2),
            sample_step_s=density.SAMPLE_STEP_S,
            objects=densities,
            caveats=density.CAVEATS,
            decay_method=decay.METHOD,
            decay_caveats=decay.CAVEATS,
            decay=decays,
        )
    return publish(paths.orbits_artifacts, models, manifest)
