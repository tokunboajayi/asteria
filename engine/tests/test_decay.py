"""Orbit-decay density: fits, maneuver splits, the B-cancelling ratio."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from asteria.orbits import decay, ghost

T0 = datetime(2024, 4, 11, tzinfo=UTC)


class _Sat:
    """Stands in for sgp4's Satrec: only what ElementSet's altitude needs."""

    def __init__(self, a_km: float) -> None:
        n_rad_s = math.sqrt(ghost.MU_KM3_S2 / a_km**3)
        self.no_kozai = n_rad_s * 60.0


def sets(points: list[tuple[float, float]]) -> list[ghost.ElementSet]:
    """(days after T0, semi-major axis km) -> element sets."""
    return [
        ghost.ElementSet(25544, T0 + timedelta(days=d), "", "", _Sat(a))  # type: ignore[arg-type]
        for d, a in points
    ]


def test_linear_fit_recovers_slope_and_zero_error_on_exact_line() -> None:
    slope, err = decay.linear_fit([0, 1, 2, 3], [10, 8, 6, 4])
    assert slope == pytest.approx(-2.0) and err == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        decay.linear_fit([0, 1], [1, 2])


def test_semi_major_axis_round_trips_through_mean_motion() -> None:
    (es,) = sets([(0, 6790.0)])
    assert es.semi_major_axis_km == pytest.approx(6790.0, rel=1e-9)


def test_runs_split_at_maneuvers() -> None:
    s = sets([(0, 6790), (0.3, 6789.9), (0.6, 6790.4), (0.9, 6790.3)])
    r = decay.runs(s, [s[2].epoch])
    assert [len(x) for x in r] == [2, 2]


def test_ratio_of_decay_rates_is_the_density_ratio_and_b_cancels() -> None:
    # Quiet: 60 m/day. Storm day: 180 m/day, same B: density x3 (a barely changes).
    quiet = sets([(d / 4, 6790.0 - 0.060 * d / 4) for d in range(13)])
    storm = sets([(30 + d / 4, 6789.0 - 0.180 * d / 4) for d in range(5)])
    q = decay.fit_window(quiet, [], T0, T0 + timedelta(days=4), 5, 2.0)
    f = decay.fit_window(storm, [], T0 + timedelta(days=30), T0 + timedelta(days=31), 3, 0.5)
    assert q is not None and f is not None
    r, e = decay.ratio_err(f, q)
    assert r == pytest.approx(3.0 * math.sqrt(q.mean_a_km / f.mean_a_km), rel=1e-9)
    assert e == pytest.approx(0.0, abs=1e-9)


def test_fit_window_refuses_short_or_sparse_coverage() -> None:
    s = sets([(0, 6790), (0.1, 6789.99), (0.2, 6789.98)])
    assert decay.fit_window(s, [], T0, T0 + timedelta(days=1), 3, 0.5) is None
    assert decay.fit_window(s[:2], [], T0, T0 + timedelta(days=1), 3, 0.0) is None


def test_fit_window_uses_the_longest_maneuver_free_run() -> None:
    s = sets([(0, 6790), (0.2, 6789.98), (0.4, 6789.96), (0.5, 6790.5), (0.7, 6790.48)])
    f = decay.fit_window(s, [s[3].epoch], T0, T0 + timedelta(days=1), 2, 0.1)
    assert f is not None and f.n == 3 and f.slope_km_day == pytest.approx(-0.1)
