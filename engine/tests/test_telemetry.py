from __future__ import annotations

import numpy as np
import pytest

from asteria.rockets import telemetry as tm


def test_feet_converted_exactly(csv_file) -> None:  # type: ignore[no-untyped-def]
    root, name = csv_file("log.csv", "t,h\n" + "".join(f"{i},{i * 10}\n" for i in range(12)))
    raw = tm.load_log(root, tm.LogSpec(path=name, time_column="t", altitude_column="h", altitude_unit="ft"))
    assert raw.altitude_m[-1] == pytest.approx(110 * 0.3048, abs=1e-12)


def test_cutoff_needs_reason() -> None:
    with pytest.raises(ValueError):
        tm.LogSpec(path="x", time_column="t", altitude_column="h", altitude_unit="m", keep_until_s=1.0)


def test_cutoff_drops_only_later_rows(csv_file) -> None:  # type: ignore[no-untyped-def]
    rows = "".join(f"{i},{i}\n" for i in range(15)) + "15,99999\n"
    root, name = csv_file("log.csv", "t,h\n" + rows)
    spec = tm.LogSpec(
        path=name, time_column="t", altitude_column="h", altitude_unit="m",
        keep_until_s=14.0, keep_until_reason="test fixture: last row corrupt",
    )
    raw = tm.load_log(root, spec)
    assert raw.rows_after_cutoff == 1
    assert raw.altitude_m.max() == 14


def test_blank_optional_column_never_removes_an_altitude_row(csv_file) -> None:  # type: ignore[no-untyped-def]
    rows = "".join(f"{i},{i},{'' if i == 5 else i * 2}\n" for i in range(12))
    root, name = csv_file("log.csv", "t,h,v\n" + rows)
    spec = tm.LogSpec(
        path=name, time_column="t", altitude_column="h", altitude_unit="m",
        extra=(tm.ExtraChannel("vz_logged", "v", "m/s", "v"),),
    )
    raw = tm.load_log(root, spec)
    assert raw.t.size == 12
    assert np.isnan(raw.extra["vz_logged"][5])


def test_clean_keeps_first_sample_per_timestamp(csv_file) -> None:  # type: ignore[no-untyped-def]
    rows = "0,1\n0,2\n1,3\n1,4\n2,5\n" + "".join(f"{i},{i}\n" for i in range(3, 12))
    root, name = csv_file("log.csv", "t,h\n" + rows)
    clean = tm.clean(tm.load_log(root, tm.LogSpec(path=name, time_column="t", altitude_column="h", altitude_unit="m")))
    assert clean.duplicate_timestamps == 2
    assert list(clean.altitude_m[:3]) == [1, 3, 5]
    assert np.all(np.diff(clean.t) > 0)


def test_duplicate_header_uses_first_occurrence(csv_file) -> None:  # type: ignore[no-untyped-def]
    rows = "".join(f"{i},{i},{-i}\n" for i in range(12))
    root, name = csv_file("log.csv", "t,h,h\n" + rows)
    raw = tm.load_log(root, tm.LogSpec(path=name, time_column="t", altitude_column="h", altitude_unit="m"))
    assert raw.altitude_m.max() == 11


def test_gnss_drops_no_fix_rows(csv_file) -> None:  # type: ignore[no-untyped-def]
    root, name = csv_file("g.csv", "t,lat,lon\n0,0,0\n1,32.9,-106.9\n2,32.8,-106.8\n")
    g = tm.load_gnss(root, tm.GnssSpec(path=name, time_column="t", latitude_column="lat", longitude_column="lon"))
    assert list(g.t) == [1, 2]
