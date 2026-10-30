"""Build the Rockets artifacts: one JSON per flight plus fleet-level analyses.

Pass 1 (one process per flight): run the notebook, sample the ghost, load
the real log, cross-check it, align, compute Δ, calibrate k_own.
Pass 2 (in this process): held-out k̂ for every flight.
Pass 3 (one process per flight): full re-simulation at k̂ = corrected ghost.
Then the gap map, Next Best Flight, debriefs and the manifest.

Integrity gates that stop the build (they never downgrade to a warning):
* the source checkout is not the pinned commit;
* re-simulating at k = 1 does not reproduce the notebook's apogee;
* Asteria's loader disagrees with the notebook's own importer;
* a log's peak differs from the official apogee by more than 10 %;
* a quote is not found verbatim in the notebook.
"""

from __future__ import annotations

import multiprocessing as mp
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from asteria import __version__
from asteria.artifacts import IntegrityError, publish
from asteria.config import ROCKETPY_COMMIT, ROCKETPY_REPO_URL, ROCKETPY_TAG
from asteria.core import gapmap, nextbest
from asteria.models import (
    ApogeeSummary,
    BandCoverage,
    CorrectionRow,
    CorrectionSummary,
    Debrief,
    DeltaSeries,
    Diagnostics,
    Event,
    EventTiming,
    Excluded,
    Fingerprint,
    FingerprintRow,
    Fleet,
    FleetBand,
    FleetFingerprint,
    FleetProvenance,
    FlightDetail,
    FlightSummary,
    GhostSeries,
    LaunchSite,
    LaunchTime,
    Model,
    Provenance,
    Quote,
    RealSeries,
    SourceFile,
)
from asteria.provenance import source_file
from asteria.rockets import (
    band,
    catalog,
    correction,
    debrief,
    events,
    fingerprint,
    ghost,
    notebook,
    real,
    telemetry,
)

OFFICIAL_TOLERANCE = 0.10
TRANSONIC_CAVEAT = (
    "Barometric altimeters can misread near the speed of sound, so gaps in transonic cells "
    "may include sensor error as well as physics error."
)
DERIVED_VZ_NOTE = (
    "Real vertical velocity is derived from each log's altitude with the same fixed filter "
    "(Savitzky–Golay, 1.0 s window, 2nd order), so every flight is measured the same way."
)
MACH_EDGES = gapmap.edges(0.0, 1.6, 0.1)
ALT_EDGES = gapmap.edges(0.0, 4000.0, 250.0)
_DATA_REF = re.compile(r"""["'](\.\./\.\./data/[^"']+)["']""")


# ---------------------------------------------------------------------------
# Pass 1
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pass1:
    spec_id: str
    ghost: GhostSeries
    ghost_apogee_m: float
    ghost_apogee_time_s: float
    max_mach: float
    events: list[Event]
    timing: EventTiming
    fingerprint: Fingerprint
    real: RealSeries
    real_apogee_m: float
    real_apogee_time_s: float
    delta: DeltaSeries
    diagnostics: Diagnostics
    gap: gapmap.FlightSamples | None
    reach: gapmap.FlightSamples
    peak_dvz: tuple[float, float, float] | None  # (Δvz, ghost Mach, ghost altitude)
    k_own: float
    k_bracketed: bool
    launch_site: LaunchSite
    weather_time_utc: str | None
    launch: LaunchTime | None
    files: list[SourceFile]
    team_prediction: Quote | None
    official: Quote | None
    rocketpy_version: str
    cell_seconds: float


def _quote(markdown: str, text: str | None, flight_id: str) -> Quote | None:
    if text is None:
        return None
    if text not in markdown:
        raise IntegrityError(f"{flight_id}: quote not found verbatim in notebook: {text!r}")
    return Quote(value_m=catalog.metres_in_quote(text), quote=text)


