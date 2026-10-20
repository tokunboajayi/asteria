from __future__ import annotations

import pytest

from asteria.core import debrief as core
from asteria.core.facts import MINUS, fmt_delta_m, fmt_m, fmt_pct
from asteria.models import Fact, Sentence
from asteria.rockets import debrief


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


@pytest.mark.parametrize("coarse", [True, False])
def test_template_debrief_always_validates(coarse: bool) -> None:
    d = debrief.build(
        debrief.DebriefInputs(
            flight_id="erebus-11-2022",
            notebook="nb",
            log_path="log",
            real_apogee_m=3001.8,
            ghost_apogee_m=2751.1,
            official_apogee_m=3020.0,
            official_decimals=0,
            team_prediction_m=2806.0,
            team_prediction_decimals=0,
            corrected_apogee_m=2800.0,
            k_hat=0.95,
            max_mach_ghost=0.86,
            peak_dvz=-20.5,
            peak_dvz_mach=0.8,
            peak_dvz_alt=900.0,
            liftoff_offset_s=-0.31,
            median_interval_s=0.5 if coarse else 0.05,
            coarse=coarse,
        )
    )
    assert d.validation.passed and d.validation.rejected == 0
    text = " ".join(s.text for s in d.sentences)
    assert "3,020 m" in text  # source precision kept (no invented decimals)
    assert "EREBUS" not in text  # names carry digits; templates never use them
