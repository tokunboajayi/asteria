"""NASA Open MCT telemetry dictionary and historical telemetry, from published artifacts.

The dictionary follows Open MCT's telemetry tutorial format: each measurement has
a `value` range and a `utc` domain. Every key listed is served; nothing is listed
that the artifacts cannot back. Rocket points use the notebook's weather hour as
time origin (the ghost's clock), which is stated in the measurement name.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict

from asteria.api.store import OrbitStore, RocketStore


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenMctValue(_Model):
    key: str
    name: str
    units: str | None = None
    format: str
    source: str | None = None
    hints: dict[str, int]


class OpenMctMeasurement(_Model):
    key: str
    name: str
    values: list[OpenMctValue]


class OpenMctDictionary(_Model):
    name: str
    key: str
    measurements: list[OpenMctMeasurement]


class OpenMctPoint(_Model):
    id: str
    timestamp: int
    value: float


Sample = tuple[datetime, float]


def _when(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(UTC)


def _pairs(times: Sequence[str], values: Sequence[float | int | None]) -> list[Sample]:
    return [(_when(t), float(v)) for t, v in zip(times, values, strict=True) if v is not None]


def _clock(t0: datetime, t: Sequence[float], v: Sequence[float | None]) -> list[Sample]:
    """Ghost-clock seconds placed after `t0`."""
    return [
        (t0 + timedelta(seconds=ti), float(vi))
        for ti, vi in zip(t, v, strict=True)
        if vi is not None
    ]


def _values(units: str) -> list[OpenMctValue]:
    return [
        OpenMctValue(key="value", name="Value", units=units, format="float", hints={"range": 1}),
        OpenMctValue(
            key="utc", name="Timestamp", format="utc", source="timestamp", hints={"domain": 1}
        ),
    ]


_ORBIT_FIELDS = (
    ("in_track_km", "in-track gap, tracked − ghost"),
    ("radial_km", "radial gap, tracked − ghost"),
    ("cross_track_km", "cross-track gap, tracked − ghost"),
    ("tracked_alt_km", "tracked altitude"),
)


class Catalog:
    """Every telemetry point the artifacts can back: key -> (name, units, samples)."""

    def __init__(self, rockets: RocketStore | None, orbits: OrbitStore | None) -> None:
        self.points: dict[str, tuple[str, str, list[Sample]]] = {}
        if orbits is not None:
            self._orbits(orbits)
        if rockets is not None:
            self._rockets(rockets)

    def _orbits(self, o: OrbitStore) -> None:
        w = o.spaceweather
        self.points["weather.kp"] = ("Kp index (NASA OMNI2)", "index", _pairs(w.times, w.kp))
        self.points["weather.dst"] = ("Dst (NASA OMNI2)", "nT", _pairs(w.times, w.dst_nt))
        for obj in o.fleet.objects:
            s = obj.storm
            if s is None:
                continue
            for field, label in _ORBIT_FIELDS:
                self.points[f"orbit.{obj.norad_id}.{field}"] = (
                    f"{obj.name}: {label}",
                    "km",
                    _pairs(s.epochs, getattr(s, field)),
                )
        if o.density is not None:
            for d in o.density.objects:
                self.points[f"orbit.{d.norad_id}.density_ratio"] = (
                    f"{d.name}: modelled density ÷ quiet counterfactual (NRLMSIS 2.1)",
                    "ratio",
                    _pairs(d.times, d.ratio),
                )

    def _rockets(self, r: RocketStore) -> None:
        for fid, f in r.flights.items():
            if f.weather_time_utc is None:
                continue
            t0 = _when(f.weather_time_utc)
            name = f"{f.summary.name} (clock: notebook weather hour)"

            self.points[f"rocket.{fid}.ghost_altitude_m"] = (
                f"{name}: ghost altitude AGL",
                "m",
                _clock(t0, f.ghost.t, f.ghost.altitude),
            )
            self.points[f"rocket.{fid}.real_altitude_m"] = (
                f"{name}: real altitude AGL, liftoff-aligned",
                "m",
                _clock(t0, f.delta.t, f.delta.real_altitude),
            )

    def dictionary(self) -> OpenMctDictionary:
        return OpenMctDictionary(
            name="Asteria",
            key="asteria",
            measurements=[
                OpenMctMeasurement(key=k, name=name, values=_values(units))
                for k, (name, units, _) in sorted(self.points.items())
            ],
        )

    def telemetry(self, key: str) -> list[OpenMctPoint] | None:
        if key not in self.points:
            return None
        return [
            OpenMctPoint(id=key, timestamp=int(t.timestamp() * 1000), value=v)
            for t, v in self.points[key][2]
        ]