def _cross_check(checkout: Path, spec: catalog.FlightSpec, run: notebook.NotebookRun) -> str:
    """Asteria's raw parse (no cutoff, no unit change) must equal the importer's arrays."""
    if spec.importer_var is None:
        return "no-importer"
    importer = run.get(spec.importer_var)
    source = np.asarray(importer.altitude.source, dtype=np.float64)
    raw = telemetry.load_log(
        checkout,
        telemetry.LogSpec(
            path=spec.log.path,
            time_column=spec.log.time_column,
            altitude_column=spec.log.altitude_column,
            altitude_unit="m",
            delimiter=spec.log.delimiter,
        ),
    )
    ours = np.column_stack((raw.t, raw.altitude_m))
    ours = ours[np.argsort(ours[:, 0], kind="stable")]
    theirs = source[np.argsort(source[:, 0], kind="stable")]
    if ours.shape != theirs.shape or not np.array_equal(ours, theirs):
        raise IntegrityError(
            f"{spec.id}: Asteria's loader disagrees with the notebook importer "
            f"({ours.shape} vs {theirs.shape})"
        )
    return "identical"


def _source_files(checkout: Path, spec: catalog.FlightSpec) -> list[SourceFile]:
    nb_dir = (checkout / spec.notebook).parent
    referenced = set()
    for _, src in notebook.code_cells(checkout / spec.notebook):
        for ref in _DATA_REF.findall(src):
            path = (nb_dir / ref).resolve()
            if path.is_file():
                referenced.add(path.relative_to(checkout.resolve()).as_posix())
    paths = {spec.notebook, spec.log.path, *referenced}
    if spec.gnss is not None:
        paths.add(spec.gnss.path)
    return [source_file(checkout, p) for p in sorted(paths)]


