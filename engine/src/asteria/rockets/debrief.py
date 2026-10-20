"""Facts packet and template debrief for one rocket flight.

Templates contain no digits of their own (not even in flight names, which is
why sentences say "the real flight" rather than "EREBUS-11"): every number in
a sentence is a fact's display string.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core.debrief import validate
from asteria.core.facts import FactSheet, fmt_delta_m, fmt_m, fmt_pct, fmt_plain, fmt_signed_unit
from asteria.models import Debrief, Sentence


@dataclass(frozen=True)
class DebriefInputs:
    flight_id: str
    notebook: str
    log_path: str
    real_apogee_m: float
    ghost_apogee_m: float
    official_apogee_m: float | None
    official_decimals: int
    team_prediction_m: float | None
    team_prediction_decimals: int
    corrected_apogee_m: float | None
    k_hat: float | None
    max_mach_ghost: float
    peak_dvz: float | None
    peak_dvz_mach: float | None
    peak_dvz_alt: float | None
    liftoff_offset_s: float | None
    median_interval_s: float
    coarse: bool


def _err(pred: float, real: float) -> float:
    return (pred - real) / real * 100.0


def build(x: DebriefInputs) -> Debrief:
    sheet = FactSheet()
    nb, log = x.notebook, x.log_path
    f_real = sheet.add(
        "Real apogee (max of published log)", x.real_apogee_m, "m", fmt_m(x.real_apogee_m), log
    )
    f_ghost = sheet.add(
        "Ghost apogee (RocketPy reconstruction)", x.ghost_apogee_m, "m", fmt_m(x.ghost_apogee_m), nb
    )
    gap = x.real_apogee_m - x.ghost_apogee_m
    f_gap = sheet.add("Apogee gap (real − ghost)", gap, "m", fmt_delta_m(gap), f"{log}; {nb}")
    ghost_err = _err(x.ghost_apogee_m, x.real_apogee_m)
    f_gerr = sheet.add("Ghost apogee error", ghost_err, "%", fmt_pct(ghost_err), f"{log}; {nb}")
    sentences = [
        Sentence(
            text=(
                f"The real flight peaked at {sheet.display(f_real)}, while the ghost "
                f"reconstruction reached {sheet.display(f_ghost)}: "
                f"a gap of {sheet.display(f_gap)}, "
                f"or {sheet.display(f_gerr)} ghost error."
            ),
            fact_ids=[f_real, f_ghost, f_gap, f_gerr],
        )
    ]
    if x.official_apogee_m is not None:
        f_off = sheet.add(
            "Official recorded apogee (flight card)",
            x.official_apogee_m,
            "m",
            fmt_m(x.official_apogee_m, x.official_decimals),
            nb,
        )
        sentences.append(
            Sentence(
                text=(
                    f"The team's flight card records {sheet.display(f_off)} as the official apogee."
                ),
                fact_ids=[f_off],
            )
        )
    if x.team_prediction_m is not None:
        f_tp = sheet.add(
            "Team pre-flight prediction (flight card)",
            x.team_prediction_m,
            "m",
            fmt_m(x.team_prediction_m, x.team_prediction_decimals),
            nb,
        )
        tp_err = _err(x.team_prediction_m, x.real_apogee_m)
        f_tpe = sheet.add("Team prediction error", tp_err, "%", fmt_pct(tp_err), f"{log}; {nb}")
        sentences.append(
            Sentence(
                text=(
                    f"Before launch, the team's last simulation predicted {sheet.display(f_tp)}, "
                    f"an error of {sheet.display(f_tpe)} against the log."
                ),
                fact_ids=[f_tp, f_tpe],
            )
        )
    if x.coarse:
        f_dt = sheet.add(
            "Median log sample interval",
            x.median_interval_s,
            "s",
            f"{x.median_interval_s:.2f} s",
            log,
        )
        sentences.append(
            Sentence(
                text=(
                    "The log is too coarse to resolve velocity (one sample every "
                    f"{sheet.display(f_dt)} on median), so this flight counts for apogee "
                    "but stays out of the gap map."
                ),
                fact_ids=[f_dt],
            )
        )
    elif x.peak_dvz is not None and x.peak_dvz_mach is not None and x.peak_dvz_alt is not None:
        f_dv = sheet.add(
            "Largest ascent velocity gap (real − ghost)",
            x.peak_dvz,
            "m/s",
            fmt_signed_unit(x.peak_dvz, 1, "m/s"),
            f"{log}; {nb}",
        )
        f_dm = sheet.add(
            "Ghost Mach at the largest velocity gap",
            x.peak_dvz_mach,
            "",
            fmt_plain(x.peak_dvz_mach, 2),
            nb,
        )
        f_da = sheet.add(
            "Ghost altitude at the largest velocity gap",
            x.peak_dvz_alt,
            "m",
            fmt_m(x.peak_dvz_alt),
            nb,
        )
        direction = "slower" if x.peak_dvz < 0 else "faster"
        sentences.append(
            Sentence(
                text=(
                    f"The largest velocity gap in the climb was {sheet.display(f_dv)} "
                    f"(real minus ghost) near Mach {sheet.display(f_dm)} at "
                    f"{sheet.display(f_da)}: there the real rocket was moving {direction} "
                    "than the ghost."
                ),
                fact_ids=[f_dv, f_dm, f_da],
            )
        )
    if x.corrected_apogee_m is not None and x.k_hat is not None:
        f_k = sheet.add(
            "Held-out drag scale k̂", x.k_hat, "", fmt_plain(x.k_hat, 3), "correction report"
        )
        f_c = sheet.add(
            "Corrected apogee (held out)",
            x.corrected_apogee_m,
            "m",
            fmt_m(x.corrected_apogee_m),
            "correction report",
        )
        c_err = _err(x.corrected_apogee_m, x.real_apogee_m)
        f_ce = sheet.add("Corrected apogee error", c_err, "%", fmt_pct(c_err), "correction report")
        verdict = "closer to" if abs(c_err) < abs(ghost_err) else "further from"
        sentences.append(
            Sentence(
                text=(
                    "With this flight held out, the fleet correction "
                    f"(drag × {sheet.display(f_k)}) "
                    f"predicts {sheet.display(f_c)}, an error of {sheet.display(f_ce)}, "
                    f"which is {verdict} the real apogee than physics alone."
                ),
                fact_ids=[f_k, f_c, f_ce, f_gerr],
            )
        )
    if x.liftoff_offset_s is not None:
        f_lo = sheet.add(
            "Liftoff clock offset (real − ghost)",
            x.liftoff_offset_s,
            "s",
            fmt_signed_unit(x.liftoff_offset_s, 2, "s"),
            f"{log}; {nb}",
        )
        sentences.append(
            Sentence(
                text=(
                    f"The log's clock is offset {sheet.display(f_lo)} from the ghost at liftoff; "
                    "gaps are compared after aligning the two at that moment."
                ),
                fact_ids=[f_lo],
            )
        )
    else:
        sentences.append(
            Sentence(
                text=(
                    "No clean liftoff was found in the log, so its clock is used "
                    "exactly as published."
                ),
                fact_ids=[f_real],
            )
        )
    f_mach = sheet.add("Ghost peak Mach", x.max_mach_ghost, "", fmt_plain(x.max_mach_ghost, 2), nb)
    sentences.append(
        Sentence(
            text=f"The ghost's fastest point was Mach {sheet.display(f_mach)}.",
            fact_ids=[f_mach],
        )
    )
    kept, validation = validate(sentences, sheet.facts)
    return Debrief(
        flight_id=x.flight_id,
        facts=sheet.facts,
        sentences=kept,
        generator="template",
        validation=validation,
    )
