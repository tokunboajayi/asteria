"""Motor & drag fingerprint: real ÷ ghost readings over identical fixed windows."""

import numpy as np

from asteria.rockets import events, fingerprint


def TEST_ONLY_track(burn: float, coast: float):  # TEST_ONLY_: synthetic data
    t = np.arange(0.0, 15.0, 0.02)
    force = np.where(t < 3.0, burn, coast)
    zeros = np.zeros_like(t)
    return events.Track(t, zeros, zeros, force)


def test_ratios_compare_like_with_like() -> None:
    ghost = TEST_ONLY_track(burn=100.0, coast=-8.0)
    real = TEST_ONLY_track(burn=110.0, coast=-7.2)
    fp = fingerprint.measure(ghost, real, liftoff_s=0.0, accelerometer_note="ok")
    assert fp.status == "measured"
    # Both windows end 0.5 s after the same thrust end, so the coast part of the burn
    # window is identical in form; the ratio sits between the coast and burn ratios.
    assert fp.burn_ratio is not None and 1.0 < fp.burn_ratio < 1.11
    assert fp.coast_drag_ratio is not None and np.isclose(fp.coast_drag_ratio, 0.9)


def test_no_accelerometer_means_not_measured_with_the_reason() -> None:
    ghost = TEST_ONLY_track(burn=100.0, coast=-8.0)
    real = events.Track(ghost.t, ghost.altitude, ghost.vz, None)
    fp = fingerprint.measure(ghost, real, liftoff_s=0.0, accelerometer_note=None)
    assert fp.status == "not_measured" and fp.reason and "no accelerometer" in fp.reason