def run_pass1(checkout_str: str, spec_id: str) -> Pass1:
    checkout = Path(checkout_str)
    spec = catalog.by_id(spec_id)
    run = notebook.run_notebook(checkout, spec.notebook, spec.skip_cells)
    flight = run.get(spec.flight_var)
    kwargs = notebook.flight_init_kwargs(flight)
    ghost_apogee = ghost.apogee_agl(flight)
    correction.check_reproduction(kwargs, ghost_apogee)

    g = ghost.sample(flight)
    flight_events = ghost.events(flight, g)
    markdown = notebook.markdown_text(checkout / spec.notebook)
    if spec.title_quote not in markdown:
        raise IntegrityError(f"{spec.id}: title not found in notebook")
    team = _quote(markdown, spec.team_prediction_quote, spec.id)
    official = _quote(markdown, spec.official_apogee_quote, spec.id)

    cross = _cross_check(checkout, spec, run)
    raw = telemetry.load_log(checkout, spec.log)
    real_peak = float(np.max(raw.altitude_m))
    real_peak_t = float(raw.t[int(np.argmax(raw.altitude_m))])
    if (
        official is not None
        and abs(real_peak - official.value_m) > OFFICIAL_TOLERANCE * official.value_m
    ):
        raise IntegrityError(
            f"{spec.id}: log peak {real_peak:.1f} m vs official {official.value_m:.1f} m "
            f"differ by more than {OFFICIAL_TOLERANCE:.0%}: check units and cutoffs"
        )
    clean = telemetry.clean(raw)
    arrays = real.real_arrays(clean)
    gnss = telemetry.load_gnss(checkout, spec.gnss) if spec.gnss else None
    clock = telemetry.load_utc_clock(checkout, spec.utc_clock) if spec.utc_clock else None

    ghost_lift = ghost.first_crossing(g.t, g.altitude, ghost.LIFTOFF_ALTITUDE_M)
    if ghost_lift is None:
        raise IntegrityError(f"{spec.id}: ghost never reaches liftoff altitude")
    real_lift = real.real_liftoff(arrays.t, arrays.altitude)
    shift = ghost_lift - real_lift if real_lift is not None else 0.0
    d = real.delta(g, arrays, shift, aligned=real_lift is not None)
    coarse = clean.median_interval_s > real.COARSE_INTERVAL_S

    ghost_force = ghost.axial_specific_force(flight, g.t)
    logged_accel = arrays.extra.get("accel_logged")
    accel: events.Accelerometer | None = None
    accel_note: str | None = None
    if logged_accel is not None:
        accel, why = events.read_accelerometer(
            arrays.t + shift, logged_accel, ghost_lift, g.t, ghost_force
        )
        accel_note = accel.evidence if accel is not None else why
    ghost_track = events.Track(g.t, g.altitude, g.vz, ghost_force)
    real_track = events.Track(
        arrays.t + shift,
        arrays.altitude,
        arrays.vz,
        None if accel is None else accel.specific_force,
    )
    timing = events.compare(
        ghost_track,
        events.GhostContext(
            liftoff_s=ghost_lift,
            mach=g.mach,
            deploys=sorted(
                ((str(p.name), float(t)) for t, p in flight.parachute_events), key=lambda d: d[1]
            ),
        ),
        real_track,
        coarse=clean.median_interval_s > real.COARSE_INTERVAL_S,
        accelerometer_note=accel_note,
    )
    motor_drag = fingerprint.measure(ghost_track, real_track, ghost_lift, accel_note)

    rail_exit = float(flight.out_of_rail_time)
    samples = real.gap_samples(g, d, rail_exit, float(flight.apogee_time))
    climbing = (g.t >= rail_exit) & (g.t <= float(flight.apogee_time))
    reach = gapmap.FlightSamples(
        spec.id, g.mach[climbing], g.altitude[climbing], np.zeros(int(climbing.sum()))
    )
    gap = None
    peak = None
    if not coarse and samples.dvz.size:
        gap = gapmap.FlightSamples(spec.id, samples.mach, samples.altitude, samples.dvz)
        k = int(np.argmax(np.abs(samples.dvz)))
        peak = (float(samples.dvz[k]), float(samples.mach[k]), float(samples.altitude[k]))

    cal = correction.calibrate(kwargs, real_peak)
    diagnostics = Diagnostics(
        real_t_start_s=float(clean.t[0]),
        real_t_end_s=float(clean.t[-1]),
        real_liftoff_s=None if real_lift is None else round(real_lift, 4),
        ghost_liftoff_s=round(ghost_lift, 4),
        liftoff_offset_s=None if real_lift is None else round(real_lift - ghost_lift, 4),
        median_sample_interval_s=round(clean.median_interval_s, 4),
        coarse_log=coarse,
        duplicate_timestamps=clean.duplicate_timestamps,
        rows_after_cutoff=raw.rows_after_cutoff,
        importer_cross_check=cross,  # type: ignore[arg-type]
    )
    gnss_source = spec.gnss.path if spec.gnss else None
    return Pass1(
        spec_id=spec.id,
        ghost=g.to_model(),
        ghost_apogee_m=round(ghost_apogee, 3),
        ghost_apogee_time_s=round(float(flight.apogee_time), 3),
        max_mach=round(float(np.max(g.mach)), 4),
        events=flight_events,
        timing=timing,
        fingerprint=motor_drag,
        real=real.real_series(arrays, spec.log, int(raw.t.size), gnss, gnss_source),
        real_apogee_m=round(real_peak, 3),
        real_apogee_time_s=round(real_peak_t, 3),
        delta=d,
        diagnostics=diagnostics,
        gap=gap,
        reach=reach,
        peak_dvz=peak,
        k_own=cal.k_own,
        k_bracketed=cal.bracketed,
        launch_site=LaunchSite(
            latitude_deg=float(flight.env.latitude),
            longitude_deg=float(flight.env.longitude),
            elevation_m=float(flight.env.elevation),
        ),
        weather_time_utc=_weather_time(flight),
        launch=_launch(clock, real_lift, _weather_time(flight)),
        files=_source_files(checkout, spec),
        team_prediction=team,
        official=official,
        rocketpy_version=version("rocketpy"),
        cell_seconds=round(sum(c.seconds for c in run.cells), 2),
    )


