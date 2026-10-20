from __future__ import annotations

import numpy as np
import pytest

from asteria.core import gapmap, nextbest
from asteria.models import CorrectionRow
from asteria.rockets import correction


def _samples(fid: str, xs: list[float], ys: list[float], vs: list[float]) -> gapmap.FlightSamples:
    return gapmap.FlightSamples(fid, np.array(xs), np.array(ys), np.array(vs))


def _map(samples, reach=()):  # type: ignore[no-untyped-def]
    return gapmap.build(
        samples, [0.0, 0.5, 1.0], [0.0, 100.0, 200.0],
        quantity="q", unit="u", coordinates="c", x_label="x", y_label="y", reach=reach,
    )


def test_gap_cells_need_two_flights_and_count_everything() -> None:
    gm = _map([
        _samples("a", [0.1, 0.1, 0.7], [10, 20, 150], [1.0, 3.0, 9.0]),
        _samples("b", [0.2], [50], [5.0]),
    ])
    cell = {(c.x_index, c.y_index): c for c in gm.cells}
    assert cell[(0, 0)].charted and cell[(0, 0)].mean == pytest.approx(3.0)
    assert cell[(0, 0)].n_flights == 2 and cell[(0, 0)].n_samples == 3
    assert not cell[(1, 1)].charted and cell[(1, 1)].mean is None
    assert gm.total_samples == 4


def test_top_edge_belongs_to_last_cell_and_outside_is_dropped() -> None:
    gm = _map([_samples("a", [1.0, 1.5], [200.0, 50.0], [1.0, 2.0])])
    assert gm.total_samples == 1
    assert {(c.x_index, c.y_index) for c in gm.cells if c.n_samples} == {(1, 1)}


def test_next_best_only_picks_reachable_cells() -> None:
    measured = [
        _samples("a", [0.1, 0.1], [10, 20], [1.0, 3.0]),
        _samples("b", [0.2, 0.2], [30, 40], [5.0, 7.0]),
    ]
    reach = [_samples("a", [0.1, 0.7], [10, 50], [0, 0])]  # ghosts reach (0,0) and (1,0)
    gm = _map(measured, reach)
    best = nextbest.recommend(gm, [nextbest.Candidate("a", "A", 0.8), nextbest.Candidate("b", "B", 0.4)])
    assert best.cells == [(1, 0)]  # reachable, uncharted; (1,1) and (0,1) are never flown
    assert best.target.mach == (0.5, 1.0)
    assert best.ghost_flights == ["a"]  # a's ghost flies there; its log never measured it
    assert best.nearest_flight.id == "a"


def test_held_out_k_never_sees_its_own_flight() -> None:
    k = {"a": 0.6, "b": 1.0, "c": 1.1, "d": 5.0}
    assert correction.held_out_k(k, "a") == pytest.approx(1.1)  # median(1.0, 1.1, 5.0)
    assert correction.held_out_k(k, "d") == pytest.approx(1.0)  # median(0.6, 1.0, 1.1)
    assert correction.held_out_k({"a": 2.0, "b": 2.0}, "a") == correction.K_CLIP[1]


def test_report_aggregates_from_rows() -> None:
    rows = [
        CorrectionRow(id=i, k_own=1, k_hat=1, real_apogee_m=1, ghost_apogee_m=1, corrected_apogee_m=1,
                      err_before_pct=b, err_after_pct=a)
        for i, b, a in [("x", 5.0, 2.0), ("y", -4.0, -6.0), ("z", 1.0, 1.0)]
    ]
    rep = correction.report(rows)
    assert rep.aggregate.median_abs_err_before_pct == 4.0
    assert rep.aggregate.median_abs_err_after_pct == 2.0
    assert (rep.aggregate.n_improved, rep.aggregate.n_worse) == (1, 1)


def test_scaled_drag_multiplies_and_restores() -> None:
    class Rocket:
        def __init__(self) -> None:
            self.power_on_drag_7d = lambda *a: 0.5
            self.power_off_drag_7d = lambda *a: 0.4

    r = Rocket()
    on = r.power_on_drag_7d
    with correction.scaled_drag(r, 1.2):
        assert r.power_on_drag_7d(0, 0, 0.5, 0, 0, 0, 0) == pytest.approx(0.6)
        assert r.power_off_drag_7d(0, 0, 0.5, 0, 0, 0, 0) == pytest.approx(0.48)
    assert r.power_on_drag_7d is on
