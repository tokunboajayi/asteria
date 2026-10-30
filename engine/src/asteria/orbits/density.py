"""Modelled thermospheric density along each satellite's real orbit (NRLMSIS 2.1).

What is computed
----------------
* Positions: SGP4 from the latest real element set at each instant (see ephemeris).
* Model: NRLMSIS 2.1 (pymsis), storm-time ap mode (the full 3-hour ap history).
* Indices: NASA OMNI2 only. Daily F10.7 of the previous day; the 81-day centred
  F10.7 mean; 3-hour ap and the daily Ap built from it. All indices are passed in
  explicitly, so pymsis never downloads its own.
* Counterfactual: the same positions, times and F10.7, with every ap value set to
  the mean daily Ap of the storm-free quiet window. ratio = real / counterfactual
  isolates what the storm's geomagnetic heating did to density at that satellite.
* Orbit average: each hourly value is the mean of samples within half an orbital
  period either side, so it does not swing with local time around one orbit.

This is a model output, not a measurement. It is shown beside the measured
in-track gaps, never in place of them.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np

from asteria.artifacts import IntegrityError
from asteria.models import ObjectDensity
from asteria.orbits import ephemeris, ghost, spaceweather


@dataclass(frozen=True)
class MsisModel:
    key: str
    version: float  # pymsis version argument
    name: str
    licence: str


MODELS = {
    "nrlmsis-2.1": MsisModel(
        "nrlmsis-2.1",
        2.1,
        "NRLMSIS 2.1 (pymsis), storm-time ap mode",
        "NRL MSIS2 licence: academic, non-commercial use only. Not for commercial deployments.",
    ),
    "nrlmsise-00": MsisModel(
        "nrlmsise-00",
        0,
        "NRLMSISE-00 (pymsis), storm-time ap mode",
        "U.S. Government work, believed public domain; note the pymsis package also ships "
        "MSIS2 code under NRL's non-commercial licence.",
    ),
}
SETTING = "ASTERIA_DENSITY_MODEL"


def configured() -> MsisModel | None:
    """The model chosen in settings, or None (the default: measured density only)."""
    from asteria.config import setting

    key = setting(SETTING).strip().lower()
    if not key or key == "none":
        return None
    if key not in MODELS:
        raise ValueError(f"{SETTING}={key!r}: choose one of {', '.join(MODELS)} or leave empty")
    try:
        import pymsis  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            f"{SETTING}={key} needs the optional model extra: cd engine; uv sync --extra model"
        ) from exc
    return MODELS[key]


SAMPLE_STEP_S = 600.0
F107A_DAYS = 81
F107A_MIN_DAYS = 70  # of 81; fewer and the centred mean is not trusted
METHOD = (
    "Mass density from the chosen NRLMSIS version at each satellite's SGP4 position "
    "every 10 minutes, "
    "orbit-averaged hourly, with NASA OMNI2 F10.7 (previous day and 81-day centred mean) "
    "and 3-hour ap. Counterfactual: same positions and F10.7, ap held at the quiet "
    "window's mean daily Ap."
)
CAVEATS = [
    "Modelled, not measured: NRLMSIS is an empirical climatology; compare it with the "
    "measured ratios (orbit decay, GRACE-FO accelerometer).",
    "Positions come from element sets, which already absorb the storm's real drag.",
]


def _day(t: datetime) -> date:
    return t.astimezone(UTC).date()


class Indices:
    """OMNI2 hours turned into the inputs NRLMSIS expects."""

    def __init__(self, hours: Sequence[spaceweather.Hour]) -> None:
        f107_by_day: dict[date, list[float]] = {}
        self._ap: dict[datetime, float] = {}
        for h in hours:
            if h.f107_sfu is not None:
                f107_by_day.setdefault(_day(h.time), []).append(h.f107_sfu)
            if h.ap_nt is not None and h.time.hour % 3 == 0:
                self._ap[h.time] = float(h.ap_nt)
        self._f107 = {d: statistics.fmean(v) for d, v in f107_by_day.items()}

    def f107_previous_day(self, t: datetime) -> float:
        d = _day(t) - timedelta(days=1)
        if d not in self._f107:
            raise IntegrityError(f"OMNI has no F10.7 for {d}")
        return self._f107[d]

    def f107_81day(self, t: datetime) -> float:
        centre = _day(t)
        half = F107A_DAYS // 2
        values = [
            self._f107[centre + timedelta(days=k)]
            for k in range(-half, half + 1)
            if centre + timedelta(days=k) in self._f107
        ]
        if len(values) < F107A_MIN_DAYS:
            raise IntegrityError(
                f"only {len(values)} of {F107A_DAYS} days of F10.7 around {centre}"
            )
        return statistics.fmean(values)

    def ap3(self, t: datetime) -> float:
        """3-hour ap of the block containing `t`."""
        block = t.replace(hour=t.hour - t.hour % 3, minute=0, second=0, microsecond=0)
        if block not in self._ap:
            raise IntegrityError(f"OMNI has no ap for {block.isoformat()}")
        return self._ap[block]

    def daily_ap(self, d: date) -> float:
        start = datetime(d.year, d.month, d.day, tzinfo=UTC)
        return statistics.fmean(self.ap3(start + timedelta(hours=3 * k)) for k in range(8))

    def ap_vector(self, t: datetime) -> list[float]:
        """The seven ap inputs NRLMSIS uses in storm-time mode (see pymsis docs)."""

        def back(hours: int) -> float:
            return self.ap3(t - timedelta(hours=hours))

        return [
            self.daily_ap(_day(t)),
            back(0),
            back(3),
            back(6),
            back(9),
            statistics.fmean(back(h) for h in range(12, 34, 3)),
            statistics.fmean(back(h) for h in range(36, 58, 3)),
        ]

    def quiet_ap(self, start: datetime, end: datetime) -> float:
        days = []
        d = _day(start)
        while d <= _day(end):
            days.append(self.daily_ap(d))
            d += timedelta(days=1)
        return statistics.fmean(days)


def _msis(
    model: MsisModel,
    when: Sequence[datetime],
    lat: Sequence[float],
    lon: Sequence[float],
    alt: Sequence[float],
    f107: Sequence[float],
    f107a: Sequence[float],
    aps: Sequence[Sequence[float]],
) -> np.ndarray:
    from pymsis import msis

    dates = np.array([np.datetime64(t.replace(tzinfo=None), "s") for t in when])
    out = msis.calculate(
        dates,
        np.asarray(lon),
        np.asarray(lat),
        np.asarray(alt),
        f107s=np.asarray(f107),
        f107as=np.asarray(f107a),
        aps=np.asarray(aps),
        version=model.version,
        geomagnetic_activity=-1,
    )
    rho = np.asarray(out[..., msis.Variable.MASS_DENSITY], dtype=np.float64).reshape(-1)
    if not np.all(np.isfinite(rho)) or np.any(rho <= 0):
        raise IntegrityError("NRLMSIS returned a non-positive or non-finite density")
    return rho


def orbit_average(
    t_s: np.ndarray, values: np.ndarray, centres_s: np.ndarray, period_s: float
) -> np.ndarray:
    """Mean of `values` within ±period/2 of each centre (needs ≥ 3 samples)."""
    out = np.empty(centres_s.size)
    for i, c in enumerate(centres_s):
        inside = np.abs(t_s - c) <= period_s / 2
        if int(inside.sum()) < 3:
            raise IntegrityError("fewer than 3 density samples within half an orbit")
        out[i] = float(values[inside].mean())
    return out


def positions(
    sets: Sequence[ghost.ElementSet], samples: Sequence[datetime]
) -> tuple[list[float], list[float], list[float]]:
    """Geodetic lat, lon, height (km) from the latest element set at each sample."""
    lat, lon, alt = [], [], []
    for t in samples:
        r, _ = ghost.state(ephemeris.latest_at(sets, t), t)
        a, b, c = ghost.geodetic(r, t)
        lat.append(a)
        lon.append(b)
        alt.append(c)
    return lat, lon, alt


def mean_density(
    model: MsisModel,
    sets: Sequence[ghost.ElementSet],
    indices: Indices,
    start: datetime,
    end: datetime,
) -> float:
    """NRLMSIS 2.1 mass density averaged along the real orbit over [start, end], real indices."""
    samples = ephemeris.times(start, end, SAMPLE_STEP_S)
    lat, lon, alt = positions(sets, samples)
    rho = _msis(
        model,
        samples,
        lat,
        lon,
        alt,
        [indices.f107_previous_day(t) for t in samples],
        [indices.f107_81day(t) for t in samples],
        [indices.ap_vector(t) for t in samples],
    )
    return float(rho.mean())


def object_density(
    model: MsisModel,
    norad_id: int,
    name: str,
    sets: Sequence[ghost.ElementSet],
    indices: Indices,
    quiet_ap: float,
    start: datetime,
    end: datetime,
    iso: Callable[[datetime], str],
) -> ObjectDensity:
    samples = ephemeris.times(start, end, SAMPLE_STEP_S)
    lat, lon, alt = positions(sets, samples)
    f107 = [indices.f107_previous_day(t) for t in samples]
    f107a = [indices.f107_81day(t) for t in samples]
    real_ap = [indices.ap_vector(t) for t in samples]
    quiet = [[quiet_ap] * 7 for _ in samples]
    rho = _msis(model, samples, lat, lon, alt, f107, f107a, real_ap)
    rho_q = _msis(model, samples, lat, lon, alt, f107, f107a, quiet)

    period_s = ephemeris.period_min(ephemeris.latest_at(sets, start)) * 60.0
    t0 = samples[0]
    t_s = np.array([(t - t0).total_seconds() for t in samples])
    first = t0.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    hours = [
        h
        for h in ephemeris.times(first, end, 3600.0)
        if (h - t0).total_seconds() >= period_s / 2 and (end - h).total_seconds() >= period_s / 2
    ]
    centres = np.array([(h - t0).total_seconds() for h in hours])
    avg = orbit_average(t_s, rho, centres, period_s)
    avg_q = orbit_average(t_s, rho_q, centres, period_s)
    ratio = avg / avg_q
    k = int(np.argmax(ratio))
    return ObjectDensity(
        norad_id=norad_id,
        name=name,
        mean_altitude_km=round(float(np.mean(alt)), 1),
        times=[iso(h) for h in hours],
        density_kg_m3=[float(f"{v:.4e}") for v in avg],
        quiet_density_kg_m3=[float(f"{v:.4e}") for v in avg_q],
        ratio=[round(float(v), 4) for v in ratio],
        peak_ratio=round(float(ratio[k]), 3),
        peak_time=iso(hours[k]),
    )