# ---------------------------------------------------------------------------
# Pass 3
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BandRun:
    altitude: list[float | None]
    apogee_m: float


@dataclass(frozen=True)
class Pass3:
    spec_id: str
    corrected: GhostSeries
    corrected_apogee_m: float
    band_runs: tuple[BandRun, BandRun] | None


def _band_run(kwargs: dict[str, Any], k: float, t_grid: list[float]) -> BandRun:
    flight = correction.resimulate(kwargs, k, to_apogee=False)
    t_end = float(flight.t_final)
    t = np.asarray([x for x in t_grid if x <= t_end], dtype=np.float64)
    alt = np.asarray(flight.altitude.get_value(t), dtype=np.float64) if t.size else np.array([])
    values: list[float | None] = [round(float(v), 2) for v in alt]
    values += [None] * (len(t_grid) - len(values))
    return BandRun(altitude=values, apogee_m=round(ghost.apogee_agl(flight), 3))


def run_pass3(
    checkout_str: str,
    spec_id: str,
    k_hat: float,
    k_range: tuple[float, float] | None,
    t_grid: list[float],
) -> Pass3:
    checkout = Path(checkout_str)
    spec = catalog.by_id(spec_id)
    run = notebook.run_notebook(checkout, spec.notebook, spec.skip_cells)
    kwargs = notebook.flight_init_kwargs(run.get(spec.flight_var))
    flight = correction.resimulate(kwargs, k_hat, to_apogee=False)
    runs = (
        None
        if k_range is None
        else (_band_run(kwargs, k_range[0], t_grid), _band_run(kwargs, k_range[1], t_grid))
    )
    return Pass3(
        spec_id=spec_id,
        corrected=ghost.sample(flight).to_model(),
        corrected_apogee_m=round(ghost.apogee_agl(flight), 3),
        band_runs=runs,
    )


def _coast(g: GhostSeries, apogee_time_s: float) -> tuple[float, float]:
    """Ghost peak vertical speed (end of powered climb) to ghost apogee."""
    k = int(np.argmax(g.vz))
    return (g.t[k], apogee_time_s)


def _launch(
    clock: telemetry.UtcClock | None, real_lift_s: float | None, weather: str | None
) -> LaunchTime | None:
    """Real liftoff from the log's own UTC clock; None without a clock or a found liftoff."""
    if clock is None or real_lift_s is None:
        return None
    when = clock.at(real_lift_s)
    offset = None
    if weather is not None:
        w = datetime.fromisoformat(weather.replace("Z", "+00:00"))
        offset = round((w - when).total_seconds() / 86400.0, 4)
    return LaunchTime(
        utc=when.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        uncertainty_s=round(clock.half_width_s, 3),
        source=f"{clock.source}; {clock.rows} rows",
        weather_offset_days=offset,
    )


def _pair(k: band.KRange | None) -> tuple[float, float] | None:
    return None if k is None else (k.k_low, k.k_high)


