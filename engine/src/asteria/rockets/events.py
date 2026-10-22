"""Event timing detective: find what really happened, by code, and compare with the ghost.

Every event is defined once and measured the same way on the ghost and on the
real log, so a timing gap means the flight differed, not the method. All times
are on the ghost clock (real log time + the liftoff shift).

A detection that fails its quality gate is reported as not detected, with the
reason. Nothing is ever estimated to fill the gap.

Events
------
* Thrust < drag: the first time, after the boost peak, that axial specific
  force (what an accelerometer reads) turns negative and stays negative. It
  marks the end of useful thrust, slightly before the motor fully burns out.
  Real: only from a logged accelerometer.
* Peak vertical speed: maximum of vertical velocity. Real: derived from logged
  altitude; not reported for coarse logs, flagged when the ghost is transonic
  there (barometric altimeters can misread near Mach 1).
* Apogee: maximum altitude.
* Final parachute: the descent-rate change where the last parachute opens.
  Real: the best two-line fit to descending altitude (changepoint).

Descent rates under each parachute are compared too: they test the parachute
model directly (drag area), independent of the ascent.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asteria.models import DescentRate, EventTiming, TimedEvent

FloatArray = NDArray[np.float64]

# Quality gates. Fixed for every flight; changing one changes the analysis for all.
BOOST_SEARCH_S = 20.0  # look for the thrust/drag crossing only this soon after liftoff
SUSTAIN_S = 0.3  # a crossing must hold this long to count
DESCENT_SETTLE_S = 5.0  # skip the parachute-opening transient after apogee
GROUND_MARGIN_M = 15.0  # ignore samples this close to the ground
MIN_SEGMENT_S = 3.0  # each descent segment must last this long
MIN_RATE_RATIO = 1.5  # the second parachute must slow the descent at least this much
MIN_FIT_GAIN = 4.0  # two lines must explain descent this much better than one
TRANSONIC = (0.8, 1.2)  # ghost Mach band where barometric speed is unreliable
PEAK_AFTER_THRUST_S = 0.5  # speed cannot keep rising this long after thrust < drag

THRUST_METHOD = "First sustained negative axial specific force after the boost peak"
PEAK_VZ_METHOD = "Maximum vertical velocity (real: from logged altitude, fixed filter)"
APOGEE_METHOD = "Maximum altitude"
DEPLOY_METHOD = "Best two-line fit to descending altitude (changepoint)"


@dataclass(frozen=True)
class Track:
    """One flight on the ghost clock: altitude AGL, vertical velocity, optional axial force."""

    t: FloatArray
    altitude: FloatArray
    vz: FloatArray
    axial: FloatArray | None


@dataclass(frozen=True)
class GhostContext:
    liftoff_s: float
    mach: FloatArray  # on Track.t of the ghost
    deploys: list[tuple[str, float]]  # (parachute name, ghost time), in time order


def _interp(t: FloatArray, y: FloatArray, x: float) -> float:
    return float(np.interp(x, t, y))


def thrust_end(track: Track, liftoff_s: float) -> float | None:
    """Time axial specific force turns negative after the boost peak, held SUSTAIN_S."""
    if track.axial is None:
        return None
    window = (track.t >= liftoff_s) & (track.t <= liftoff_s + BOOST_SEARCH_S)
    idx = np.flatnonzero(window & np.isfinite(track.axial))
    if idx.size < 3:
        return None
    peak = idx[int(np.argmax(track.axial[idx]))]
    for i in idx[idx > peak]:
        if track.axial[i] < 0 <= track.axial[i - 1]:
            held = (track.t >= track.t[i]) & (track.t <= track.t[i] + SUSTAIN_S)
            if np.all(track.axial[held] < 0):
                # Linear interpolation of the crossing between the two samples.
                a0, a1 = track.axial[i - 1], track.axial[i]
                return float(track.t[i - 1] + (track.t[i] - track.t[i - 1]) * a0 / (a0 - a1))
    return None


GRAVITY = 9.80665
PAD_TOLERANCE = 1.0  # m/s²: how close a pad reading must be to 0 or to 1 g
PAD_BEFORE_LIFTOFF_S = 1.0  # pad readings end this long before liftoff (motor ignition comes first)
COAST_WINDOW_S = (7.0, 12.0)  # after liftoff: coasting, motor out, rocket near vertical
CONVENTION_MAX_LOG_RATIO = 0.4  # chosen reading within ~±50 % of the ghost's drag
CONVENTION_MIN_MARGIN = 0.405  # and the other reading at least 1.5× further away (ln 1.5)


@dataclass(frozen=True)
class Accelerometer:
    """A logged accelerometer converted to axial specific force, with the evidence why."""

    t: FloatArray
    specific_force: FloatArray
    gravity_removed: bool
    evidence: str


def _mean_in(t: FloatArray, y: FloatArray, lo: float, hi: float) -> float | None:
    sel = (t >= lo) & (t <= hi) & np.isfinite(y)
    return float(np.mean(y[sel])) if int(sel.sum()) >= 3 else None


def read_accelerometer(
    t: FloatArray,
    logged: FloatArray,
    liftoff_s: float,
    ghost_t: FloatArray,
    ghost_force: FloatArray,
) -> tuple[Accelerometer | None, str]:
    """Decide whether the logger removed gravity, from the data itself.

    Loggers differ: some record what the sensor feels (1 g on the pad), some
    subtract gravity (0 on the pad). Two independent tests:
    * pad: readings before liftoff sit near 0 (removed) or near 1 g (raw);
    * physics: in coast the sensor measures drag only, which must be close to
      the ghost's drag; one convention lands near it, the other ~1 g away.
    Both must agree when both are available; otherwise the accelerometer is not used.
    """
    pad = _mean_in(t, logged, -np.inf, liftoff_s - PAD_BEFORE_LIFTOFF_S)
    pad_says: bool | None = None
    if pad is not None:
        if abs(pad) <= PAD_TOLERANCE:
            pad_says = True
        elif abs(pad - GRAVITY) <= PAD_TOLERANCE:
            pad_says = False

    lo, hi = liftoff_s + COAST_WINDOW_S[0], liftoff_s + COAST_WINDOW_S[1]
    real_coast = _mean_in(t, logged, lo, hi)
    ghost_coast = _mean_in(ghost_t, ghost_force, lo, hi)
    physics_says: bool | None = None
    ratios = ""
    if real_coast is not None and ghost_coast is not None and ghost_coast < 0:
        removed, raw = real_coast + GRAVITY, real_coast
        if removed < 0 and raw < 0:
            d_removed = abs(np.log(removed / ghost_coast))
            d_raw = abs(np.log(raw / ghost_coast))
            ratios = (
                f"coast drag {removed / ghost_coast:.2f}× the ghost's if gravity was removed, "
                f"{raw / ghost_coast:.2f}× if not"
            )
            best, other = min(d_removed, d_raw), max(d_removed, d_raw)
            if best <= CONVENTION_MAX_LOG_RATIO and other - best >= CONVENTION_MIN_MARGIN:
                physics_says = d_removed < d_raw

    verdicts = [v for v in (pad_says, physics_says) if v is not None]
    if not verdicts:
        return None, "The accelerometer's zero could not be verified, so it is not used."
    if len(set(verdicts)) > 1:
        return None, "The pad and coast tests disagree about the accelerometer's zero; not used."
    removed = verdicts[0]
    parts = []
    if pad is not None:
        parts.append(f"reads {pad:.2f} m/s² on the pad")
    if ratios:
        parts.append(ratios)
    evidence = (
        f"Gravity {'removed' if removed else 'included'} by the logger: " + "; ".join(parts) + "."
    )
    force = logged + GRAVITY if removed else logged
    return Accelerometer(t, np.asarray(force, dtype=np.float64), removed, evidence), ""


def _line_sse(t: FloatArray, y: FloatArray) -> tuple[float, float]:
    """(slope, sum of squared residuals) of a least-squares line."""
    slope, intercept = np.polyfit(t, y, 1)
    resid = y - (slope * t + intercept)
    return float(slope), float(resid @ resid)


@dataclass(frozen=True)
class Changepoint:
    t: float
    rate_before: float  # m/s, negative = descending
    rate_after: float
    fit_gain: float


def _descent_window(track: Track, apogee_s: float) -> tuple[FloatArray, FloatArray]:
    w = (
        (track.t >= apogee_s + DESCENT_SETTLE_S)
        & (track.altitude > GROUND_MARGIN_M)
        & np.isfinite(track.altitude)
    )
    return track.t[w], track.altitude[w]


def one_phase_rate(track: Track, apogee_s: float) -> float | None:
    """Slope of one line through the whole recorded descent, m/s (negative = down)."""
    t, y = _descent_window(track, apogee_s)
    if t.size < 10 or t[-1] - t[0] < 2 * MIN_SEGMENT_S:
        return None
    return _line_sse(t, y)[0]


def descent_changepoint(track: Track, apogee_s: float) -> tuple[Changepoint | None, str]:
    """Where descent slows most sharply: the best split into two straight lines."""
    t, y = _descent_window(track, apogee_s)
    if t.size < 10 or t[-1] - t[0] < 2 * MIN_SEGMENT_S:
        return None, "The log ends before enough of the descent is recorded."
    _, sse_one = _line_sse(t, y)
    best: tuple[float, int] | None = None
    for i in range(2, t.size - 2):
        if t[i] - t[0] < MIN_SEGMENT_S or t[-1] - t[i] < MIN_SEGMENT_S:
            continue
        sse = _line_sse(t[:i], y[:i])[1] + _line_sse(t[i:], y[i:])[1]
        if best is None or sse < best[0]:
            best = (sse, i)
    if best is None:
        return None, "The descent is too short to split into two parachute phases."
    sse_two, i = best
    rate_before = _line_sse(t[:i], y[:i])[0]
    rate_after = _line_sse(t[i:], y[i:])[0]
    gain = sse_one / sse_two if sse_two > 0 else float("inf")
    if not (rate_before < 0 and rate_after < 0):
        return None, "The descending altitude does not show two descending phases."
    if rate_before / rate_after < MIN_RATE_RATIO:
        return None, "No parachute opening slows the descent clearly enough to time it."
    if gain < MIN_FIT_GAIN:
        return None, "Two phases do not fit the descent clearly better than one."
    return Changepoint(float(t[i]), rate_before, rate_after, gain), ""


def _median_rate(track: Track, start: float, end: float) -> float | None:
    sel = (track.t >= start) & (track.t <= end) & (track.altitude > GROUND_MARGIN_M)
    if int(sel.sum()) < 3:
        return None
    return float(np.median(track.vz[sel]))


def _transonic(ctx: GhostContext, ghost: Track, t: float) -> float | None:
    """The ghost's Mach at t if it is in the band where barometric altitude is unreliable."""
    mach = _interp(ghost.t, ctx.mach, t)
    return mach if TRANSONIC[0] <= mach <= TRANSONIC[1] else None


