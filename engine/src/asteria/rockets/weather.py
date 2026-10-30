"""The ghost re-flown on the launch day's real weather.

RocketPy's example notebooks sometimes load reanalysis for a different date than
the flight (Prometheus: 2023-06-24 for a 2022-06-24 launch, because the repository
ships only a 2023 file). Here the notebook's Environment is copied and only two
things change: the date (the real liftoff, to the hour ERA5 provides) and the
reanalysis file (ERA5 pressure levels for that day, same box, levels and
variables). Everything else (site, rail, rocket, motor, drag) is the notebook's.

Gate: the same pipeline applied to an ERA5 download of the notebook's own date
must reproduce the notebook's apogee. If it does not, the download or the file
format changed the weather, and the build stops.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from asteria.artifacts import IntegrityError
from asteria.rockets.ghost import apogee_agl
from asteria.rockets.notebook import seed_rng

CONTROL_TOLERANCE_M = 1.0
ERA5_DICTIONARY = "ECMWF"  # RocketPy's mapping for the current CDS netCDF layout
SOURCE = "Copernicus Climate Change Service ERA5 hourly pressure levels (CC-BY 4.0)"


@dataclass(frozen=True)
class WeatherFile:
    path: Path
    when_utc: datetime

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def reflown(flight_kwargs: Mapping[str, Any], weather: WeatherFile, *, to_apogee: bool) -> Any:
    """The notebook's Flight with only the Environment's date and reanalysis file replaced."""
    from rocketpy import Flight

    kwargs = dict(flight_kwargs)
    env = copy.deepcopy(kwargs["environment"])
    # set_date reloads the reanalysis file the Environment points at, so point it at the new
    # file first: one load, on the new file, at the new date. Nothing else is touched.
    env.atmospheric_model_file = str(weather.path)
    env.atmospheric_model_dict = ERA5_DICTIONARY
    when = weather.when_utc
    env.set_date((when.year, when.month, when.day, when.hour), timezone="UTC")
    if env.atmospheric_model_type != "Reanalysis":
        raise IntegrityError(f"expected a Reanalysis atmosphere, got {env.atmospheric_model_type}")
    kwargs["environment"] = env
    if to_apogee:
        kwargs["terminate_on_apogee"] = True
    seed_rng()
    return Flight(**kwargs)


def check_control(
    flight_kwargs: Mapping[str, Any], control: WeatherFile, notebook_apogee: float
) -> float:
    """Re-fly on our download of the notebook's own date; it must match the notebook."""
    got = apogee_agl(reflown(flight_kwargs, control, to_apogee=True))
    if abs(got - notebook_apogee) > CONTROL_TOLERANCE_M:
        raise IntegrityError(
            f"ERA5 control: re-flown on a fresh download of the notebook's date gave {got:.2f} m, "
            f"notebook {notebook_apogee:.2f} m (tolerance {CONTROL_TOLERANCE_M:g} m)"
        )
    return got