def _weather_time(flight: Any) -> str | None:
    when = getattr(flight.env, "datetime_date", None)
    if when is None:
        return None
    text: str = when.astimezone(UTC).replace(microsecond=0).isoformat()
    return text.replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _flight_artifacts(
    spec: catalog.FlightSpec,
    a: Pass1,
    c: Pass3,
    k_hat: float,
    k_range: band.KRange | None,
    generated_at: str,
) -> tuple[CorrectionRow, FlightSummary, FlightDetail, Debrief]:
    """Everything one flight contributes: its correction row, summary, detail and debrief."""
    err_before = correction.error_pct(a.ghost_apogee_m, a.real_apogee_m)
    err_after = correction.error_pct(c.corrected_apogee_m, a.real_apogee_m)
    corr = CorrectionSummary(
        k_own=a.k_own,
        k_hat=k_hat,
        corrected_apogee_m=c.corrected_apogee_m,
        err_before_pct=err_before,
        err_after_pct=err_after,
    )
    row = CorrectionRow(
        id=spec.id,
        real_apogee_m=a.real_apogee_m,
        ghost_apogee_m=a.ghost_apogee_m,
        **corr.model_dump(),
    )
    summary = FlightSummary(
        id=spec.id,
        name=spec.name,
        team=spec.team,
        event=spec.event,
        year=spec.year,
        launch_site=a.launch_site,
        has_position=a.real.gnss is not None,
        real_channels=sorted(a.real.channels),
        apogee=ApogeeSummary(
            real_m=a.real_apogee_m,
            real_time_s=a.real_apogee_time_s,
            ghost_m=a.ghost_apogee_m,
            ghost_time_s=a.ghost_apogee_time_s,
            delta_m=round(a.real_apogee_m - a.ghost_apogee_m, 3),
            ghost_error_pct=err_before,
        ),
        team_prediction=a.team_prediction,
        official_apogee=a.official,
        max_mach_ghost=a.max_mach,
        correction=corr,
    )
    detail = FlightDetail(
        summary=summary,
        provenance=Provenance(
            repo=ROCKETPY_REPO_URL,
            tag=ROCKETPY_TAG,
            commit=ROCKETPY_COMMIT,
            notebook=spec.notebook,
            files=a.files,
            rocketpy_version=a.rocketpy_version,
            engine_version=__version__,
            generated_at=generated_at,
        ),
        ghost=a.ghost,
        corrected=c.corrected,
        real=a.real,
        delta=a.delta,
        events=a.events,
        timing=a.timing,
        fingerprint=a.fingerprint,
        diagnostics=a.diagnostics,
        band=(
            None
            if k_range is None or c.band_runs is None
            else band.make(
                k_range,
                a.ghost.t,
                c.band_runs[0].altitude,
                c.band_runs[1].altitude,
                c.band_runs[0].apogee_m,
                c.band_runs[1].apogee_m,
                a.delta.real_altitude,
                a.real_apogee_m,
                _coast(a.ghost, a.ghost_apogee_time_s),
            )
        ),
        weather_time_utc=a.weather_time_utc,
        launch=a.launch,
    )
    return row, summary, detail, debrief.build(spec, summary, a.diagnostics, a.peak_dvz)


def _run_passes(
    checkout: Path, specs: list[catalog.FlightSpec], jobs: int
) -> tuple[dict[str, Pass1], dict[str, float], dict[str, band.KRange | None], dict[str, Pass3]]:
    ctx = mp.get_context("spawn")
    pool = ProcessPoolExecutor(max_workers=jobs, mp_context=ctx)
    try:
        futures = {s.id: pool.submit(run_pass1, str(checkout), s.id) for s in specs}
        p1: dict[str, Pass1] = {}
        for fid, fut in futures.items():
            p1[fid] = fut.result()
            r = p1[fid]
            _log(
                f"[pass1] {fid}: ghost {r.ghost_apogee_m:.1f} m, real {r.real_apogee_m:.1f} m, "
                f"k_own {r.k_own:.4f}{'' if r.k_bracketed else ' (UNBRACKETED)'}, "
                f"notebook {r.cell_seconds:.1f}s, cross-check {r.diagnostics.importer_cross_check}"
            )

        k_own = {fid: r.k_own for fid, r in p1.items()}
        bracketed = {fid: r.k_bracketed for fid, r in p1.items()}
        k_hat = {fid: correction.held_out_k(k_own, fid) for fid in p1}
        k_ranges = {fid: band.held_out_range(k_own, bracketed, fid) for fid in p1}
        futures3 = {
            fid: pool.submit(
                run_pass3,
                str(checkout),
                fid,
                k_hat[fid],
                _pair(k_ranges[fid]),
                p1[fid].ghost.t,
            )
            for fid in p1
        }
        p3 = {fid: fut.result() for fid, fut in futures3.items()}
    except BaseException:
        # A failed gate must not wait for the remaining queued notebook runs.
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return p1, k_hat, k_ranges, p3


