"""GRACE-FO accelerometer cleaning and the ERA5 request shape."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pytest

from asteria.orbits import accel
from asteria.sources import era5, gracefo

T0 = datetime(2024, 5, 11, tzinfo=UTC).timestamp()


def series(n: int, bad: slice | None = None, fill: slice | None = None) -> accel.Series:
    t = T0 + 10.0 * np.arange(n)
    rho = np.full(n, 2e-12)
    flag = np.zeros(n, dtype=np.int64)
    if bad is not None:
        flag[bad] = 1
    if fill is not None:
        rho[fill] = 0.999e33
    return accel.clean(t, rho, rho.copy(), flag, flag.copy())


def test_invalid_and_fill_samples_are_dropped() -> None:
    s = series(100, bad=slice(0, 10), fill=slice(10, 20))
    assert np.isnan(s.rho[:20]).all() and np.isfinite(s.rho[20:]).all()


def test_interval_needs_80_percent_valid_coverage() -> None:
    a = datetime.fromtimestamp(T0, UTC)
    b = datetime.fromtimestamp(T0 + 1000, UTC)
    assert accel.interval_mean(series(100, bad=slice(0, 15)), a, b) == pytest.approx(2e-12)
    assert accel.interval_mean(series(100, bad=slice(0, 25)), a, b) is None


def test_era5_request_matches_the_notebook_file_grid() -> None:
    r = era5.request(date(2022, 6, 24))
    assert r["area"] == [36.75, -108.875, 29.0, -105.125]
    assert len(r["pressure_level"]) == 37  # type: ignore[arg-type]
    assert r["year"] == ["2022"] and r["day"] == ["24"] and len(r["time"]) == 24  # type: ignore[arg-type]


def test_gracefo_file_name_matches_esa_naming() -> None:
    assert gracefo.name_for(date(2024, 5, 11)) == (
        "GF_OPER_DNS1ACC_2__20240511T000000_20240511T235959_0003.cdf"
    )
