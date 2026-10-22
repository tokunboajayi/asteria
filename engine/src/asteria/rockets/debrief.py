"""Facts packet and template debrief for one rocket flight.

Templates contain no digits of their own (not even in flight names, which is
why sentences say "the real flight" rather than "EREBUS-11"): every number in
a sentence is a fact's display string.
"""

from __future__ import annotations

from asteria.core.debrief import validate
from asteria.core.facts import FactSheet, fmt_delta_m, fmt_m, fmt_pct, fmt_plain, fmt_signed_unit
from asteria.models import Debrief, Diagnostics, FlightSummary, Sentence
from asteria.rockets.catalog import FlightSpec, metre_decimals
from asteria.rockets.correction import error_pct


def build(
    spec: FlightSpec,
    summary: FlightSummary,
    diagnostics: Diagnostics,
    peak_dvz: tuple[float, float, float] | None,
) -> Debrief:
    """`peak_dvz` is (Δvz, ghost Mach, ghost altitude) at the largest ascent velocity gap."""
    sheet = FactSheet()
    nb, log = spec.notebook, spec.log.path
    real_m, ghost_m = summary.apogee.real_m, summary.apogee.ghost_m
    official, team = summary.official_apogee, summary.team_prediction
    corrected = summary.correction
    f_real = sheet.add("Real apogee (max of published log)", real_m, "m", fmt_m(real_m), log)
    f_ghost = sheet.add("Ghost apogee (RocketPy reconstruction)", ghost_m, "m", fmt_m(ghost_m), nb)
    gap = real_m - ghost_m
    f_gap = sheet.add("Apogee gap (real − ghost)", gap, "m", fmt_delta_m(gap), f"{log}; {nb}")
    ghost_err = error_pct(ghost_m, real_m)
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
    if official is not None:
        f_off = sheet.add(
            "Official recorded apogee (flight card)",
            official.value_m,
            "m",
            fmt_m(official.value_m, metre_decimals(official.quote)),
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
    if team is not None:
        f_tp = sheet.add(
            "Team pre-flight prediction (flight card)",
            team.value_m,
            "m",
            fmt_m(team.value_m, metre_decimals(team.quote)),
            nb,
        )
        tp_err = error_pct(team.value_m, real_m)
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
    if diagnostics.coarse_log:
        f_dt = sheet.add(
            "Median log sample interval",
            diagnostics.median_sample_interval_s,
            "s",
            f"{diagnostics.median_sample_interval_s:.2f} s",
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
    elif peak_dvz is not None:
        dvz, dvz_mach, dvz_alt = peak_dvz
        f_dv = sheet.add(
            "Largest ascent velocity gap (real − ghost)",
            dvz,
            "m/s",
            fmt_signed_unit(dvz, 1, "m/s"),
            f"{log}; {nb}",
        )
        f_dm = sheet.add(
            "Ghost Mach at the largest velocity gap",
            dvz_mach,
            "",
            fmt_plain(dvz_mach, 2),
            nb,
        )
        f_da = sheet.add(
            "Ghost altitude at the largest velocity gap",
            dvz_alt,
            "m",
            fmt_m(dvz_alt),
            nb,
        )
        direction = "slower" if dvz < 0 else "faster"
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
    if corrected is not None:
        f_k = sheet.add(
            "Held-out drag scale k̂",
            corrected.k_hat,
            "",
            fmt_plain(corrected.k_hat, 3),
            "correction report",
        )
        f_c = sheet.add(
            "Corrected apogee (held out)",
            corrected.corrected_apogee_m,
            "m",
            fmt_m(corrected.corrected_apogee_m),
            "correction report",
        )
        c_err = error_pct(corrected.corrected_apogee_m, real_m)
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
    if diagnostics.liftoff_offset_s is not None:
        f_lo = sheet.add(
            "Liftoff clock offset (real − ghost)",
            diagnostics.liftoff_offset_s,
            "s",
            fmt_signed_unit(diagnostics.liftoff_offset_s, 2, "s"),
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
    f_mach = sheet.add(
        "Ghost peak Mach", summary.max_mach_ghost, "", fmt_plain(summary.max_mach_ghost, 2), nb
    )
    sentences.append(
        Sentence(
            text=f"The ghost's fastest point was Mach {sheet.display(f_mach)}.",
            fact_ids=[f_mach],
        )
    )
    kept, validation = validate(sentences, sheet.facts)
    return Debrief(
        flight_id=spec.id,
        facts=sheet.facts,
        sentences=kept,
        generator="template",
        validation=validation,
    )
