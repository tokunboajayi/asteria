"""Thermospheric density measured from each satellite's own orbit decay.

Drag shrinks a near-circular orbit at da/dt = -rho * B * sqrt(mu * a), where B
(drag coefficient x area / mass) is unknown. For the same satellite, the ratio
of two decay rates, each divided by sqrt(a), is therefore the ratio of the
average densities it flew through, and B cancels:

    rho_storm / rho_quiet = (da/dt / sqrt(a))_storm / (da/dt / sqrt(a))_quiet

The quiet rate is a least-squares slope over a maneuver-free stretch of the
quiet window. A storm interval's rate is the drop in semi-major axis between its
two ends, each end estimated from a local straight-line fit to every element
set within half a day of it. Single-day slopes from 3-4 element sets are not
used: Space-Track fits lag and scatter during a storm, and three points give no
honest error. The same ratio is computed from NRLMSIS 2.1 over exactly the same
intervals, so measurement and model are compared like for like.

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

# Storm intervals, days after onset: main phase, then recovery.
INTERVALS_DAYS = ((0.0, 2.0), (2.0, 5.0))
ANCHOR_HALF_DAYS = 0.5
ANCHOR_MIN_SETS = 3
QUIET_MIN_DAYS = 2.0
QUIET_MIN_SETS = 5
QUIET_MIN_SNR = 5.0  # decay slope / its standard error
INTERVAL_MIN_SNR = 3.0
METHOD = (
    "Measured: drop in the mean semi-major axis of real element sets across each storm "
    "interval (each end from a straight-line fit to all sets within half a day of it), "
    "divided by sqrt(a) and the interval's length, over the decay slope of a "
    "maneuver-free stretch of the quiet window. Drag coefficient, area and mass cancel for "
    "the same satellite. Model: NRLMSIS 2.1 density averaged along the real orbit over "
    "exactly the same intervals."
)
CAVEATS = [
    "Assumes the satellite's drag area and attitude were the same in both windows.",
    "An interval is 'below noise' when its decay is under 3 standard errors: high orbits "
    "decay too slowly for element sets to resolve.",
    "Element sets are fits over days of tracking and lag a sudden density rise, so the "
    "main-phase ratio can be understated and part of it appear in the recovery interval.",
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


@dataclass(frozen=True)
class Anchor:
    a_km: float
    se_km: float
    n: int


def anchor(sets: Sequence[ghost.ElementSet], at: datetime) -> Anchor | None:
    """Semi-major axis at `at` from a straight line through all sets within half a day."""
    half = timedelta(days=ANCHOR_HALF_DAYS)
    near = [s for s in sets if at - half <= s.epoch <= at + half]
    if len(near) < ANCHOR_MIN_SETS:
        return None
    x = np.array([(s.epoch - at).total_seconds() / 86400.0 for s in near])
    y = np.array([s.semi_major_axis_km for s in near])
    if float(np.ptp(x)) == 0:
        return None
    slope, _ = linear_fit(x.tolist(), y.tolist())
    xm = x - x.mean()
    resid = y - (y.mean() + slope * xm)
    s2 = float(resid @ resid) / (x.size - 2)
    a0 = float(y.mean() + slope * (0.0 - x.mean()))
    se = math.sqrt(s2 * (1.0 / x.size + x.mean() ** 2 / float(xm @ xm)))
    return Anchor(a0, se, len(near))


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    a0: Anchor
    a1: Anchor

    @property
    def days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400.0

    @property
    def rate_km_day(self) -> float:
        """Mean decay rate (positive when the orbit shrinks)."""
        return (self.a0.a_km - self.a1.a_km) / self.days

    @property
    def rate_err(self) -> float:
        return math.hypot(self.a0.se_km, self.a1.se_km) / self.days

    @property
    def proxy(self) -> float:
        return self.rate_km_day / math.sqrt((self.a0.a_km + self.a1.a_km) / 2)

    @property
    def proxy_err(self) -> float:
        return self.rate_err / math.sqrt((self.a0.a_km + self.a1.a_km) / 2)

    @property
    def snr(self) -> float:
        return self.rate_km_day / self.rate_err if self.rate_err > 0 else math.inf


def interval(
    sets: Sequence[ghost.ElementSet], maneuvers: Sequence[datetime], start: datetime, end: datetime
) -> Interval | str:
    """The interval's decay, or why it cannot be measured."""
    half = timedelta(days=ANCHOR_HALF_DAYS)
    if any(start - half <= m <= end + half for m in maneuvers):
        return "maneuver"
    a0, a1 = anchor(sets, start), anchor(sets, end)
    if a0 is None or a1 is None:
        return "too few element sets near an end"
    return Interval(start, end, a0, a1)


def ratio_err(num: Fit | Interval, den: Fit) -> tuple[float, float]:
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
    for d0, d1 in INTERVALS_DAYS:
        start = storm[0] + timedelta(days=d0)
        end = storm[0] + timedelta(days=d1)
        iv = interval(sets, maneuvers, start, end)
        if isinstance(iv, str):
            bins.append(
                DecayBin(
                    start=iso(start),
                    end=iso(end),
                    status="no_fit",
                    note=iv,
                    n_sets=0,
                    measured_ratio=None,
                    measured_err=None,
                    model_ratio=None,
                    snr=None,
                )
            )
            continue
        model = density.mean_density(sets, indices, start, end) / rho_q
        r, e = ratio_err(iv, q)
        ok = iv.snr >= INTERVAL_MIN_SNR
        bins.append(
            DecayBin(
                start=iso(start),
                end=iso(end),
                status="measured" if ok else "below_noise",
                note=None,
                n_sets=iv.a0.n + iv.a1.n,
                measured_ratio=round(r, 3) if ok else None,
                measured_err=round(e, 3) if ok else None,
                model_ratio=round(model, 3),
                snr=round(iv.snr, 2),
            )
        )

    measured = [b for b in bins if b.measured_ratio is not None and b.model_ratio is not None]
    peak = max(measured, key=lambda b: b.measured_ratio or 0.0) if measured else None
    return ObjectDecay(
        norad_id=norad_id,
        name=name,
        status="measured" if measured else "not_measurable",
        reason=None if measured else "No storm interval resolved above noise.",
        quiet_start=iso(q.start),
        quiet_end=iso(q.end),
        quiet_decay_m_per_day=round(-q.slope_km_day * 1000, 2),
        quiet_snr=round(q.snr, 1),
        bins=bins,
        peak=peak,
    )
