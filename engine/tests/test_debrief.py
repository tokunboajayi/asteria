from __future__ import annotations

import pytest

from asteria.core import debrief as core
from asteria.core.facts import MINUS, fmt_delta_m, fmt_m, fmt_pct
from asteria.models import (
    ApogeeSummary,
    CorrectionSummary,
    Diagnostics,
    Fact,
    FlightSummary,
    LaunchSite,
    Quote,
    Sentence,
)
from asteria.rockets import catalog, debrief


def _fact(fid: str, display: str) -> Fact:
    return Fact(id=fid, label="label", value=0.0, unit="m", display=display, source="s")


def test_formats_use_true_minus_and_explicit_plus() -> None:
    assert fmt_m(-1234.56) == f"{MINUS}1,234.6 m"
    assert fmt_delta_m(12.0) == "+12.0 m"
    assert fmt_pct(-0.04) == f"{MINUS}0.0%"


def test_validator_rejects_numbers_not_in_cited_facts() -> None:
    facts = [_fact("F1", "3,438.5 m")]
    ok = Sentence(text="It peaked at 3,438.5 m.", fact_ids=["F1"])
    bad = Sentence(text="It peaked at 3,500 m.", fact_ids=["F1"])
    uncited = Sentence(text="It flew well.", fact_ids=[])
    missing = Sentence(text="It peaked at 3,438.5 m.", fact_ids=["F9"])
    kept, v = core.validate([ok, bad, uncited, missing], facts)
    assert kept == [ok]
    assert v.rejected == 3 and not v.passed


def _summary() -> FlightSummary:
    return FlightSummary(
        id="erebus-11-2022",
        name="Erebus",
        team="t",
        event="e",
        year=2022,
        launch_site=LaunchSite(latitude_deg=0.0, longitude_deg=0.0, elevation_m=0.0),
        has_position=False,
        real_channels=[],
        apogee=ApogeeSummary(
            real_m=3001.8,
            real_time_s=25.0,
            ghost_m=2751.1,
            ghost_time_s=24.0,
            delta_m=250.7,
            ghost_error_pct=-8.4,
        ),
        team_prediction=Quote(value_m=2806.0, quote="Last simulated apogee: 2806 m"),
        official_apogee=Quote(value_m=3020.0, quote="Official apogee: 3,020 m"),
        max_mach_ghost=0.86,
        correction=CorrectionSummary(
            k_own=0.9,
            k_hat=0.95,
            corrected_apogee_m=2800.0,
            err_before_pct=-8.4,
            err_after_pct=-6.7,
        ),
    )


def _diagnostics(coarse: bool) -> Diagnostics:
    return Diagnostics(
        real_t_start_s=0.0,
        real_t_end_s=100.0,
        real_liftoff_s=1.0,
        ghost_liftoff_s=1.31,
        liftoff_offset_s=-0.31,
        median_sample_interval_s=0.5 if coarse else 0.05,
        coarse_log=coarse,
        duplicate_timestamps=0,
        rows_after_cutoff=0,
        importer_cross_check="identical",
    )


@pytest.mark.parametrize("coarse", [True, False])
def test_template_debrief_always_validates(coarse: bool) -> None:
    spec = catalog.by_id("erebus-11-2022")
    d = debrief.build(spec, _summary(), _diagnostics(coarse), (-20.5, 0.8, 900.0))
    assert d.validation.passed and d.validation.rejected == 0
    text = " ".join(s.text for s in d.sentences)
    assert "3,020 m" in text  # source precision kept (no invented decimals)
    assert "EREBUS" not in text  # names carry digits; templates never use them
