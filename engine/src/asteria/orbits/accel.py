"""Measured density from GRACE-FO 1's accelerometer (TU Delft TOLEOS v0003, via ESA).

The independent check on everything else in the density panel:
* the same storm/quiet intervals the orbit-decay method used: accelerometer ratio
  vs decay ratio vs NRLMSIS ratio;
* absolute density, hour by hour: accelerometer (orbit mean) vs NRLMSIS 2.1
  averaged along the same orbit.

Only samples with validity_flag == 0 (the provider's "valid") are used; fill values
(9.99e32) are dropped. An interval needs 80% valid coverage or it is not compared.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from asteria.models import AccelCheck, AccelDensity, ObjectDecay

FILL = 1e32
MIN_COVERAGE = 0.8
CADENCE_S = 10.0
SOURCE = (
    "GRACE-FO 1 accelerometer-derived thermosphere density, TU Delft TOLEOS v0003. "
    "Data provided by the European Space Agency (ESA)"
)

F = NDArray[np.float64]


@dataclass(frozen=True)
class Series:
    t: F  # seconds since the Unix epoch, UTC
    rho: F  # kg/m3
    rho_orbitmean: F

    def window(self, start: datetime, end: datetime, orbit_mean: bool = False) -> F:
        a, b = start.timestamp(), end.timestamp()
        inside = (self.t >= a) & (self.t < b)
        v = (self.rho_orbitmean if orbit_mean else self.rho)[inside]
        return v[np.isfinite(v)]

    def coverage(self, start: datetime, end: datetime) -> float:
        expected = (end - start).total_seconds() / CADENCE_S
        return float(self.window(start, end).size) / expected if expected > 0 else 0.0


def clean(t: F, rho: F, rho_om: F, flag: NDArray[np.int64], flag_om: NDArray[np.int64]) -> Series:
    """Drop fill values; set samples the provider flags as invalid to NaN."""
    good_t = t < FILL
    rho = np.where((flag == 0) & (rho < FILL) & (rho > 0), rho, np.nan)
    rho_om = np.where((flag_om == 0) & (rho_om < FILL) & (rho_om > 0), rho_om, np.nan)
    order = np.argsort(t[good_t])
    return Series(t[good_t][order], rho[good_t][order], rho_om[good_t][order])


def load(files: Sequence[Path]) -> Series:
    import cdflib

    parts: list[tuple[F, ...]] = []
    for f in files:
        c = cdflib.CDF(str(f))
        epoch_ms = np.asarray(c.varget("time"), dtype=np.float64)
        # CDF_EPOCH: milliseconds since 0000-01-01; to Unix seconds.
        unix = np.asarray(cdflib.cdfepoch.unixtime(epoch_ms), dtype=np.float64)
        parts.append(
            (
                unix,
                np.asarray(c.varget("density"), dtype=np.float64),
                np.asarray(c.varget("density_orbitmean"), dtype=np.float64),
                np.asarray(c.varget("validity_flag"), dtype=np.int64).astype(np.float64),
                np.asarray(c.varget("validity_flag_orbitmean"), dtype=np.int64).astype(np.float64),
            )
        )
    t, rho, om, fl, flo = (np.concatenate([p[i] for p in parts]) for i in range(5))
    return clean(t, rho, om, fl.astype(np.int64), flo.astype(np.int64))


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def interval_mean(s: Series, start: datetime, end: datetime) -> float | None:
    if s.coverage(start, end) < MIN_COVERAGE:
        return None
    return float(np.mean(s.window(start, end)))


def build(
    s: Series,
    norad_id: int,
    decay: ObjectDecay,
    times: Sequence[str],
    model_kg_m3: Sequence[float] | None,
    files: Sequence[tuple[str, str]],
) -> AccelDensity:
    checks: list[AccelCheck] = []
    quiet = None
    if decay.quiet_start and decay.quiet_end:
        quiet = interval_mean(s, _utc(decay.quiet_start), _utc(decay.quiet_end))
    for b in decay.bins:
        num = interval_mean(s, _utc(b.start), _utc(b.end))
        checks.append(
            AccelCheck(
                start=b.start,
                end=b.end,
                accel_ratio=None if num is None or quiet is None else round(num / quiet, 3),
                decay_ratio=b.measured_ratio,
                decay_err=b.measured_err,
                model_ratio=b.model_ratio,
            )
        )
    measured: list[float | None] = []
    for t in times:
        h = _utc(t)
        v = s.window(h - timedelta(minutes=30), h + timedelta(minutes=30), orbit_mean=True)
        measured.append(float(f"{float(np.mean(v)):.4e}") if v.size else None)
    pairs = (
        [(m, x) for m, x in zip(model_kg_m3, measured, strict=True) if x is not None]
        if model_kg_m3 is not None
        else []
    )
    bias = float(np.median([m / x for m, x in pairs])) if pairs else None
    return AccelDensity(
        norad_id=norad_id,
        source=SOURCE,
        files=[f"{name} sha256:{sha}" for name, sha in files],
        times=list(times),
        measured_kg_m3=measured,
        model_kg_m3=None if model_kg_m3 is None else list(model_kg_m3),
        median_model_over_measured=None if bias is None else round(bias, 3),
        checks=checks,
    )
