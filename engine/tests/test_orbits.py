"""Storm Ghost: OMNI parsing, SGP4 ghost geometry, maneuver rule, Space-Track client."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sgp4.api import WGS72, Satrec

from asteria.orbits import catalog, ghost, spacetrack, spaceweather

DATA = Path(__file__).parent / "data"

# The ISS element set printed in the sgp4 package's own documentation (a real 2019 TLE).
ISS_L1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
ISS_L2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


# --- NASA OMNI ---------------------------------------------------------------
def test_omni_records_parse_to_the_storm_peak() -> None:
    hours = spaceweather.parse((DATA / "omni2_2024_day132_h00_h03.dat").read_text().splitlines())
    assert [h.time for h in hours] == [
        datetime(2024, 5, 11, 0, tzinfo=UTC),
        datetime(2024, 5, 11, 3, tzinfo=UTC),
    ]
    assert (hours[0].kp, hours[0].dst_nt, hours[0].ap_nt) == (9.0, -313, 400)
    assert (hours[1].kp, hours[1].dst_nt) == (8.3, -395)
    assert hours[0].f107_sfu == pytest.approx(218.0)


def test_omni_fill_values_become_none() -> None:
    line = (DATA / "omni2_2024_day132_h00_h03.dat").read_text().splitlines()[0].split()
    line[38], line[40], line[49], line[50] = "99", "99999", "999", "999.9"
    h = spaceweather.parse_line(" ".join(line))
    assert (h.kp, h.dst_nt, h.ap_nt, h.f107_sfu) == (None, None, None, None)


def test_omni_rejects_a_short_record() -> None:
    with pytest.raises(ValueError):
        spaceweather.parse_line("2024 132 0 2601")


def _TEST_ONLY_hours(kps: list[float | None], start: datetime) -> list[spaceweather.Hour]:
    return [
        spaceweather.Hour(start + timedelta(hours=i), kp, None, None, None)
        for i, kp in enumerate(kps)
    ]


def test_quiet_window_is_the_latest_all_quiet_span() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    kps: list[float | None] = [2.0] * 10 + [5.0] + [1.0] * 6 + [None] + [1.0] * 3
    hours = _TEST_ONLY_hours(kps, t0)
    found = spaceweather.quiet_window(hours, t0 + timedelta(hours=21), days=4 / 24, kp_limit=3.0)
    # Hours: 0-9 Kp 2, 10 Kp 5 (stormy), 11-16 Kp 1, 17 missing, 18-20 Kp 1. Every 4-hour window
    # starting at 14..17 touches the missing hour 17 (or runs past the data), so the latest
    # all-quiet window is hours 13-16.
    assert found == (t0 + timedelta(hours=13), t0 + timedelta(hours=17))


def test_max_kp_uses_overlapping_hours() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    hours = _TEST_ONLY_hours([1.0, 7.0, 2.0], t0)
    assert spaceweather.max_kp(hours, t0 + timedelta(minutes=90), t0 + timedelta(hours=2)) == 7.0
    assert (
        spaceweather.max_kp(
            hours, t0 + timedelta(hours=2, minutes=5), t0 + timedelta(hours=2, minutes=50)
        )
        == 2.0
    )


def test_hour_starting_exactly_at_the_end_is_outside_the_window() -> None:
    # Regression: a quiet window ending at midnight used to include the next day's 00:00 hour.
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    hours = _TEST_ONLY_hours([1.0, 1.0, 6.0], t0)
    assert spaceweather.max_kp(hours, t0, t0 + timedelta(hours=2)) == 1.0
    found = spaceweather.quiet_window(hours, t0 + timedelta(hours=2), days=2 / 24, kp_limit=3.0)
    assert found is not None
    assert spaceweather.max_kp(hours, *found) == 1.0


# --- SGP4 ghost ----------------------------------------------------------------
def test_record_gives_a_real_iss_orbit() -> None:
    es = ghost.from_record(
        {
            "NORAD_CAT_ID": "25544",
            "EPOCH": "2019-12-09T16:38:29.363424",
            "TLE_LINE1": ISS_L1,
            "TLE_LINE2": ISS_L2,
        }
    )
    assert es.norad_id == 25544
    assert 400 < es.mean_altitude_km < 430  # the ISS flew at ~420 km in Dec 2019
    r, v = ghost.state(es, es.epoch)
    assert 6700 < np.linalg.norm(r) < 6830 and 7.5 < np.linalg.norm(v) < 7.8


def test_ric_projects_onto_the_ghost_frame() -> None:
    r = np.array([7000.0, 0.0, 0.0])
    v = np.array([0.0, 7.5, 0.0])
    assert ghost.ric(r, v, r + np.array([1.0, 0, 0])) == pytest.approx((1.0, 0.0, 0.0))
    assert ghost.ric(r, v, r + np.array([0, -2.0, 0])) == pytest.approx((0.0, -2.0, 0.0))  # behind
    assert ghost.ric(r, v, r + np.array([0, 0, 3.0])) == pytest.approx((0.0, 0.0, 3.0))


def test_zero_gap_when_tracked_equals_ghost() -> None:
    es = ghost.from_record(
        {
            "NORAD_CAT_ID": "25544",
            "EPOCH": "2019-12-09T16:38:29.363424",
            "TLE_LINE1": ISS_L1,
            "TLE_LINE2": ISS_L2,
        }
    )
    same = ghost.ElementSet(25544, es.epoch + timedelta(hours=6), ISS_L1, ISS_L2, es.satrec)
    points, stop = ghost.gaps([es, same], es, timedelta(days=1), rise_m=200.0)
    assert stop is None and len(points) == 1
    assert (points[0].radial_km, points[0].in_track_km, points[0].cross_track_km) == pytest.approx(
        (0, 0, 0), abs=1e-9
    )


def _TEST_ONLY_set(epoch: datetime, mean_motion_rev_day: float) -> ghost.ElementSet:
    sat = Satrec()
    epoch_days = (epoch - datetime(1949, 12, 31, tzinfo=UTC)).total_seconds() / 86400.0
    n_rad_min = mean_motion_rev_day * 2 * math.pi / 1440.0
    sat.sgp4init(
        WGS72,
        "i",
        99999,
        epoch_days,
        0.0,
        0.0,
        0.0,
        0.001,
        0.0,
        math.radians(51.6),
        0.0,
        n_rad_min,
        0.0,
    )
    return ghost.ElementSet(99999, epoch, "", "", sat)


def test_maneuver_rule_flags_a_rise_and_stops_the_ghost() -> None:
    t0 = datetime(2024, 5, 1, tzinfo=UTC)
    # Mean motion falling = orbit rising. A drop from 15.5 to 15.45 rev/day raises a by ~15 km.
    sets = [
        _TEST_ONLY_set(t0, 15.50),
        _TEST_ONLY_set(t0 + timedelta(days=1), 15.50),
        _TEST_ONLY_set(t0 + timedelta(days=2), 15.45),
        _TEST_ONLY_set(t0 + timedelta(days=3), 15.45),
    ]
    assert ghost.maneuver_epochs(sets, 200.0) == [t0 + timedelta(days=2)]
    points, stop = ghost.gaps(sets, sets[0], timedelta(days=5), 200.0)
    assert stop == t0 + timedelta(days=2)
    assert [p.epoch for p in points] == [t0 + timedelta(days=1)]


def test_decay_is_not_a_maneuver() -> None:
    t0 = datetime(2024, 5, 1, tzinfo=UTC)
    sets = [_TEST_ONLY_set(t0 + timedelta(days=i), 15.50 + 0.01 * i) for i in range(4)]  # falling
    assert ghost.maneuver_epochs(sets, 200.0) == []


def test_geodetic_of_a_point_over_the_equator() -> None:
    when = datetime(2024, 5, 11, 0, tzinfo=UTC)
    theta = ghost.gmst_rad(when)
    r = np.array(
        [7000.0 * math.cos(theta), 7000.0 * math.sin(theta), 0.0]
    )  # on the Greenwich meridian
    lat, lon, h = ghost.geodetic(r, when)
    assert lat == pytest.approx(0.0, abs=1e-9)
    assert lon == pytest.approx(0.0, abs=1e-9)
    assert h == pytest.approx(7000.0 - 6378.137, abs=1e-6)


# --- Space-Track client -----------------------------------------------------------
def test_history_url_has_ids_and_window_and_no_credentials() -> None:
    url = spacetrack.history_url(
        [43013, 25544], datetime(2024, 3, 11, tzinfo=UTC), datetime(2024, 5, 16, tzinfo=UTC)
    )
    assert "/class/gp_history/NORAD_CAT_ID/25544,43013/EPOCH/2024-03-11--2024-05-16/" in url
    assert " " not in url and "password" not in url.lower()


def test_credentials_from_env_file_and_password_never_printed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)
    env = tmp_path / ".env.local"
    env.write_text(
        '# comment\nSPACETRACK_USER=aj@example.com\nSPACETRACK_PASSWORD="TEST_ONLY_secret"\n'
    )
    creds = spacetrack.credentials([env])
    assert creds.user == "aj@example.com" and creds.password == "TEST_ONLY_secret"
    assert "TEST_ONLY_secret" not in repr(creds)


def test_missing_credentials_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)
    with pytest.raises(spacetrack.CredentialsMissing):
        spacetrack.credentials([tmp_path / "absent.env"])


def test_a_blank_value_never_hides_a_saved_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SPACETRACK_USER", raising=False)
    monkeypatch.delenv("SPACETRACK_PASSWORD", raising=False)
    local, plain = tmp_path / ".env.local", tmp_path / ".env"
    local.write_text("SPACETRACK_USER=\nSPACETRACK_PASSWORD=\n")  # template left blank
    plain.write_text("SPACETRACK_USER=aj@example.com\nSPACETRACK_PASSWORD=TEST_ONLY_pw\n")
    creds = spacetrack.credentials([local, plain])
    assert creds.user == "aj@example.com" and creds.password == "TEST_ONLY_pw"


def test_a_reissued_epoch_keeps_only_the_latest_issue() -> None:
    def rec(gp_id: int, created: str, epoch: str = "2024-05-13T11:25:59.123456") -> dict[str, Any]:
        return {
            "NORAD_CAT_ID": "48274",
            "EPOCH": epoch,
            "CREATION_DATE": created,
            "GP_ID": str(gp_id),
        }

    older, newer = rec(10, "2024-05-13T15:00:00"), rec(9, "2024-05-13T19:00:00")
    tie_low, tie_high = rec(20, "2024-05-14T01:00:00"), rec(21, "2024-05-14T01:00:00")
    other = rec(5, "2024-05-12T00:00:00", epoch="2024-05-12T08:00:00")
    assert ghost.latest_issue_per_epoch([newer, older, other]) == [newer, other]
    assert ghost.latest_issue_per_epoch([tie_high, tie_low]) == [tie_high]


# --- Catalog ----------------------------------------------------------------------
def test_catalog_ids_are_unique_and_rules_fixed() -> None:
    ids = [o.norad_id for o in catalog.OBJECTS]
    assert len(ids) == len(set(ids)) == 12
    onset = catalog.STORM_ONSET
    assert onset == datetime(2024, 5, 10, 17, tzinfo=UTC)
    assert (catalog.FOLLOW_DAYS, catalog.MANEUVER_RISE_M, catalog.QUIET_MAX_KP) == (5.0, 200.0, 3.0)
