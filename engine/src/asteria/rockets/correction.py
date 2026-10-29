"""Drag-scale re-simulation, per-flight calibration, and the held-out fleet model.

Pre-registered (see gan-harness/spec.md, F4) before any result was seen:

* k_i  = the drag scale (both power-on and power-off curves × k) that makes
         flight i's ghost apogee equal its real apogee. Bracket [0.5, 1.5].
* k̂_i = median of the OTHER flights' k, clipped to [0.8, 1.2].
* The corrected ghost for flight i is a full re-simulation at k̂_i. Flight i's
  own k_i is never used for its own correction.
"""

from __future__ import annotations

import contextlib
import statistics
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from scipy.optimize import brentq

from asteria.models import BandCoverage, CorrectionAggregate, CorrectionReport, CorrectionRow
from asteria.rockets.ghost import apogee_agl
from asteria.rockets.notebook import seed_rng

K_BRACKET = (0.5, 1.5)
K_CLIP = (0.8, 1.2)
K_XTOL = 1e-4
MODEL_TEXT = "Fleet-median drag scale from the other flights, clipped to [0.8, 1.2]"
REPRODUCTION_RTOL = 1e-6


class _ScaledDrag:
    """Multiplies a RocketPy 7-input drag function by a constant."""

    def __init__(self, base: Callable[..., float], k: float) -> None:
        self.base = base
        self.k = k

    def __call__(self, *args: Any) -> float:
        return self.k * self.base(*args)


@contextlib.contextmanager
def scaled_drag(rocket: Any, k: float) -> Iterator[None]:
    on, off = rocket.power_on_drag_7d, rocket.power_off_drag_7d
    rocket.power_on_drag_7d = _ScaledDrag(on, k)
    rocket.power_off_drag_7d = _ScaledDrag(off, k)
    try:
        yield
    finally:
        rocket.power_on_drag_7d, rocket.power_off_drag_7d = on, off


def resimulate(flight_kwargs: Mapping[str, Any], k: float, *, to_apogee: bool) -> Any:
    """Re-run RocketPy's Flight with the notebook's exact arguments, drag × k."""
    from rocketpy import Flight

    kwargs = dict(flight_kwargs)
    if to_apogee:
        kwargs["terminate_on_apogee"] = True
    seed_rng()  # same parachute noise on every re-run, so results are reproducible
    with scaled_drag(kwargs["rocket"], k):
        return Flight(**kwargs)


@dataclass(frozen=True)
class Calibration:
    k_own: float
    bracketed: bool


def check_reproduction(flight_kwargs: Mapping[str, Any], notebook_apogee_agl: float) -> None:
    """Re-simulate at k = 1 and require the notebook's apogee back (harness fidelity)."""
    again = apogee_agl(resimulate(flight_kwargs, 1.0, to_apogee=True))
    if abs(again - notebook_apogee_agl) > REPRODUCTION_RTOL * abs(notebook_apogee_agl):
        raise RuntimeError(
            f"re-simulation at k=1 gave {again:.6f} m, notebook gave {notebook_apogee_agl:.6f} m"
        )


def calibrate(flight_kwargs: Mapping[str, Any], real_apogee_m: float) -> Calibration:
    def gap(k: float) -> float:
        return apogee_agl(resimulate(flight_kwargs, k, to_apogee=True)) - real_apogee_m

    lo, hi = K_BRACKET
    g_lo, g_hi = gap(lo), gap(hi)
    if g_lo * g_hi > 0:
        # Not bracketed: the closest edge is reported as such, never extrapolated.
        k = lo if abs(g_lo) < abs(g_hi) else hi
        return Calibration(k_own=k, bracketed=False)
    k = float(brentq(gap, lo, hi, xtol=K_XTOL))
    return Calibration(k_own=round(k, 5), bracketed=True)


def held_out_k(k_own: Mapping[str, float], flight_id: str) -> float:
    others = [k for fid, k in k_own.items() if fid != flight_id]
    if not others:
        raise ValueError("need at least two flights for a held-out estimate")
    lo, hi = K_CLIP
    return min(max(statistics.median(others), lo), hi)


def error_pct(predicted: float, real: float) -> float:
    return (predicted - real) / real * 100.0


def report(
    rows: list[CorrectionRow], band_coverage: BandCoverage | None = None
) -> CorrectionReport:
    before = statistics.median(abs(r.err_before_pct) for r in rows)
    after = statistics.median(abs(r.err_after_pct) for r in rows)
    return CorrectionReport(
        model=MODEL_TEXT,
        clip=K_CLIP,
        k_bracket=K_BRACKET,
        evaluation="leave-one-flight-out",
        per_flight=rows,
        aggregate=CorrectionAggregate(
            median_abs_err_before_pct=before,
            median_abs_err_after_pct=after,
            n_improved=sum(abs(r.err_after_pct) < abs(r.err_before_pct) for r in rows),
            n_worse=sum(abs(r.err_after_pct) > abs(r.err_before_pct) for r in rows),
        ),
        band_coverage=band_coverage,
    )
