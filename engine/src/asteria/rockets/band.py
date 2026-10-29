"""Fleet band: the ghost re-flown at the drag factors the other flights needed.

Every flight has a calibrated k_own: the drag scale that makes RocketPy's ghost
reach the real apogee. For flight i, the band is the ghost re-flown at the lowest
and highest k_own among the OTHER flights (bracketed calibrations only). It asks a
falsifiable question: had this flight erred like any of the others, where would it
have gone? For n exchangeable flights, the range of n others contains a new one
with probability (n - 1) / (n + 1); the build counts how often it actually did.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from asteria.models import FleetBand

MIN_OTHERS = 2


@dataclass(frozen=True)
class KRange:
    k_low: float
    k_high: float
    n_others: int


def held_out_range(
    k_own: Mapping[str, float], bracketed: Mapping[str, bool], flight_id: str
) -> KRange | None:
    others = [k for fid, k in k_own.items() if fid != flight_id and bracketed[fid]]
    if len(others) < MIN_OTHERS:
        return None
    return KRange(min(others), max(others), len(others))


def expected_coverage(n_others: int) -> float:
    return (n_others - 1) / (n_others + 1)


def outside_intervals(
    t: Sequence[float],
    real: Sequence[float | None],
    low: Sequence[float | None],
    high: Sequence[float | None],
    window: tuple[float, float],
) -> list[tuple[float, float]]:
    """Runs of grid points inside `window` where the real altitude lies outside [low, high]."""
    out: list[tuple[float, float]] = []
    start: float | None = None
    last = 0.0
    for ti, r, lo, hi in zip(t, real, low, high, strict=True):
        outside = (
            window[0] <= ti <= window[1]
            and r is not None
            and lo is not None
            and hi is not None
            and not lo <= r <= hi
        )
        if outside:
            if start is None:
                start = ti
            last = ti
        elif start is not None:
            out.append((start, last))
            start = None
    if start is not None:
        out.append((start, last))
    return out


def make(
    k: KRange,
    t: Sequence[float],
    alt_a: Sequence[float | None],
    alt_b: Sequence[float | None],
    apogee_a: float,
    apogee_b: float,
    real_on_grid: Sequence[float | None],
    real_apogee_m: float,
    coast: tuple[float, float],
) -> FleetBand:
    low: list[float | None] = []
    high: list[float | None] = []
    for a, b in zip(alt_a, alt_b, strict=True):
        if a is None or b is None:
            low.append(None)
            high.append(None)
        else:
            low.append(round(min(a, b), 2))
            high.append(round(max(a, b), 2))
    ap_lo, ap_hi = min(apogee_a, apogee_b), max(apogee_a, apogee_b)
    return FleetBand(
        k_low=k.k_low,
        k_high=k.k_high,
        n_others=k.n_others,
        expected_coverage=round(expected_coverage(k.n_others), 4),
        t=list(t),
        altitude_low=low,
        altitude_high=high,
        apogee_low_m=round(ap_lo, 3),
        apogee_high_m=round(ap_hi, 3),
        real_apogee_inside=ap_lo <= real_apogee_m <= ap_hi,
        coast_s=coast,
        real_outside=outside_intervals(t, real_on_grid, low, high, coast),
    )