def _event(
    key: str,
    name: str,
    method: str,
    ghost_t: float,
    ghost: Track,
    real_t: float | None,
    real: Track,
    ctx: GhostContext,
    note: str = "",
) -> TimedEvent:
    g_alt = _interp(ghost.t, ghost.altitude, ghost_t)
    r_alt = None if real_t is None else _interp(real.t, real.altitude, real_t)
    mach = None if real_t is None else _transonic(ctx, ghost, real_t)
    if r_alt is not None and mach is not None:
        # The time is still valid (it may come from an accelerometer); the altitude is not.
        r_alt = None
        note = " ".join(
            filter(
                None,
                [
                    note,
                    f"Real altitude not shown: near Mach {mach:.2f} a barometric altimeter "
                    "can misread.",
                ],
            )
        )
    return TimedEvent(
        key=key,  # type: ignore[arg-type]
        name=name,
        method=method,
        ghost_t=round(ghost_t, 3),
        ghost_altitude_m=round(g_alt, 1),
        real_t=None if real_t is None else round(real_t, 3),
        real_altitude_m=None if r_alt is None else round(r_alt, 1),
        delta_t_s=None if real_t is None else round(real_t - ghost_t, 3),
        delta_altitude_m=None if r_alt is None else round(r_alt - g_alt, 1),
        status="detected" if real_t is not None else "not_detected",
        note=note or None,
    )


