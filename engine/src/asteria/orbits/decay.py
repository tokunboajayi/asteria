"""Thermospheric density measured from each satellite's own orbit decay.

Drag shrinks a near-circular orbit at da/dt = -rho * B * sqrt(mu * a), where B
(drag coefficient x area / mass) is unknown. For the same satellite, the ratio
of two decay rates, each divided by sqrt(a), is therefore the ratio of the
average densities it flew through, and B cancels:

    rho_storm / rho_quiet = (da/dt / sqrt(a))_storm / (da/dt / sqrt(a))_quiet

Each rate is a least-squares slope of the mean semi-major axis of real
Space-Track element sets against time, within a stretch with no maneuver. The
same ratio is computed from NRLMSIS 2.1 over exactly the same intervals, so
measurement and model are compared like for like.

Assumes B is the same in both windows. Attitude changes (e.g. ISS solar arrays)
break that; the result is labelled per satellite, never blended across them.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from asteria.models import DecayBin, ObjectDecay
from asteria.orbits import density, ghost

BIN_DAYS = 1.0
MIN_SETS = 3
MIN_SPAN_FRACTION = 0.5  # a fit must cover at least half its bin
QUIET_MIN_DAYS = 2.0
QUIET_MIN_SETS = 5
QUIET_MIN_SNR = 5.0  # decay slope / its standard error
BIN_MIN_SNR = 3.0
METHOD = (
    "Measured: least-squares decay rate of the mean semi-major axis of real element sets "
    "in each day (maneuver-free stretch, at least 3 sets covering half the day), divided "
    "by sqrt(a), over the same quantity in the quiet window. Drag coefficient, area and "
    "mass cancel for the same satellite. Model: NRLMSIS 2.1 density averaged along the "
    "real orbit over exactly the same two intervals."
)
CAVEATS = [
    "Assumes the satellite's drag area and attitude were the same in both windows.",
    "A day is 'below noise' when its decay is under 3 standard errors: high orbits decay "
    "too slowly for daily element sets to resolve.",
]


@dataclass(frozen=True)
class Fit:
    start: datetime
    end: datetime
    n: int
    slope_km_day: float
    stderr_km_day: float
    mean_a_km: float

    @property
    def proxy(self) -> float:
        """-(da/dt) / sqrt(a): proportional to the average density (km^0.5 / day)."""
        return -self.slope_km_day / math.sqrt(self.mean_a_km)

    @property
    def proxy_err(self) -> float:
        return self.stderr_km_day / math.sqrt(self.mean_a_km)

    @property
    def snr(self) -> float:
        return -self.slope_km_day / self.stderr_km_day if self.stderr_km_day > 0 else 0.0


def linear_fit(t_days: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    """Slope and its standard error (ordinary least squares, needs >= 3 points)."""
    x, v = np.asarray(t_days, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if x.size < 3:
        raise ValueError("need at least 3 points")
    xm = x - x.mean()
    sxx = float(xm @ xm)
    if sxx == 0:
        raise ValueError("all points at one time")
    slope = float(xm @ (v - v.mean())) / sxx
    resid = v - (v.mean() + slope * xm)
    var = float(resid @ resid) / (x.size - 2)
    return slope, math.sqrt(var / sxx)


def runs(
    sets: Sequence[ghost.ElementSet], maneuvers: Sequence[datetime]
) -> list[list[ghost.ElementSet]]:
    """Split time-ordered sets so no run spans a maneuver (a maneuver epoch starts a new run)."""
    stops = set(maneuvers)
    out: list[list[ghost.ElementSet]] = []
    for s in sets:
        if not out or s.epoch in stops:
            out.append([])
        out[-1].append(s)
    return [r for r in out if r]


def fit_window(
    sets: Sequence[ghost.ElementSet],
    maneuvers: Sequence[datetime],
    start: datetime,
    end: datetime,
    min_sets: int,
    min_span_days: float,
) -> Fit | None:
    """Fit the longest maneuver-free run of sets inside [start, end)."""
    inside = [s for s in sets if start <= s.epoch < end]
    candidates = [r for r in runs(inside, maneuvers) if len(r) >= min_sets]
    if not candidates:
        return None
    run = max(candidates, key=lambda r: (r[-1].epoch - r[0].epoch, len(r)))
    span = (run[-1].epoch - run[0].epoch).total_seconds() / 86400.0
    if span < min_span_days:
        return None
    t0 = run[0].epoch
    t = [(s.epoch - t0).total_seconds() / 86400.0 for s in run]
    a = [s.semi_major_axis_km for s in run]
    slope, err = linear_fit(t, a)
    return Fit(run[0].epoch, run[-1].epoch, len(run), slope, err, float(np.mean(a)))


def ratio_err(num: Fit, den: Fit) -> tuple[float, float]:
    """Proxy ratio and its 1-sigma error (relative errors in quadrature)."""
    r = num.proxy / den.proxy
    rel = math.hypot(num.proxy_err / num.proxy, den.proxy_err / den.proxy)
    return r, abs(r) * rel


def object_decay(
    norad_id: int,
    name: str,
    sets: Sequence[ghost.ElementSet],
    maneuver_rise_m: float,
    quiet: tuple[datetime, datetime],
    storm: tuple[datetime, datetime],
    indices: density.Indices,
    iso: Callable[[datetime], str],
) -> ObjectDecay:
    maneuvers = ghost.maneuver_epochs(sets, maneuver_rise_m)
    q = fit_window(sets, maneuvers, quiet[0], quiet[1], QUIET_MIN_SETS, QUIET_MIN_DAYS)

    def empty(reason: str) -> ObjectDecay:
        return ObjectDecay(
            norad_id=norad_id,
            name=name,
            status="not_measurable",
            reason=reason,
            quiet_start=None,
            quiet_end=None,
            quiet_decay_m_per_day=None,
            quiet_snr=None,
            bins=[],
            peak=None,
        )

    if q is None:
        return empty(
            f"No maneuver-free stretch of {QUIET_MIN_DAYS:g}+ days with {QUIET_MIN_SETS}+ "
            "element sets in the quiet window."
        )
    if q.snr < QUIET_MIN_SNR:
        return empty(
            f"Quiet-window decay {-q.slope_km_day * 1000:.1f} m/day is only {q.snr:.1f} standard "
            f"errors (needs {QUIET_MIN_SNR:g}): the orbit decays too slowly to resolve."
        )
    rho_q = density.mean_density(sets, indices, q.start, q.end)

    bins: list[DecayBin] = []
    t = storm[0]
    while t + timedelta(days=BIN_DAYS) <= storm[1]:
        end = t + timedelta(days=BIN_DAYS)
        f = fit_window(sets, maneuvers, t, end, MIN_SETS, BIN_DAYS * MIN_SPAN_FRACTION)
        if f is None:
            bins.append(
                DecayBin(
                    start=iso(t),
                    end=iso(end),
                    status="no_fit",
                    n_sets=0,
                    measured_ratio=None,
                    measured_err=None,
                    model_ratio=None,
                    snr=None,
                )
            )
        else:
            model = density.mean_density(sets, indices, f.start, f.end) / rho_q
            r, e = ratio_err(f, q)
            ok = f.snr >= BIN_MIN_SNR
            bins.append(
                DecayBin(
                    start=iso(t),
                    end=iso(end),
                    status="measured" if ok else "below_noise",
                    n_sets=f.n,
                    measured_ratio=round(r, 3) if ok else None,
                    measured_err=round(e, 3) if ok else None,
                    model_ratio=round(model, 3),
                    snr=round(f.snr, 2),
                )
            )
        t = end

    measured = [b for b in bins if b.measured_ratio is not None and b.model_ratio is not None]
    peak = max(measured, key=lambda b: b.measured_ratio or 0.0) if measured else None
    return ObjectDecay(
        norad_id=norad_id,
        name=name,
        status="measured" if measured else "not_measurable",
        reason=None if measured else "No storm day resolved above noise.",
        quiet_start=iso(q.start),
        quiet_end=iso(q.end),
        quiet_decay_m_per_day=round(-q.slope_km_day * 1000, 2),
        quiet_snr=round(q.snr, 1),
        bins=bins,
        peak=peak,
    )
