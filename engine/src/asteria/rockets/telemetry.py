"""Load a published flight log exactly as declared in the catalog.

Deliberately small: read the named columns, convert declared units, apply
the declared (and evidenced) cutoff, and report everything that was done.
No smoothing, filling, or outlier rejection happens here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

FT_TO_M = 0.3048  # exact, by definition

FloatArray = NDArray[np.float64]
Unit = Literal["m", "ft", "m/s", "ft/s", "m/s²", "g"]
_SCALE: dict[str, tuple[str, float]] = {
    "m": ("m", 1.0),
    "ft": ("m", FT_TO_M),
    "m/s": ("m/s", 1.0),
    "ft/s": ("m/s", FT_TO_M),
    "m/s²": ("m/s²", 1.0),
    "g": ("g", 1.0),  # kept in g: converting would need the logger's own g
}


@dataclass(frozen=True)
class ExtraChannel:
    """Another logged column shown as published (after unit conversion)."""

    key: str
    column: str
    unit: Unit
    label: str


@dataclass(frozen=True)
class LogSpec:
    """Which columns of which published file hold the flight."""

    path: str
    time_column: str
    altitude_column: str
    altitude_unit: Literal["m", "ft"]
    extra: tuple[ExtraChannel, ...] = field(default_factory=tuple)
    delimiter: str = ","
    keep_until_s: float | None = None
    keep_until_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.keep_until_s is None) != (self.keep_until_reason is None):
            raise ValueError(f"{self.path}: a cutoff needs both a time and a written reason")
        keys = [c.key for c in self.extra]
        if len(keys) != len(set(keys)) or {"altitude", "vz"} & set(keys):
            raise ValueError(f"{self.path}: extra channel keys must be unique and not reserved")


@dataclass(frozen=True)
class GnssSpec:
    path: str
    time_column: str
    latitude_column: str
    longitude_column: str
    delimiter: str = ","


@dataclass(frozen=True)
class RawLog:
    """Rows as published (after the declared cutoff), in file order, SI units."""

    t: FloatArray
    altitude_m: FloatArray
    extra: dict[str, FloatArray]
    rows_read: int
    rows_after_cutoff: int


@dataclass(frozen=True)
class CleanLog:
    """Strictly increasing time base for interpolation (first sample kept per time)."""

    t: FloatArray
    altitude_m: FloatArray
    extra: dict[str, FloatArray]
    duplicate_timestamps: int
    median_interval_s: float


def _number(row: list[str], i: int) -> float:
    try:
        return float(row[i])
    except (IndexError, ValueError):
        return float("nan")


def read_columns(
    path: Path, required: list[str], delimiter: str, optional: list[str] | None = None
) -> tuple[list[FloatArray], int]:
    """Numeric rows of the named columns (first occurrence of each header name).

    A row is a sample only if every *required* column parses as a number;
    optional columns that do not parse become NaN and never remove a row.
    """
    optional = optional or []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = next(reader)
        try:
            req = [header.index(n) for n in required]
            opt = [header.index(n) for n in optional]
        except ValueError as exc:
            raise KeyError(f"{path.name}: column missing ({exc}); header={header}") from exc
        out: list[list[float]] = [[] for _ in required + optional]
        rows = 0
        for row in reader:
            rows += 1
            values = [_number(row, i) for i in req]
            if any(np.isnan(v) for v in values):
                continue
            values += [_number(row, i) for i in opt]
            for col, v in zip(out, values, strict=True):
                col.append(v)
    return [np.asarray(c, dtype=np.float64) for c in out], rows


def load_log(root: Path, spec: LogSpec) -> RawLog:
    cols, rows = read_columns(
        root / spec.path,
        [spec.time_column, spec.altitude_column],
        spec.delimiter,
        optional=[c.column for c in spec.extra],
    )
    t, alt = cols[0], cols[1] * _SCALE[spec.altitude_unit][1]
    extra = {c.key: cols[2 + k] * _SCALE[c.unit][1] for k, c in enumerate(spec.extra)}
    after = 0
    if spec.keep_until_s is not None:
        keep = t <= spec.keep_until_s
        after = int((~keep).sum())
        t, alt = t[keep], alt[keep]
        extra = {k: v[keep] for k, v in extra.items()}
    if t.size < 10:
        raise ValueError(f"{spec.path}: only {t.size} numeric samples")
    return RawLog(t=t, altitude_m=alt, extra=extra, rows_read=rows, rows_after_cutoff=after)


def si_unit(unit: Unit) -> str:
    return _SCALE[unit][0]


def clean(raw: RawLog) -> CleanLog:
    """Stable-sort by time and keep the first sample at each time stamp."""
    order = np.argsort(raw.t, kind="stable")
    t = raw.t[order]
    keep = np.concatenate(([True], np.diff(t) > 0))
    return CleanLog(
        t=t[keep],
        altitude_m=raw.altitude_m[order][keep],
        extra={k: v[order][keep] for k, v in raw.extra.items()},
        duplicate_timestamps=int((~keep).sum()),
        median_interval_s=float(np.median(np.diff(t[keep]))),
    )


@dataclass(frozen=True)
class Gnss:
    t: FloatArray
    latitude: FloatArray
    longitude: FloatArray


def load_gnss(root: Path, spec: GnssSpec) -> Gnss:
    """GNSS fixes, dropping rows with no fix (latitude or longitude exactly 0)."""
    (t, lat, lon), _ = read_columns(
        root / spec.path,
        [spec.time_column, spec.latitude_column, spec.longitude_column],
        spec.delimiter,
    )
    valid = (lat != 0) & (lon != 0) & (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    order = np.argsort(t[valid], kind="stable")
    return Gnss(t=t[valid][order], latitude=lat[valid][order], longitude=lon[valid][order])


# --- Real UTC clock in a log ---------------------------------------------------
@dataclass(frozen=True)
class UtcClockSpec:
    """A log whose rows carry a whole-second UTC clock (e.g. a GPS receiver's)."""

    path: str
    time_column: str
    columns: tuple[str, str, str, str, str, str] = (
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
    )
    source: str = "GPS clock in the flight log (UTC as logged, whole seconds)"


@dataclass(frozen=True)
class UtcClock:
    """UTC = offset + log time, with the offset known to within [offset_low, offset_high)."""

    epoch: datetime  # log time 0, midpoint estimate
    half_width_s: float
    rows: int
    source: str

    def at(self, log_t: float) -> datetime:
        return self.epoch + timedelta(seconds=log_t)


def offset_bounds(log_t: FloatArray, utc_floor_s: FloatArray) -> tuple[float, float]:
    """Interval for O (UTC = O + log time) from a whole-second clock that steps.

    A receiver reports second S once its fix for S arrives, after an unknown delay
    L in [0, 1) s, and repeats it until the next. At each step, first seen at log
    time t: O = S - t + L. Every step must agree, so O lies in
    [max(S - t), min(S - t) + 1). The first group is skipped (the log may start mid-second).
    """
    change = np.flatnonzero(np.diff(utc_floor_s) != 0) + 1
    if change.size < 3:
        raise ValueError("fewer than 3 clock steps in the log")
    o = utc_floor_s[change] - log_t[change]
    lo, hi = float(np.max(o)), float(np.min(o) + 1.0)
    if not lo < hi:
        raise ValueError(f"UTC clock steps disagree by more than 1 s ({lo - hi + 1:.3f} s)")
    return lo, hi


def load_utc_clock(root: Path, spec: UtcClockSpec) -> UtcClock:
    cols, _ = read_columns(root / spec.path, [spec.time_column, *spec.columns], ",")
    t = cols[0]
    y, mo, d, h, mi, se = (c.astype(int) for c in cols[1:])
    valid = (y >= 1980) & (mo >= 1) & (d >= 1)  # receivers log zeros before a fix
    if int(valid.sum()) < 10:
        raise ValueError(f"{spec.path}: fewer than 10 rows with a UTC clock")
    ref = datetime(int(y[valid][0]), 1, 1, tzinfo=UTC)
    secs = np.array(
        [
            (
                datetime(int(a), int(b), int(c), int(e), int(f), int(g), tzinfo=UTC) - ref
            ).total_seconds()
            for a, b, c, e, f, g in zip(
                y[valid], mo[valid], d[valid], h[valid], mi[valid], se[valid], strict=True
            )
        ]
    )
    lo, hi = offset_bounds(t[valid], secs)
    return UtcClock(
        epoch=ref + timedelta(seconds=(lo + hi) / 2),
        half_width_s=(hi - lo) / 2,
        rows=int(valid.sum()),
        source=spec.source,
    )