def _peak_vz(
    real: Track, ghost: Track, ctx: GhostContext, coarse: bool, r_thrust: float | None
) -> tuple[float | None, str]:
    """The real speed peak, only when the barometric speed can be trusted there."""
    if coarse:
        return None, "The log samples too slowly to resolve the speed peak."
    rising = real.t <= real.t[int(np.nanargmax(real.altitude))]
    r_peak = float(real.t[rising][int(np.nanargmax(real.vz[rising]))])
    mach = _transonic(ctx, ghost, r_peak)
    if mach is not None:
        return None, (
            f"Not timed: the speed peak falls near Mach {mach:.2f}, where barometric altitude "
            "(and so the speed derived from it) can misread."
        )
    if r_thrust is not None and r_peak > r_thrust + PEAK_AFTER_THRUST_S:
        return None, (
            "Not timed: the altimeter-derived speed peaks after the accelerometer shows the "
            "rocket already decelerating, so the two sensors disagree."
        )
    return r_peak, ""


def compare(
    ghost: Track,
    ctx: GhostContext,
    real: Track,
    coarse: bool,
    accelerometer_note: str | None = None,
) -> EventTiming:
    """Every event and descent rate the two flights can be compared on.

    `real.axial` must already be axial specific force (see `read_accelerometer`);
    `accelerometer_note` says how it was read, or why a logged one was not used.
    """
    events: list[TimedEvent] = []

    # Thrust < drag (both tracks are on the ghost clock, aligned at liftoff)
    g_thrust = thrust_end(ghost, ctx.liftoff_s)
    r_thrust = thrust_end(real, ctx.liftoff_s)
    if g_thrust is not None:
        note = ""
        if real.axial is None:
            note = accelerometer_note or (
                "This log has no accelerometer, so the real moment cannot be measured."
            )
        elif r_thrust is None:
            note = "The accelerometer does not show a clear, sustained end of thrust."
        events.append(
            _event(
                "thrust_end",
                "Thrust < drag",
                THRUST_METHOD,
                g_thrust,
                ghost,
                r_thrust,
                real,
                ctx,
                note,
            )
        )

    # Peak vertical speed
    g_peak = float(ghost.t[int(np.argmax(ghost.vz))])
    r_peak, note = _peak_vz(real, ghost, ctx, coarse, r_thrust)
    events.append(
        _event(
            "peak_vz", "Peak vertical speed", PEAK_VZ_METHOD, g_peak, ghost, r_peak, real, ctx, note
        )
    )

    # Apogee
    g_apo = float(ghost.t[int(np.argmax(ghost.altitude))])
    r_apo = float(real.t[int(np.nanargmax(real.altitude))])
    events.append(_event("apogee", "Apogee", APOGEE_METHOD, g_apo, ghost, r_apo, real, ctx))

    # Final parachute and descent rates
    descent: list[DescentRate] = []
    if len(ctx.deploys) >= 2:
        first_name, first_t = ctx.deploys[0]
        final_name, final_t = ctx.deploys[-1]
        cp, why = descent_changepoint(real, r_apo)
        events.append(
            _event(
                "final_deploy",
                f"{final_name} opens",
                DEPLOY_METHOD,
                final_t,
                ghost,
                None if cp is None else cp.t,
                real,
                ctx,
                why,
            )
        )
        g_first = _median_rate(ghost, first_t + DESCENT_SETTLE_S, final_t)
        g_final = _median_rate(ghost, final_t + DESCENT_SETTLE_S, float(ghost.t[-1]))
        for phase, g_rate, r_rate in (
            (f"Under {first_name}", g_first, None if cp is None else cp.rate_before),
            (f"Under {final_name}", g_final, None if cp is None else cp.rate_after),
        ):
            if g_rate is not None:
                descent.append(
                    DescentRate(
                        phase=phase,
                        ghost_mps=round(g_rate, 2),
                        real_mps=None if r_rate is None else round(r_rate, 2),
                    )
                )
        single = one_phase_rate(real, r_apo) if cp is None else None
        if single is not None:
            descent.append(
                DescentRate(
                    phase="Real descent, one phase",
                    ghost_mps=None,
                    real_mps=round(single, 2),
                )
            )
    elif len(ctx.deploys) == 1:
        # One parachute: its modelled descent rate against the whole recorded descent.
        name, t_open = ctx.deploys[0]
        g_rate = _median_rate(ghost, t_open + DESCENT_SETTLE_S, float(ghost.t[-1]))
        r_rate = one_phase_rate(real, r_apo)
        if g_rate is not None:
            descent.append(
                DescentRate(
                    phase=f"Under {name}",
                    ghost_mps=round(g_rate, 2),
                    real_mps=None if r_rate is None else round(r_rate, 2),
                )
            )
    return EventTiming(events=events, descent=descent, accelerometer=accelerometer_note)
