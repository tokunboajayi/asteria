"""Load a published flight log exactly as declared in the catalog.

Deliberately small: read the named columns, convert declared units, apply
the declared (and evidenced) cutoff, and report everything that was done.
No smoothing, filling, or outlier rejection happens here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
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
