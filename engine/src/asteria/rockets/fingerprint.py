"""Motor & drag fingerprint: what a verified accelerometer says about the burn and the coast.

Exploratory analysis, added after the pre-registered correction result was
known. It describes each flight; it is never used to correct a ghost.

Two readings, taken identically from the real accelerometer and from the
ghost's own simulated sensor (axial specific force, see
ghost.axial_specific_force), over windows fixed once per flight:

* burn: the speed the sensor gained, ∫ f dt, from liftoff to 0.5 s after the
  later of the two "thrust < drag" moments;
* coast: the mean deceleration the sensor felt over the next 5 s, starting
  0.5 s later (motor out, so the sensor feels drag only).

Each is reported as real ÷ ghost. Only accelerometers whose zero has been
verified are used (events.read_accelerometer).

Not attempted: splitting the apogee miss into metres "from the motor" and
"from drag". It was tried, by re-simulating the notebook with thrust × s and
drag × k and solving for both readings. The effects are a few per cent, the
size of an ordinary accelerometer calibration error, and within that error a
weaker motor and less drag trade off against each other: the solutions ran
to the edges of the search range (drag × 0.3, thrust × 1.16 with drag × 1.64)
or failed to match at all. Those numbers would have been guesses, so they are
not reported.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from asteria.models import Fingerprint
from asteria.rockets import events

FloatArray = NDArray[np.float64]

BURN_MARGIN_S = 0.5
COAST_GAP_S = 0.5
COAST_WINDOW_S = 5.0
MIN_SAMPLES = 3

METHOD = (
    "Real ÷ ghost for two accelerometer readings over fixed windows: the speed gained in the "
    "burn (∫ axial specific force from liftoff to 0.5 s after the later 'thrust < drag') and "
    "the mean deceleration in the next 5 s of coast (drag only). Exploratory: added after the "
    "pre-registered result was known; never used to correct a ghost."
)
NOT_ATTEMPTED = (
    "Splitting the apogee miss into metres from the motor and from drag was tried and rejected: "
    "the effects are a few per cent, the size of an accelerometer calibration error, and within "
    "that error a weaker motor and less drag trade off against each other, so the split would "
    "be a guess."
)


def burn_gain(t: FloatArray, force: FloatArray, start: float, end: float) -> float | None:
    """∫ force dt from start to end (m/s), with the ends interpolated."""
    inside = (t > start) & (t < end) & np.isfinite(force)
    if int(inside.sum()) < MIN_SAMPLES:
        return None
    tt = np.concatenate([[start], t[inside], [end]])
    ff = np.concatenate([[np.interp(start, t, force)], force[inside], [np.interp(end, t, force)]])
    return float(np.trapezoid(ff, tt))


def window_mean(t: FloatArray, force: FloatArray, start: float, end: float) -> float | None:
    sel = (t >= start) & (t <= end) & np.isfinite(force)
    return float(np.mean(force[sel])) if int(sel.sum()) >= MIN_SAMPLES else None


def measure(
    ghost: events.Track,
    real: events.Track,
    liftoff_s: float,
    accelerometer_note: str | None,
) -> Fingerprint:
    """Burn and coast readings for one flight; `real.axial` must be verified specific force."""
    if real.axial is None or ghost.axial is None:
        return _not_measured(
            accelerometer_note
            or "This log has no accelerometer, so burn and coast are not measured."
        )
    g_end = events.thrust_end(ghost, liftoff_s)
    r_end = events.thrust_end(real, liftoff_s)
    if g_end is None or r_end is None:
        return _not_measured("The end of thrust could not be located in both flights.")
    burn_end = max(g_end, r_end) + BURN_MARGIN_S
    coast = (burn_end + COAST_GAP_S, burn_end + COAST_GAP_S + COAST_WINDOW_S)
    g_burn = burn_gain(ghost.t, ghost.axial, liftoff_s, burn_end)
    r_burn = burn_gain(real.t, real.axial, liftoff_s, burn_end)
    g_coast = window_mean(ghost.t, ghost.axial, *coast)
    r_coast = window_mean(real.t, real.axial, *coast)
    if None in (g_burn, r_burn, g_coast, r_coast):
        return _not_measured("Too few accelerometer samples in the burn or coast window.")
    assert g_burn is not None and r_burn is not None and g_coast is not None and r_coast is not None
    if g_burn <= 0 or r_burn <= 0 or g_coast >= 0 or r_coast >= 0:
        return _not_measured("The readings do not show a burn followed by a coast.")
    return Fingerprint(
        status="measured",
        burn_gain_real_mps=round(r_burn, 1),
        burn_gain_ghost_mps=round(g_burn, 1),
        burn_ratio=round(r_burn / g_burn, 4),
        coast_decel_real_mps2=round(r_coast, 2),
        coast_decel_ghost_mps2=round(g_coast, 2),
        coast_drag_ratio=round(r_coast / g_coast, 4),
        burn_window_s=(round(liftoff_s, 2), round(burn_end, 2)),
        coast_window_s=(round(coast[0], 2), round(coast[1], 2)),
        reason=None,
    )


def _not_measured(reason: str) -> Fingerprint:
    return Fingerprint(
        status="not_measured",
        burn_gain_real_mps=None,
        burn_gain_ghost_mps=None,
        burn_ratio=None,
        coast_decel_real_mps2=None,
        coast_decel_ghost_mps2=None,
        coast_drag_ratio=None,
        burn_window_s=None,
        coast_window_s=None,
        reason=reason,
    )
