"""Event timing detective: pure detection rules on synthetic tracks.

Inputs here are TEST_ONLY_ shapes chosen to exercise one rule each; real flights
are checked by the build and the acceptance tests.
"""

import numpy as np

from asteria.rockets import events


def TEST_ONLY_track(t, altitude, axial=None):  # TEST_ONLY_: synthetic data
    t = np.asarray(t, dtype=float)
    altitude = np.asarray(altitude, dtype=float)
    vz = np.gradient(altitude, t)
    return events.Track(t, altitude, vz, None if axial is None else np.asarray(axial, float))


def test_thrust_end_is_the_sustained_zero_crossing_after_the_boost_peak() -> None:
    t = np.arange(0, 10, 0.1)
    axial = np.where(t < 3.0, 80.0, -20.0)  # thrust, then drag deceleration
    axial[(t > 0.95) & (t < 1.05)] = -5.0  # one-sample dip before the peak: ignored
    track = TEST_ONLY_track(t, t * 10, axial)
    end = events.thrust_end(track, liftoff_s=0.0)
    assert end is not None and 2.9 <= end <= 3.0


def test_thrust_end_needs_an_accelerometer() -> None:
    t = np.arange(0, 10, 0.1)
    assert events.thrust_end(TEST_ONLY_track(t, t * 10), liftoff_s=0.0) is None


def test_two_parachute_descent_is_split_where_the_rate_changes() -> None:
    t = np.arange(0, 200, 0.5)
    alt = np.where(t < 100, 3000 - 25 * t, 3000 - 25 * 100 - 6 * (t - 100))
    cp, why = events.descent_changepoint(TEST_ONLY_track(t, alt), apogee_s=0.0)
    assert cp is not None, why
    assert abs(cp.t - 100) <= 1.0
    assert round(cp.rate_before) == -25 and round(cp.rate_after) == -6


def test_a_single_steady_descent_is_not_split() -> None:
    t = np.arange(0, 200, 0.5)
    rng = np.random.default_rng(0)
    alt = 3000 - 8 * t + rng.normal(0, 1.0, t.size)
    cp, why = events.descent_changepoint(TEST_ONLY_track(t, alt), apogee_s=0.0)
    assert cp is None and why
    assert round(events.one_phase_rate(TEST_ONLY_track(t, alt), 0.0)) == -8


def test_real_altitude_is_withheld_near_mach_one_but_the_time_is_kept() -> None:
    t = np.arange(0, 10, 0.1)
    ghost = TEST_ONLY_track(t, t * 100, np.where(t < 4, 80.0, -20.0))
    real = TEST_ONLY_track(t, t * 90, np.where(t < 4.3, 80.0, -20.0))
    ctx = events.GhostContext(liftoff_s=0.0, mach=np.full(t.size, 0.95), deploys=[])
    timing = events.compare(ghost, ctx, real, coarse=False)
    thrust = next(e for e in timing.events if e.key == "thrust_end")
    assert thrust.real_t is not None and thrust.real_altitude_m is None
    assert thrust.note and "Mach 0.95" in thrust.note
    peak = next(e for e in timing.events if e.key == "peak_vz")
    assert peak.status == "not_detected"


def test_speed_peak_after_deceleration_is_rejected_as_sensor_disagreement() -> None:
    t = np.arange(0, 30, 0.1)
    ghost = TEST_ONLY_track(t, 100 * t - 2 * t**2, np.where(t < 3, 80.0, -20.0))
    # Real altitude keeps steepening until t = 8 although the accelerometer says thrust ended at 3.
    real_alt = np.where(t < 8, 12 * t**2, 12 * 64 + 192 * (t - 8) - 5 * (t - 8) ** 2)
    real = TEST_ONLY_track(t, real_alt, np.where(t < 3, 80.0, -20.0))
    ctx = events.GhostContext(liftoff_s=0.0, mach=np.full(t.size, 0.4), deploys=[])
    peak = next(
        e for e in events.compare(ghost, ctx, real, coarse=False).events if e.key == "peak_vz"
    )
    assert peak.status == "not_detected" and peak.note and "disagree" in peak.note


def TEST_ONLY_sensor(pad: float, coast: float, n_pad: int = 20):  # TEST_ONLY_: synthetic data
    """Pad readings, a burn, then coast, on a 0.05 s grid starting before liftoff (t = 0)."""
    t = np.arange(-2.0, 15.0, 0.05)
    a = np.where(t < -0.2, pad, np.where(t < 3.0, 60.0, coast))
    if n_pad == 0:
        keep = t > -0.2
        return t[keep], a[keep]
    return t, a


def test_gravity_removed_is_read_from_the_pad_and_confirmed_by_coast_physics() -> None:
    t, a = TEST_ONLY_sensor(pad=0.02, coast=-17.0)
    ghost_f = np.where(t < 3.0, 70.0, -7.0)  # ghost drag in coast: −7 m/s²
    acc, why = events.read_accelerometer(t, a, 0.0, t, ghost_f)
    assert acc is not None, why
    assert acc.gravity_removed
    assert np.isclose(acc.specific_force[-1], -17.0 + events.GRAVITY)


def test_a_raw_sensor_reads_one_g_on_the_pad() -> None:
    t, a = TEST_ONLY_sensor(pad=9.8, coast=-7.2)
    acc, why = events.read_accelerometer(t, a, 0.0, t, np.where(t < 3.0, 70.0, -7.0))
    assert acc is not None, why
    assert not acc.gravity_removed


def test_pad_and_physics_disagreeing_means_the_accelerometer_is_not_used() -> None:
    # Pad says raw (1 g) but coast only matches the ghost if gravity was removed.
    t, a = TEST_ONLY_sensor(pad=9.8, coast=-17.0)
    acc, why = events.read_accelerometer(t, a, 0.0, t, np.where(t < 3.0, 70.0, -7.0))
    assert acc is None and "disagree" in why


def test_without_pad_samples_the_physics_test_decides() -> None:
    t, a = TEST_ONLY_sensor(pad=0.0, coast=-16.5, n_pad=0)
    acc, why = events.read_accelerometer(t, a, 0.0, t, np.where(t < 3.0, 70.0, -7.0))
    assert acc is not None and acc.gravity_removed, why