def build(checkout: Path, out_dir: Path, jobs: int = 2, only: list[str] | None = None) -> Path:
    specs = [s for s in catalog.FLEET if not only or s.id in only]
    if len(specs) < 2:
        raise ValueError("need at least two flights for held-out evaluation")
    p1, k_hat, k_ranges, p3 = _run_passes(checkout, specs, jobs)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    rocketpy_version = next(iter(p1.values())).rocketpy_version
    parts = [
        _flight_artifacts(s, p1[s.id], p3[s.id], k_hat[s.id], k_ranges[s.id], generated_at)
        for s in specs
    ]
    rows = [row for row, _, _, _ in parts]
    summaries = [summary for _, summary, _, _ in parts]

    gap = gapmap.build(
        [a.gap for a in p1.values() if a.gap is not None],
        MACH_EDGES,
        ALT_EDGES,
        quantity="Velocity gap Δvz (real − ghost), ascent",
        unit="m/s",
        coordinates="Ghost Mach and ghost altitude AGL at the same (liftoff-aligned) time",
        x_label="Mach (ghost)",
        y_label="Altitude AGL (ghost), m",
        reach=[a.reach for a in p1.values()],
        caveats=[TRANSONIC_CAVEAT, DERIVED_VZ_NOTE],
    )
    best = nextbest.recommend(
        gap, [nextbest.Candidate(s.id, s.name, s.max_mach_ghost) for s in summaries]
    )
    fleet = Fleet(
        flights=summaries,
        excluded=[Excluded(notebook=e.notebook, reason=e.reason) for e in catalog.EXCLUDED],
        provenance=FleetProvenance(
            repo=ROCKETPY_REPO_URL,
            tag=ROCKETPY_TAG,
            commit=ROCKETPY_COMMIT,
            rocketpy_version=rocketpy_version,
            engine_version=__version__,
            generated_at=generated_at,
        ),
    )
    fleet_fingerprint = FleetFingerprint(
        method=fingerprint.METHOD,
        not_attempted=fingerprint.NOT_ATTEMPTED,
        rows=[
            FingerprintRow(
                id=detail.summary.id,
                name=detail.summary.name,
                ghost_error_pct=detail.summary.apogee.ghost_error_pct,
                fingerprint=detail.fingerprint,
            )
            for _, _, detail, _ in parts
        ],
    )
    models: dict[str, Model] = {
        "fleet.json": fleet,
        "gapmap.json": gap,
        "correction.json": correction.report(
            rows, _coverage([d.band for _, _, d, _ in parts], [s.id for s in specs])
        ),
        "nextbest.json": best,
        "fingerprint.json": fleet_fingerprint,
    }
    for _, summary, detail, db in parts:
        models[f"flights/{summary.id}.json"] = detail
        models[f"debriefs/{db.flight_id}.json"] = db
    manifest = {
        "generated_at": generated_at,
        "engine_version": __version__,
        "source_commit": ROCKETPY_COMMIT,
    }
    return publish(out_dir, models, manifest)


def _coverage(bands: list[FleetBand | None], ids: list[str]) -> BandCoverage | None:
    pairs = [(fid, b) for fid, b in zip(ids, bands, strict=True) if b is not None]
    if not pairs:
        return None
    return BandCoverage(
        flights=len(pairs),
        inside=sum(b.real_apogee_inside for _, b in pairs),
        expected_inside=round(sum(b.expected_coverage for _, b in pairs), 3),
        outside_ids=[fid for fid, b in pairs if not b.real_apogee_inside],
    )
