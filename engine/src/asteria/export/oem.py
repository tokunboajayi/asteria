"""CCSDS Orbit Ephemeris Message (OEM, CCSDS 502.0-B-2) writer.

Only real states are written: SGP4 states from Space-Track element sets (TEME), or
RocketPy's ghost trajectory converted from WGS-84 geodetic to Earth-fixed
Cartesian. COMMENT lines say which, and what each epoch means.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from datetime import UTC, datetime

WGS84_A_KM = 6378.137
WGS84_F = 1 / 298.257223563


def ccsds_time(iso: str) -> str:
    """ISO-8601 UTC ('...Z' or '+00:00') to CCSDS ASCII time (no zone designator)."""
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC)
    return t.replace(tzinfo=None).isoformat(timespec="milliseconds")


def geodetic_to_ecef_km(lat_deg: float, lon_deg: float, h_km: float) -> tuple[float, float, float]:
    """WGS-84 geodetic latitude/longitude and ellipsoidal height to Earth-fixed x, y, z (km)."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    e2 = WGS84_F * (2 - WGS84_F)
    n = WGS84_A_KM / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    x = (n + h_km) * math.cos(lat) * math.cos(lon)
    y = (n + h_km) * math.cos(lat) * math.sin(lon)
    z = (n * (1 - e2) + h_km) * math.sin(lat)
    return x, y, z


def format_oem(
    *,
    object_name: str,
    object_id: str,
    ref_frame: str,
    epochs: Sequence[str],
    positions_km: Sequence[tuple[float, float, float]],
    velocities_km_s: Sequence[tuple[float, float, float]] | None,
    comments: Sequence[str],
    creation: datetime | None = None,
) -> str:
    if not epochs:
        raise ValueError("an OEM needs at least one state")
    if len(positions_km) != len(epochs) or (
        velocities_km_s is not None and len(velocities_km_s) != len(epochs)
    ):
        raise ValueError("epochs, positions and velocities differ in length")
    times = [ccsds_time(e) for e in epochs]
    if any(b <= a for a, b in itertools.pairwise(times)):
        raise ValueError("OEM epochs must strictly increase")
    created = (creation or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    lines = [
        "CCSDS_OEM_VERS = 2.0",
        f"CREATION_DATE = {created.isoformat(timespec='seconds')}",
        "ORIGINATOR = ASTERIA",
        "",
        "META_START",
        f"OBJECT_NAME = {object_name}",
        f"OBJECT_ID = {object_id}",
        "CENTER_NAME = EARTH",
        f"REF_FRAME = {ref_frame}",
        "TIME_SYSTEM = UTC",
        f"START_TIME = {times[0]}",
        f"STOP_TIME = {times[-1]}",
        "META_STOP",
        "",
        *[f"COMMENT {c}" for c in comments],
    ]
    for i, (t, p) in enumerate(zip(times, positions_km, strict=True)):
        row = f"{t} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}"
        if velocities_km_s is not None:
            v = velocities_km_s[i]
            row += f" {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}"
        lines.append(row)
    return "\n".join(lines) + "\n"
