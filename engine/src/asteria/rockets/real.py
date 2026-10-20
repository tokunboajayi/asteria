"""The real flight: channels, liftoff alignment, and Δ against the ghost."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import savgol_filter

from asteria.models import DeltaSeries, GnssTrack, RawSource, RealChannel, RealSeries
from asteria.rockets.ghost import LIFTOFF_ALTITUDE_M, GhostArrays, first_crossing
from asteria.rockets.telemetry import CleanLog, Gnss, LogSpec, si_unit

FloatArray = NDArray[np.float64]

COARSE_INTERVAL_S = 0.2
DERIVATIVE_GRID_S = 0.05
SAVGOL_WINDOW = 21  # samples on the 0.05 s grid = 1.0 s
SAVGOL_ORDER = 2
MAX_UI_POINTS = 2500
LIFTOFF_CONFIRM_ALTITUDE_M = 50.0
LIFTOFF_CONFIRM_WITHIN_S = 3.0


@dataclass(frozen=True)
class RealArrays:
    """The real flight on its clean time base.

    `vz` is always derived from the logged altitude with one fixed filter, so
    the velocity gap means the same thing for every flight in the fleet. Any
    velocity the logger reported itself is kept separately in `extra`.
    """

    t: FloatArray
    altitude: FloatArray
    vz: FloatArray
    extra: dict[str, FloatArray]


def derive_vz(t: FloatArray, altitude: FloatArray) -> FloatArray:
    """Savitzky–Golay derivative of altitude on a uniform grid, mapped back to `t`."""
    grid = np.arange(t[0], t[-1], DERIVATIVE_GRID_S)
    if grid.size < SAVGOL_WINDOW:
        return np.asarray(np.gradient(altitude, t), dtype=np.float64)
    resampled = np.interp(grid, t, altitude)
    slope = savgol_filter(resampled, SAVGOL_WINDOW, SAVGOL_ORDER, deriv=1, delta=DERIVATIVE_GRID_S)
    return np.asarray(np.interp(t, grid, slope), dtype=np.float64)


def real_arrays(log: CleanLog) -> RealArrays:
    return RealArrays(log.t, log.altitude_m, derive_vz(log.t, log.altitude_m), dict(log.extra))


def real_liftoff(t: FloatArray, altitude: FloatArray) -> float | None:
    """First 10 m crossing that is followed by 50 m within 3 s (rejects pad noise)."""
    candidates = np.nonzero(
        (altitude[1:] >= LIFTOFF_ALTITUDE_M) & (altitude[:-1] < LIFTOFF_ALTITUDE_M)
    )[0]
    for i in candidates:
        crossing = first_crossing(t[i : i + 2], altitude[i : i + 2], LIFTOFF_ALTITUDE_M)
        if crossing is None:
            continue
        window = (t >= crossing) & (t <= crossing + LIFTOFF_CONFIRM_WITHIN_S)
        if np.any(altitude[window] >= LIFTOFF_CONFIRM_ALTITUDE_M):
            return crossing
    return None


def _r(value: float, digits: int) -> float:
    return float(round(value, digits))


def delta(ghost: GhostArrays, real: RealArrays, shift: float, aligned: bool) -> DeltaSeries:
    """real − ghost on the ghost grid. Real time on the ghost clock = t_real + shift.

    The overlap test uses exactly the rounded numbers that are published (ghost
    t to 3 dp, real t to 4 dp, shift to 4 dp), so anyone can re-check from the
    JSON which samples are inside the real log's span.
    """
    shift_r = _r(shift, 4)
    t_out = [_r(v, 3) for v in ghost.t]
    lo = _r(real.t[0], 4) + shift_r
    hi = _r(real.t[-1], 4) + shift_r
    inside = [lo <= tv <= hi for tv in t_out]
    t_real_on_ghost = real.t + shift_r
    alt_i = np.interp(ghost.t, t_real_on_ghost, real.altitude)
    vz_i = np.interp(ghost.t, t_real_on_ghost, real.vz)
    ghost_alt = [_r(v, 3) for v in ghost.altitude]
    real_alt: list[float | None] = []
    d_alt: list[float | None] = []
    d_vz: list[float | None] = []
    for k, ok in enumerate(inside):
        if not ok:
            real_alt.append(None)
            d_alt.append(None)
            d_vz.append(None)
            continue
        ra = _r(alt_i[k], 3)
        real_alt.append(ra)
        d_alt.append(_r(ra - ghost_alt[k], 3))
        d_vz.append(_r(vz_i[k] - ghost.vz[k], 3))
    return DeltaSeries(
        real_time_shift_s=shift_r,
        alignment="liftoff-10m" if aligned else "none",
        t=t_out,
        ghost_altitude=ghost_alt,
        real_altitude=real_alt,
        altitude=d_alt,
        vz=d_vz,
    )


def _decimation_index(n: int, keep: int) -> NDArray[np.int64]:
    if n <= MAX_UI_POINTS:
        return np.arange(n, dtype=np.int64)
    idx = np.linspace(0, n - 1, MAX_UI_POINTS).round().astype(np.int64)
    return np.unique(np.concatenate((idx, [0, n - 1, keep])))


def _values(a: FloatArray) -> list[float | None]:
    return [None if not np.isfinite(v) else float(round(v, 3)) for v in a]


def real_series(
    real: RealArrays, spec: LogSpec, n_raw: int, gnss: Gnss | None, gnss_source: str | None
) -> RealSeries:
    """Published samples for display (decimated, never averaged; apogee sample kept)."""
    idx = _decimation_index(real.t.size, int(np.argmax(real.altitude)))
    channels = {
        "altitude": RealChannel(
            name="Altitude AGL",
            unit="m",
            kind="measured",
            source_column=spec.altitude_column,
            values=_values(real.altitude[idx]),
        ),
        "vz": RealChannel(
            name="Vertical velocity (derived from altitude)",
            unit="m/s",
            kind="derived",
            source_column=None,
            values=_values(real.vz[idx]),
        ),
    }
    for ch in spec.extra:
        channels[ch.key] = RealChannel(
            name=ch.label,
            unit=si_unit(ch.unit),
            kind="measured",
            source_column=ch.column,
            values=_values(real.extra[ch.key][idx]),
        )
    track = None
    if gnss is not None and gnss_source is not None:
        track = GnssTrack(
            t=[float(round(v, 3)) for v in gnss.t],
            latitude=[float(round(v, 7)) for v in gnss.latitude],
            longitude=[float(round(v, 7)) for v in gnss.longitude],
            source=gnss_source,
        )
    return RealSeries(
        t=[float(round(v, 4)) for v in real.t[idx]],
        channels=channels,
        gnss=track,
        raw_source=RawSource(
            path=spec.path,
            time_column=spec.time_column,
            altitude_column=spec.altitude_column,
            altitude_unit=spec.altitude_unit,
            delimiter=spec.delimiter,
            keep_until_s=spec.keep_until_s,
            keep_until_reason=spec.keep_until_reason,
        ),
        n_raw_samples=n_raw,
        decimated=bool(idx.size < real.t.size),
    )


@dataclass(frozen=True)
class GapSamples:
    """Ascent samples for the fleet gap map: ghost Mach, ghost altitude, Δvz."""

    mach: FloatArray
    altitude: FloatArray
    dvz: FloatArray


def gap_samples(
    ghost: GhostArrays, d: DeltaSeries, rail_exit_s: float, apogee_s: float
) -> GapSamples:
    t = ghost.t
    dvz = np.array([np.nan if v is None else v for v in d.vz], dtype=np.float64)
    use = (t >= rail_exit_s) & (t <= apogee_s) & np.isfinite(dvz)
    return GapSamples(mach=ghost.mach[use], altitude=ghost.altitude[use], dvz=dvz[use])
