"""ERA5 pressure levels from the Copernicus Climate Data Store (free account, CC-BY 4.0).

Same box, levels and variables as RocketPy's spaceport_america_pressure_levels_2023_hourly.nc.
Credentials: CDSAPI_URL and CDSAPI_KEY from the environment or the settings files; the account
must have accepted the ERA5 pressure-level licence on the CDS website. Never printed.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from asteria.config import setting

DATASET = "reanalysis-era5-pressure-levels"
LEVELS = (
    1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400,
    450, 500, 550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000,
)  # fmt: skip
# North, West, South, East: the notebook file's 0.25-degree grid.
SPACEPORT_AMERICA_AREA = (36.75, -108.875, 29.0, -105.125)


def path_for(cache: Path, day: date) -> Path:
    return cache / f"spaceport_america_era5_pl_{day.isoformat()}.nc"


def request(day: date) -> dict[str, object]:
    return {
        "product_type": ["reanalysis"],
        "variable": ["geopotential", "temperature", "u_component_of_wind", "v_component_of_wind"],
        "pressure_level": [str(x) for x in LEVELS],
        "year": [f"{day.year}"],
        "month": [f"{day.month:02d}"],
        "day": [f"{day.day:02d}"],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": list(SPACEPORT_AMERICA_AREA),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def fetch(cache: Path, day: date) -> Path:
    out = path_for(cache, day)
    if out.is_file():
        return out
    import cdsapi

    for name in ("CDSAPI_URL", "CDSAPI_KEY"):
        value = setting(name)
        if not value:
            raise RuntimeError(f"{name} is not set (environment or .env.local / .env)")
        os.environ.setdefault(name, value)
    cache.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    cdsapi.Client(quiet=True).retrieve(DATASET, request(day), str(tmp))
    tmp.replace(out)
    return out
