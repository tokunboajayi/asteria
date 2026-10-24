"""What Storm Ghost studies, and the rules it uses — fixed before any orbit data was seen.

Pre-registered 2026-10-20, before the first Space-Track download. Changing any
rule here after seeing results must be recorded in gan-harness/spec.md (F7)
with the reason, the way the Rockets rules record their revisions.

Objects
-------
A hand-picked list (not a random sample): well-known, continuously tracked
low-Earth-orbit objects spanning roughly 380–830 km, all in orbit through
2024. Catalog numbers were checked against CelesTrak's active catalog on
2026-10-20 (16,767 objects): every name below matched its number.

Storm
-----
The 10–11 May 2024 geomagnetic storm (the "Gannon" storm), the strongest in
two decades. NASA OMNI hourly Kp reaches 9.0 at 2024-05-11 00:00 UTC and Dst
reaches −395 nT at 03:00 UTC (checked against omni2_2024.dat on 2026-10-20).

Rules
-----
* One element set per epoch: Space-Track sometimes re-issues a fit for the same
  epoch; only the latest issue (``CREATION_DATE``, then ``GP_ID``) is used, the
  way Space-Track's own current catalog supersedes it.
* Ghost: SGP4 from the last element set with epoch before ``STORM_ONSET``.
* Tracked: every later element set within ``FOLLOW_DAYS``, evaluated by SGP4 at
  its own epoch (a tracking-based orbit fit, not a direct measurement).
* Gap: tracked − ghost position in the ghost's radial / in-track / cross-track
  frame, km.
* Maneuvers: drag only ever lowers an orbit, so a rise in mean semi-major axis
  of more than ``MANEUVER_RISE_M`` between consecutive element sets marks a
  maneuver; a ghost is never compared across one (its gaps stop there).
* Quiet baseline: the same procedure from the latest ``FOLLOW_DAYS``-long
  window before the storm in which hourly Kp never exceeds ``QUIET_MAX_KP``,
  so storm gaps can be compared with what quiet days produce.
* Gap map: x = the highest hourly Kp between the ghost's epoch and the
  tracked epoch; y = the object's mean altitude at the ghost epoch; value =
  in-track gap per day elapsed (km/day). A cell needs ≥ 2 objects to be charted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class OrbitObject:
    norad_id: int
    name: str
    note: str


OBJECTS: tuple[OrbitObject, ...] = (
    OrbitObject(25544, "ISS (ZARYA)", "Crewed station; reboosts are flagged as maneuvers."),
    OrbitObject(48274, "CSS (TIANHE)", "Crewed station; reboosts are flagged as maneuvers."),
    OrbitObject(20580, "HST", "Hubble Space Telescope; no propulsion."),
    OrbitObject(43476, "GRACE-FO 1", "Gravity mission; low, drag-sensitive orbit."),
    OrbitObject(39452, "SWARM A", "ESA magnetic-field mission."),
    OrbitObject(43613, "ICESAT-2", "Laser altimetry mission."),
    OrbitObject(25994, "TERRA", "Earth observation, ~700 km."),
    OrbitObject(27424, "AQUA", "Earth observation, ~700 km."),
    OrbitObject(39084, "LANDSAT 8", "Earth observation, ~700 km."),
    OrbitObject(49260, "LANDSAT 9", "Earth observation, ~700 km."),
    OrbitObject(40697, "SENTINEL-2A", "Earth observation, ~790 km."),
    OrbitObject(43013, "NOAA 20 (JPSS-1)", "Weather satellite, ~830 km."),
)

STORM_NAME = "10–11 May 2024 geomagnetic storm"
STORM_ONSET = datetime(2024, 5, 10, 17, 0, tzinfo=UTC)
FOLLOW_DAYS = 5.0
MANEUVER_RISE_M = 200.0
QUIET_MAX_KP = 3.0
MIN_OBJECTS_PER_CELL = 2

# How much history to request: the quiet baseline is searched up to this far before onset.
HISTORY_LOOKBACK_DAYS = 60.0

KP_EDGES = [float(k) for k in range(10)]  # 0..9; Kp 9.0 falls in the top cell
ALT_EDGES = [float(a) for a in range(350, 901, 50)]  # km


def by_id(norad_id: int) -> OrbitObject:
    for obj in OBJECTS:
        if obj.norad_id == norad_id:
            return obj
    raise KeyError(norad_id)
