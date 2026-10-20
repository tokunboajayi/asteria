"""Sample a RocketPy Flight (the ghost) onto a fixed grid, and list its events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from asteria.models import Event, GhostSeries

FloatArray = NDArray[np.float64]

ASCENT_STEP_S = 0.05
DESCENT_STEP_S = 0.5
LIFTOFF_ALTITUDE_M = 10.0


@dataclass(frozen=True)
class GhostArrays:
    t: FloatArray
    altitude: FloatArray
    vz: FloatArray
    speed: FloatArray
    mach: FloatArray
    dynamic_pressure: FloatArray
    latitude: FloatArray
    longitude: FloatArray

    def to_model(self) -> GhostSeries:
        return GhostSeries(
            t=_round(self.t, 3),
            altitude=_round(self.altitude, 2),
            vz=_round(self.vz, 3),
            speed=_round(self.speed, 3),
            mach=_round(self.mach, 4),
            dynamic_pressure=_round(self.dynamic_pressure, 1),
            latitude=_round(self.latitude, 7),
            longitude=_round(self.longitude, 7),
        )


def _round(values: FloatArray, digits: int) -> list[float]:
    return [float(v) for v in np.round(values, digits)]


def time_grid(apogee_time: float, t_final: float) -> FloatArray:
    """0.05 s to apogee (apogee time included exactly), then 0.5 s to the end."""
    ascent = np.arange(0.0, apogee_time, ASCENT_STEP_S)
    descent = np.arange(apogee_time, t_final, DESCENT_STEP_S)
    grid = np.concatenate((ascent, descent, [t_final]))
    return np.unique(grid)


def sample(flight: Any) -> GhostArrays:
    t = time_grid(float(flight.apogee_time), float(flight.t_final))

    def at(attr: str) -> FloatArray:
        return np.asarray(getattr(flight, attr).get_value(t), dtype=np.float64)

    return GhostArrays(
        t=t,
        altitude=at("altitude"),
        vz=at("vz"),
        speed=at("speed"),
        mach=at("mach_number"),
        dynamic_pressure=at("dynamic_pressure"),
        latitude=at("latitude"),
        longitude=at("longitude"),
    )


def first_crossing(t: FloatArray, y: FloatArray, level: float) -> float | None:
    """Linear-interpolated time where y first rises through `level`."""
    above = np.nonzero(y >= level)[0]
    if above.size == 0:
        return None
    i = int(above[0])
    if i == 0:
        return float(t[0])
    t0, t1, y0, y1 = t[i - 1], t[i], y[i - 1], y[i]
    return float(t0 + (level - y0) * (t1 - t0) / (y1 - y0))


def apogee_agl(flight: Any) -> float:
    return float(flight.apogee - flight.env.elevation)


def events(flight: Any, ghost: GhostArrays) -> list[Event]:
    out = [
        Event(
            name="Rail exit",
            t=round(float(flight.out_of_rail_time), 3),
            source="ghost",
            detail="Leaves the launch rail",
        ),
        Event(
            name="Burnout",
            t=round(float(flight.rocket.motor.burn_out_time), 3),
            source="ghost",
            detail="Motor burn ends",
        ),
        Event(
            name="Max-Q",
            t=round(float(flight.max_dynamic_pressure_time), 3),
            source="ghost",
            detail="Peak dynamic pressure",
        ),
    ]
    mach1 = first_crossing(ghost.t, ghost.mach, 1.0)
    if mach1 is not None:
        out.append(
            Event(name="Mach 1", t=round(mach1, 3), source="ghost", detail="Ghost goes supersonic")
        )
    out.append(
        Event(
            name="Apogee",
            t=round(float(flight.apogee_time), 3),
            source="ghost",
            detail="Ghost apogee",
        )
    )
    for t_event, parachute in flight.parachute_events:
        out.append(
            Event(
                name=f"{parachute.name} deploy",
                t=round(float(t_event), 3),
                source="ghost",
                detail=f"Trigger: {_trigger_text(parachute.trigger)}",
            )
        )
    return sorted(out, key=lambda e: e.t)


def _trigger_text(trigger: object) -> str:
    if isinstance(trigger, str):
        return trigger
    if isinstance(trigger, int | float):
        return f"{trigger:g} m AGL"
    return "custom function"
