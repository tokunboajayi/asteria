"""Dense SGP4 ephemerides and one-revolution arcs from real element sets.

Every state comes from SGP4 applied to a real Space-Track element set: the latest
one at or before that instant (the standard way to turn a TLE history into an
ephemeris). Nothing is interpolated between element sets or synthesised.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from asteria.models import GeoPoint, ObjectEphemeris, StateVector
from asteria.orbits import ghost

EPHEMERIS_STEP_S = 300.0
ARC_STEP_S = 60.0
SOURCE = (
    "SGP4 (WGS-72) applied to the latest Space-Track element set at or before each state; "
    "frame TEME, as SGP4 defines it."
)


def latest_at(sets: Sequence[ghost.ElementSet], when: datetime) -> ghost.ElementSet:
    """The latest element set with epoch <= `when` (`sets` sorted by epoch)."""
    i = bisect.bisect_right([s.epoch for s in sets], when)
    if i == 0:
        raise ValueError(f"no element set at or before {when.isoformat()}")
    return sets[i - 1]


def times(start: datetime, end: datetime, step_s: float) -> list[datetime]:
    n = int((end - start).total_seconds() // step_s)
    return [start + timedelta(seconds=k * step_s) for k in range(n + 1)]


def period_min(es: ghost.ElementSet) -> float:
    """Orbital period from the element set's (un-Kozai'd) mean motion, rad/min."""
    return 2.0 * math.pi / float(es.satrec.no_kozai)


def states(
    sets: Sequence[ghost.ElementSet], start: datetime, end: datetime, step_s: float
) -> list[tuple[datetime, ghost.Vec, ghost.Vec]]:
    out = []
    for t in times(start, end, step_s):
        r, v = ghost.state(latest_at(sets, t), t)
        out.append((t, r, v))
    return out


def arc(es: ghost.ElementSet, start: datetime) -> list[GeoPoint]:
    """One revolution of `es` from `start`, as geodetic points (WGS-84)."""
    end = start + timedelta(minutes=period_min(es))
    points = []
    for t in times(start, end, ARC_STEP_S):
        r, _ = ghost.state(es, t)
        lat, lon, alt = ghost.geodetic(r, t)
        points.append(GeoPoint(lat=round(lat, 4), lon=round(lon, 4), alt_km=round(alt, 3)))
    return points


def build_object(
    norad_id: int,
    name: str,
    sets: Sequence[ghost.ElementSet],
    base: ghost.ElementSet,
    start: datetime,
    end: datetime,
    arc_start: datetime,
    iso: Callable[[datetime], str],
) -> ObjectEphemeris:
    tracked = latest_at(sets, arc_start)
    return ObjectEphemeris(
        norad_id=norad_id,
        name=name,
        step_s=EPHEMERIS_STEP_S,
        source=SOURCE,
        states=[
            StateVector(
                epoch=iso(t),
                r_km=(round(float(r[0]), 6), round(float(r[1]), 6), round(float(r[2]), 6)),
                v_km_s=(round(float(v[0]), 9), round(float(v[1]), 9), round(float(v[2]), 9)),
            )
            for t, r, v in states(sets, start, end, EPHEMERIS_STEP_S)
        ],
        period_min=round(period_min(tracked), 4),
        arc_epoch=iso(arc_start),
        ghost_arc=arc(base, arc_start),
        tracked_arc=arc(tracked, arc_start),
    )
