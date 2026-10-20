"""NASA OMNI2 hourly space-weather indices (NASA GSFC Space Physics Data Facility).

Source: https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_YYYY.dat,
format per omni2.text in the same directory. Words used (1-based):
1 year, 2 day of year, 3 hour, 39 Kp ×10, 41 Dst (nT), 50 ap (nT), 51 F10.7 (sfu).
Missing values are the documented fill numbers and become None, never zero.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from asteria.provenance import sha256_file

OMNI_BASE = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni"
WORDS = 55
_KP_FILL, _DST_FILL, _AP_FILL, _F107_FILL = 99, 99999, 999, 999.9


@dataclass(frozen=True)
class Hour:
    time: datetime  # start of the hour, UTC
    kp: float | None
    dst_nt: int | None
    ap_nt: int | None
    f107_sfu: float | None


@dataclass(frozen=True)
class OmniFile:
    url: str
    path: Path
    sha256: str
    downloaded_at: str


def parse_line(line: str) -> Hour:
    words = line.split()
    if len(words) != WORDS:
        raise ValueError(f"OMNI2 record has {len(words)} words, expected {WORDS}: {line[:60]!r}")
    year, doy, hour = int(words[0]), int(words[1]), int(words[2])
    time = datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=doy - 1, hours=hour)
    kp10, dst, ap, f107 = int(words[38]), int(words[40]), int(words[49]), float(words[50])
    return Hour(
        time=time,
        kp=None if kp10 == _KP_FILL else kp10 / 10.0,
        dst_nt=None if dst == _DST_FILL else dst,
        ap_nt=None if ap == _AP_FILL else ap,
        f107_sfu=None if f107 == _F107_FILL else f107,
    )


def parse(lines: Iterable[str]) -> list[Hour]:
    return [parse_line(line) for line in lines if line.strip()]


def fetch_year(cache: Path, year: int) -> OmniFile:
    """Download omni2_<year>.dat once into `cache`; reuse it after that."""
    url = f"{OMNI_BASE}/omni2_{year}.dat"
    path = cache / f"omni2_{year}.dat"
    meta = cache / f"omni2_{year}.json"
    if not path.is_file() or not meta.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".partial")
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
            out.write(response.read())
        tmp.replace(path)
        stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
        meta.write_text(json.dumps({"url": url, "downloaded_at": stamp}), encoding="utf-8")
    info = json.loads(meta.read_text(encoding="utf-8"))
    return OmniFile(
        url=url, path=path, sha256=sha256_file(path), downloaded_at=info["downloaded_at"]
    )


def load(files: Sequence[OmniFile]) -> list[Hour]:
    hours: list[Hour] = []
    for f in files:
        hours.extend(parse(f.path.read_text(encoding="ascii").splitlines()))
    return sorted(hours, key=lambda h: h.time)


def window(hours: Sequence[Hour], start: datetime, end: datetime) -> list[Hour]:
    """Hours [t, t+1h) that overlap [start, end) by a positive amount of time.

    An hour that starts exactly at `end` is not inside the window (it adds
    zero time); before this rule existed, a quiet window ending at midnight
    picked up the next day's first hour.
    """
    return [h for h in hours if h.time + timedelta(hours=1) > start and h.time < end]


def max_kp(hours: Sequence[Hour], start: datetime, end: datetime) -> float | None:
    values = [h.kp for h in window(hours, start, end) if h.kp is not None]
    return max(values) if values else None


def quiet_window(
    hours: Sequence[Hour], before: datetime, days: float, kp_limit: float
) -> tuple[datetime, datetime] | None:
    """Latest window of `days` ending at or before `before` with every hourly Kp ≤ limit.

    Windows start on whole hours. A window with any missing Kp hour does not count.
    """
    span = timedelta(days=days)
    start = (before - span).replace(minute=0, second=0, microsecond=0)
    earliest = hours[0].time if hours else before
    by_time = {h.time: h for h in hours}
    while start >= earliest:
        end = start + span
        ok = True
        t = start
        while t < end:
            h = by_time.get(t)
            if h is None or h.kp is None or h.kp > kp_limit:
                ok = False
                break
            t += timedelta(hours=1)
        if ok:
            return start, end
        start -= timedelta(hours=1)
    return None
