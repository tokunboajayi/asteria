from __future__ import annotations

import numpy as np
import pytest

from asteria.rockets import ghost, real


def _ghost(t: np.ndarray, alt: np.ndarray, vz: np.ndarray) -> ghost.GhostArrays:
    z = np.zeros_like(t)
    return ghost.GhostArrays(t, alt, vz, np.abs(vz), z + 0.5, z, z, z)


def test_time_grid_includes_apogee_exactly() -> None:
    grid = ghost.time_grid(10.123, 20.0)
    assert 10.123 in grid and grid[0] == 0 and grid[-1] == 20.0
    assert np.all(np.diff(grid) > 0)


def test_first_crossing_interpolates() -> None:
    t = np.array([0.0, 1.0, 2.0])
    assert ghost.first_crossing(t, np.array([0.0, 5.0, 15.0]), 10.0) == pytest.approx(1.5)
    assert ghost.first_crossing(t, np.array([0.0, 1.0, 2.0]), 10.0) is None


def test_derived_vz_recovers_a_known_derivative() -> None:
    t = np.arange(0, 20, 0.01)
    alt = 3.0 * t**2  # d/dt = 6 t
    vz = real.derive_vz(t, alt)
    inner = (t > 2) & (t < 18)
    assert np.max(np.abs(vz[inner] - 6 * t[inner])) < 1e-6


def test_liftoff_ignores_pad_noise() -> None:
    t = np.arange(0, 10, 0.1)
    alt = np.where(t < 5, 0.0, 30.0 * (t - 5) ** 2)
    alt[10] = 12.0  # a single pad spike above 10 m that is not followed by a climb
    assert real.real_liftoff(t, alt) == pytest.approx(5 + np.sqrt(10 / 30), abs=0.06)


def test_delta_is_null_outside_the_log_and_exact_inside() -> None:
    t = np.arange(0, 10, 0.05)
    g = _ghost(t, 10 * t, np.full_like(t, 10.0))
    rt = np.arange(2.0, 6.0, 0.1)
    r = real.RealArrays(rt, 10 * rt + 1.0, np.full_like(rt, 9.0), {})
    d = real.delta(g, r, shift=0.5, aligned=True)
    lo, hi = d.t.index(2.5), d.t.index(6.4)
    assert all(v is None for v in d.altitude[:lo]) and all(v is None for v in d.altitude[hi + 1 :])
    for k in range(lo, hi + 1):
        assert d.real_altitude[k] is not None
        assert d.altitude[k] == pytest.approx(d.real_altitude[k] - d.ghost_altitude[k], abs=1e-9)  # type: ignore[operator]
        assert d.vz[k] == pytest.approx(-1.0, abs=1e-9)


def test_decimation_keeps_ends_and_apogee() -> None:
    idx = real._decimation_index(10_000, 4321)
    assert idx[0] == 0 and idx[-1] == 9_999 and 4321 in idx
    assert idx.size <= real.MAX_UI_POINTS + 3
