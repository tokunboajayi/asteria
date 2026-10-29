"""SGP4 ghosts and their gap to later tracking, in the ghost's own frame.

Frames and units: SGP4 returns TEME position (km) and velocity (km/s). The gap
tracked − ghost is projected on the ghost's radial (R), in-track (I) and
cross-track (C) unit vectors at the same instant. A negative in-track gap
means the tracked object is behind the ghost (what extra drag does).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sgp4.api import WGS72, Satrec, jday

MU_KM3_S2 = 398600.8  # WGS-72, the constants SGP4 element sets are fitted with
EARTH_RADIUS_KM = 6378.135  # WGS-72 equatorial radius

Vec = NDArray[np.float64]


class PropagationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ElementSet:
    norad_id: int
    epoch: datetime
    line1: str
    line2: str
    satrec: Satrec

    @property
    def mean_altitude_km(self) -> float:
        """Mean semi-major axis minus Earth's radius (from the un-Kozai'd mean motion)."""
        n_rad_s = float(self.satrec.no_kozai) / 60.0
        a_km = math.cbrt(MU_KM3_S2 / n_rad_s**2)
        return a_km - EARTH_RADIUS_KM

    @property
    def semi_major_axis_km(self) -> float:
        return self.mean_altitude_km + EARTH_RADIUS_KM


def _epoch(text: str) -> datetime:
    t = datetime.fromisoformat(text.replace("Z", ""))
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def latest_issue_per_epoch(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per (object, epoch to the second): the latest issued, by CREATION_DATE
    then GP_ID.

    Space-Track re-publishes corrected fits under the same epoch, sometimes shifted by
    a fraction of a second. Keeping every copy
    would chart two gaps at one instant and count that instant twice in the gap map.
    """
    latest: dict[tuple[int, datetime], dict[str, Any]] = {}

    def issued(r: dict[str, Any]) -> tuple[datetime, int]:
        return _epoch(str(r["CREATION_DATE"])), int(r["GP_ID"])

    for r in records:
        key = (int(r["NORAD_CAT_ID"]), _epoch(str(r["EPOCH"])).replace(microsecond=0))
        if key not in latest or issued(r) > issued(latest[key]):
            latest[key] = r
    return list(latest.values())


def from_record(record: dict[str, Any]) -> ElementSet:
    """An element set from a Space-Track GP / GP_history JSON record."""
    line1, line2 = str(record["TLE_LINE1"]), str(record["TLE_LINE2"])
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    return ElementSet(
        norad_id=int(record["NORAD_CAT_ID"]),
        epoch=_epoch(str(record["EPOCH"])),
        line1=line1,
        line2=line2,
        satrec=sat,
    )


def state(es: ElementSet, when: datetime) -> tuple[Vec, Vec]:
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    err, r, v = es.satrec.sgp4(jd, fr)
    if err != 0:
        raise PropagationError(f"SGP4 error {err} for {es.norad_id} at {when.isoformat()}")
    return np.asarray(r, dtype=np.float64), np.asarray(v, dtype=np.float64)


def ric(r_ghost: Vec, v_ghost: Vec, r_tracked: Vec) -> tuple[float, float, float]:
    """(radial, in-track, cross-track) of r_tracked − r_ghost, km."""
    radial = r_ghost / np.linalg.norm(r_ghost)
    cross = np.cross(r_ghost, v_ghost)
    cross = cross / np.linalg.norm(cross)
    in_track = np.cross(cross, radial)
    d = r_tracked - r_ghost
    return float(d @ radial), float(d @ in_track), float(d @ cross)


def maneuver_epochs(sets: Sequence[ElementSet], rise_m: float) -> list[datetime]:
    """Epochs of element sets whose mean semi-major axis rose by more than `rise_m`."""
    out = []
    for prev, cur in itertools.pairwise(sets):
        if (cur.semi_major_axis_km - prev.semi_major_axis_km) * 1000.0 > rise_m:
            out.append(cur.epoch)
    return out


@dataclass(frozen=True)
class GapPoint:
    epoch: datetime
    days: float
    radial_km: float
    in_track_km: float
    cross_track_km: float
    ghost_lat: float
    ghost_lon: float
    ghost_alt_km: float
    tracked_lat: float
    tracked_lon: float
    tracked_alt_km: float


def base_set(sets: Sequence[ElementSet], before: datetime) -> ElementSet | None:
    earlier = [s for s in sets if s.epoch < before]
    return earlier[-1] if earlier else None


def gaps(
    sets: Sequence[ElementSet], base: ElementSet, follow: timedelta, rise_m: float
) -> tuple[list[GapPoint], datetime | None]:
    """Gap at every later element set within `follow`, stopping at the first maneuver.

    Returns the points and the epoch of the maneuver that stopped it (if any).
    """
    later = [s for s in sets if base.epoch < s.epoch <= base.epoch + follow]
    chain = [base, *later]
    stops = maneuver_epochs(chain, rise_m)
    stop = stops[0] if stops else None
    out: list[GapPoint] = []
    for s in later:
        if stop is not None and s.epoch >= stop:
            break
        r_g, v_g = state(base, s.epoch)
        r_t, _ = state(s, s.epoch)
        dr, di, dc = ric(r_g, v_g, r_t)
        g_lat, g_lon, g_alt = geodetic(r_g, s.epoch)
        t_lat, t_lon, t_alt = geodetic(r_t, s.epoch)
        out.append(
            GapPoint(
                epoch=s.epoch,
                days=(s.epoch - base.epoch).total_seconds() / 86400.0,
                radial_km=dr,
                in_track_km=di,
                cross_track_km=dc,
                ghost_lat=g_lat,
                ghost_lon=g_lon,
                ghost_alt_km=g_alt,
                tracked_lat=t_lat,
                tracked_lon=t_lon,
                tracked_alt_km=t_alt,
            )
        )
    return out, stop


# --- TEME → geodetic, for drawing on the globe -------------------------------
_WGS84_A = 6378.137
_WGS84_F = 1 / 298.257223563


def gmst_rad(when: datetime) -> float:
    """Greenwich mean sidereal time (IAU-82), radians."""
    jd, fr = jday(
        when.year,
        when.month,
        when.day,
        when.hour,
        when.minute,
        when.second + when.microsecond / 1e6,
    )
    t = ((jd - 2451545.0) + fr) / 36525.0
    seconds = (
        67310.54841 + (876600.0 * 3600.0 + 8640184.812866) * t + 0.093104 * t**2 - 6.2e-6 * t**3
    )
    return math.radians((seconds % 86400.0) / 240.0)


def geodetic(r_teme: Vec, when: datetime) -> tuple[float, float, float]:
    """Latitude (deg), longitude (deg), height above the WGS-84 ellipsoid (km).

    TEME is rotated to Earth-fixed by GMST only (polar motion and the small
    TEME/PEF offset are ignored: tens of metres, far below the gaps shown).
    """
    theta = gmst_rad(when)
    c, s = math.cos(theta), math.sin(theta)
    x = c * r_teme[0] + s * r_teme[1]
    y = -s * r_teme[0] + c * r_teme[1]
    z = float(r_teme[2])
    e2 = _WGS84_F * (2 - _WGS84_F)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(6):
        n = _WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + h)))
    n = _WGS84_A / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h
