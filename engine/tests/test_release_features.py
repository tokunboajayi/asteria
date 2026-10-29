"""Fleet band, NRLMSIS inputs, SGP4 ephemeris and CCSDS OEM: the rebuilt features."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from asteria.artifacts import IntegrityError
from asteria.export import oem
from asteria.orbits import density, ephemeris, ghost, spaceweather
from asteria.rockets import band

# The ISS element set from the sgp4 package's documentation (a public test vector).
ISS_L1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
ISS_L2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
ISS_EPOCH = "2019-12-09T16:38:29.363424"


def _iss() -> ghost.ElementSet:
    return ghost.from_record(
        {"NORAD_CAT_ID": "25544", "EPOCH": ISS_EPOCH, "TLE_LINE1": ISS_L1, "TLE_LINE2": ISS_L2}
    )


# --- Fleet band --------------------------------------------------------------------
def test_held_out_range_uses_only_other_bracketed_flights() -> None:
    k = {"a": 0.7, "b": 1.0, "c": 1.2, "d": 1.5}
    ok = {"a": True, "b": True, "c": True, "d": False}
    r = band.held_out_range(k, ok, "a")
    assert r == band.KRange(1.0, 1.2, 2)
    assert band.held_out_range(k, ok, "b") == band.KRange(0.7, 1.2, 2)
    assert band.held_out_range({"a": 1.0, "b": 1.1}, {"a": True, "b": True}, "a") is None


def test_expected_coverage_is_the_exchangeable_rank_probability() -> None:
    assert band.expected_coverage(10) == pytest.approx(9 / 11)


def test_outside_intervals_close_when_reality_returns_inside() -> None:
    t = [0, 1, 2, 3, 4, 5, 6]
    low: list[float | None] = [0, 0, 0, 0, 0, 0, None]
    high: list[float | None] = [10, 10, 10, 10, 10, 10, None]
    real: list[float | None] = [5, 11, 12, 5, None, 20, 30]
    assert band.outside_intervals(t, real, low, high, (0, 6)) == [(1, 2), (5, 5)]
    assert band.outside_intervals(t, real, low, high, (3, 6)) == [(5, 5)]


def test_band_is_pointwise_min_max_and_apogee_test_uses_both_runs() -> None:
    fb = band.make(
        band.KRange(0.8, 1.2, 10),
        [0.0, 1.0],
        [5.0, 9.0],
        [7.0, None],
        apogee_a=1100.0,
        apogee_b=900.0,
        real_on_grid=[6.0, None],
        real_apogee_m=950.0,
        coast=(0.0, 1.0),
    )
    assert fb.altitude_low == [5.0, None] and fb.altitude_high == [7.0, None]
    assert (fb.apogee_low_m, fb.apogee_high_m) == (900.0, 1100.0)
    assert fb.real_apogee_inside and fb.real_outside == []


# --- NRLMSIS inputs from OMNI ----------------------------------------------------
def _hours(days: int, f107: float = 150.0, ap: int = 7) -> list[spaceweather.Hour]:
    t0 = datetime(2024, 4, 1, tzinfo=UTC)
    return [
        spaceweather.Hour(time=t0 + timedelta(hours=h), kp=1.0, dst_nt=0, ap_nt=ap, f107_sfu=f107)
        for h in range(24 * days)
    ]


def test_ap_vector_follows_the_msis_definition() -> None:
    hours = _hours(10)
    # Mark each 3-hour block with its own ap so offsets are visible.
    marked = [
        spaceweather.Hour(h.time, h.kp, h.dst_nt, h.time.hour // 3 + 10 * h.time.day, h.f107_sfu)
        for h in hours
    ]
    idx = density.Indices(marked)
    t = datetime(2024, 4, 8, 13, 30, tzinfo=UTC)
    v = idx.ap_vector(t)

    def ap(at: datetime) -> float:
        return (at.hour // 3) + 10 * at.day

    assert (
        v[1] == ap(t) and v[2] == ap(t - timedelta(hours=3)) and v[4] == ap(t - timedelta(hours=9))
    )
    assert v[5] == pytest.approx(sum(ap(t - timedelta(hours=h)) for h in range(12, 34, 3)) / 8)
    assert v[6] == pytest.approx(sum(ap(t - timedelta(hours=h)) for h in range(36, 58, 3)) / 8)
    assert v[0] == pytest.approx(sum(range(8)) / 8 + 80)


def test_f107_average_refuses_a_thin_window() -> None:
    idx = density.Indices(_hours(30))
    with pytest.raises(IntegrityError):
        idx.f107_81day(datetime(2024, 4, 15, tzinfo=UTC))
    assert density.Indices(_hours(90)).f107_81day(datetime(2024, 5, 15, tzinfo=UTC)) == 150.0


def test_orbit_average_needs_samples() -> None:
    import numpy as np

    t = np.arange(0.0, 6000.0, 600.0)
    v = np.ones_like(t)
    assert density.orbit_average(t, v, np.array([3000.0]), 5400.0)[0] == 1.0
    with pytest.raises(IntegrityError):
        density.orbit_average(t, v, np.array([3000.0]), 600.0)


# --- SGP4 ephemeris -----------------------------------------------------------------
def test_latest_at_picks_the_newest_set_not_after_the_time() -> None:
    a, b = _iss(), _iss()
    b = ghost.ElementSet(a.norad_id, a.epoch + timedelta(hours=6), a.line1, a.line2, a.satrec)
    assert ephemeris.latest_at([a, b], a.epoch + timedelta(hours=1)) is a
    assert ephemeris.latest_at([a, b], b.epoch) is b
    with pytest.raises(ValueError):
        ephemeris.latest_at([a, b], a.epoch - timedelta(seconds=1))


def test_iss_arc_is_one_revolution_at_iss_height() -> None:
    es = _iss()
    assert ephemeris.period_min(es) == pytest.approx(1440 / 15.50103472, rel=1e-3)
    pts = ephemeris.arc(es, es.epoch)
    assert len(pts) == int(ephemeris.period_min(es)) + 1
    assert all(400 < p.alt_km < 440 for p in pts)
    assert max(abs(p.lat) for p in pts) == pytest.approx(51.6, abs=0.3)


# --- CCSDS OEM ---------------------------------------------------------------------
def test_oem_rejects_repeated_epochs_and_drops_the_zone_designator() -> None:
    p = (7000.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        oem.format_oem(
            object_name="X",
            object_id="1",
            ref_frame="TEME",
            epochs=["2024-05-11T00:00:00Z", "2024-05-11T00:00:00Z"],
            positions_km=[p, p],
            velocities_km_s=None,
            comments=[],
        )
    text = oem.format_oem(
        object_name="X",
        object_id="1",
        ref_frame="TEME",
        epochs=["2024-05-11T00:00:00Z", "2024-05-11T00:05:00Z"],
        positions_km=[p, p],
        velocities_km_s=[(0.0, 7.5, 0.0), (0.0, 7.5, 0.0)],
        comments=["test"],
        creation=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert "START_TIME = 2024-05-11T00:00:00.000" in text and "Z" not in text.split("META_STOP")[1]
    assert "COMMENT test" in text


def test_geodetic_to_ecef_matches_wgs84_reference_points() -> None:
    x, y, z = oem.geodetic_to_ecef_km(0.0, 0.0, 0.0)
    assert (x, y, z) == pytest.approx((6378.137, 0.0, 0.0))
    x, y, z = oem.geodetic_to_ecef_km(90.0, 0.0, 0.0)
    assert z == pytest.approx(6356.752314, abs=1e-6) and math.hypot(x, y) < 1e-9
