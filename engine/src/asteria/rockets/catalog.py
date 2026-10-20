"""The fleet: which published flights Asteria uses, and exactly how.

Rules for an entry:
* `notebook` is a RocketPy example notebook at the pinned commit; its code
  builds the ghost (`flight_var`).
* `log` names the published file/columns the notebook itself compares
  against. Units are as published unless the evidence says otherwise.
* Quotes are copied verbatim from the notebook's markdown; their numbers are
  parsed from the quote by code, never retyped. A unit test checks every
  quote against the pinned notebook text.
* `team_prediction` is used ONLY when the notebook explicitly says the number
  is the pre-flight simulation ("before flight" / "Last simulated"). Several
  notebooks list RocketPy's own post-flight result as "Simulated apogee";
  those are not team predictions and are not used.
* Any departure from "as published" (a cutoff, a skipped cell) carries its
  evidence in writing and is shown in the console.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from asteria.rockets.telemetry import ExtraChannel, GnssSpec, LogSpec

EXAMPLES = "docs/examples"
DATA = "data/rockets"

_NUMBER_BEFORE_M = re.compile(r"([\d,]+(?:\.\d+)?)\s*m\b")


def _metre_token(quote: str) -> str:
    matches = _NUMBER_BEFORE_M.findall(quote)
    if not matches:
        raise ValueError(f"no metre value in quote: {quote!r}")
    return str(matches[-1])


def metres_in_quote(quote: str) -> float:
    """The last number followed by the unit 'm' in a verbatim quote."""
    return float(_metre_token(quote).replace(",", ""))


def metre_decimals(quote: str) -> int:
    """How many decimals the source itself gave, so we never add precision."""
    token = _metre_token(quote)
    return len(token.split(".")[1]) if "." in token else 0


@dataclass(frozen=True)
class FlightSpec:
    id: str
    name: str
    team: str
    event: str
    year: int
    notebook: str
    flight_var: str
    log: LogSpec
    importer_var: str | None
    title_quote: str
    gnss: GnssSpec | None = None
    team_prediction_quote: str | None = None
    official_apogee_quote: str | None = None
    skip_cells: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Exclusion:
    notebook: str
    reason: str


EUROC = "EuRoC"
ACCEL_FILTERED = ExtraChannel(
    "accel_logged",
    "filtered_acceleration",
    "m/s²",
    "Acceleration (filtered, logged; unit as read by the RocketPy notebook)",
)
SA_CUP = "Spaceport America Cup"

FLEET: tuple[FlightSpec, ...] = (
    FlightSpec(
        id="andromeda-2022",
        name="Andromeda",
        team="Aristotle Space and Aeronautics Team",
        event=f"{EUROC} 2022",
        year=2022,
        notebook=f"{EXAMPLES}/andromeda_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Andromeda -  Aristotle Space and Aeronautics Team - 2022",
        log=LogSpec(
            path=f"{DATA}/andromeda/flight_data.csv",
            time_column="t(s)",
            altitude_column="alt(m)",
            altitude_unit="m",
            extra=(ExtraChannel("vz_logged", "vz(m/s)", "m/s", "Vertical velocity (logged)"),),
        ),
        official_apogee_quote="Official recorded apogee: `3443 m`",
    ),
    FlightSpec(
        id="astra-2022",
        name="Astra",
        team="Faraday Rocketry UPV",
        event=f"{EUROC} 2022",
        year=2022,
        notebook=f"{EXAMPLES}/astra_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="telemetry_data",
        title_quote="# Astra - Faraday Rocketry UPV - 2022",
        log=LogSpec(
            path=f"{DATA}/astra/flight_data.csv",
            time_column="t",
            altitude_column="alt",
            altitude_unit="m",
        ),
        official_apogee_quote="Official recorded apogee: `3250 m`",
    ),
    FlightSpec(
        id="bella-lui-2020",
        name="Bella Lui",
        team="EPFL Rocket Team",
        event="Kaltbrunn mission 2020",
        year=2020,
        notebook=f"{EXAMPLES}/bella_lui_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var=None,
        title_quote="# Bella Lui - EPFL - 2020",
        log=LogSpec(
            path=f"{DATA}/EPFL_Bella_Lui/bella_lui_flight_data_filtered.csv",
            time_column="time aprox (s)",
            altitude_column="z (m)",
            altitude_unit="m",
            extra=(ExtraChannel("vz_logged", "v (m/s)", "m/s", "Vertical velocity (logged)"),),
        ),
    ),
    FlightSpec(
        id="camoes-2023",
        name="Camões",
        team="Rocket Experiment Division",
        event=f"{EUROC} 2023",
        year=2023,
        notebook=f"{EXAMPLES}/camoes_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Camões - Rocket Experiment Division",
        log=LogSpec(
            path=f"{DATA}/camoes/flight_data.csv",
            time_column="ts",
            altitude_column="filtered_altitude_AGL",
            altitude_unit="m",
            extra=(ACCEL_FILTERED,),
        ),
        gnss=GnssSpec(
            path=f"{DATA}/camoes/gnss_flight.csv",
            time_column="ts",
            latitude_column="latitude",
            longitude_column="longitude",
        ),
        official_apogee_quote="Official recorded apogee: `3015 m`",
    ),
    FlightSpec(
        id="cavour-2023",
        name="Cavour",
        team="PoliTo Rocket Team",
        event=f"{EUROC} 2023",
        year=2023,
        notebook=f"{EXAMPLES}/cavour_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Cavour - PoliTo Rocket Team",
        log=LogSpec(
            path=f"{DATA}/polito/altimeter_cavour.csv",
            time_column="ts",
            altitude_column="altitude[m]",
            altitude_unit="m",
            extra=(
                ExtraChannel("vz_logged", "velocity[m/s]", "m/s", "Vertical velocity (logged)"),
            ),
        ),
        team_prediction_quote="Last simulated apogee before flight: `2806 m`",
        official_apogee_quote="Official recorded apogee: `2789 m`",
    ),
    FlightSpec(
        id="erebus-11-2022",
        name="EREBUS-11",
        team="BME Suborbitals Rocket Team",
        event=f"{EUROC} 2022",
        year=2022,
        notebook=f"{EXAMPLES}/erebus_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# EREBUS-11  - BME Suborbitals Rocket Team",
        log=LogSpec(
            path=f"{DATA}/erebus11/flight_data_filtered.csv",
            time_column="t",
            altitude_column="alt",
            altitude_unit="m",
        ),
        official_apogee_quote="Official recorded apogee: `3020 m`",
    ),
    FlightSpec(
        id="genesis-2023",
        name="GENESIS",
        team="Faraday Rocketry UPV",
        event=f"{EUROC} 2023",
        year=2023,
        notebook=f"{EXAMPLES}/genesis_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# GENESIS - Faraday Rocketry UPV - 2023",
        log=LogSpec(
            path=f"{DATA}/genesis/flight_data_faraday.csv",
            time_column="ts",
            altitude_column="filtered_altitude_AGL",
            altitude_unit="m",
            extra=(ACCEL_FILTERED,),
        ),
        official_apogee_quote="Official recorded apogee: `2916 m`",
    ),
    FlightSpec(
        id="juno-iii-2023",
        name="Juno III",
        team="Projeto Jupiter (University of São Paulo)",
        event=f"{SA_CUP} 2023",
        year=2023,
        notebook=f"{EXAMPLES}/juno3_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Juno III - Projeto Jupiter 2023",
        log=LogSpec(
            path=f"{DATA}/juno3/cots_altimeter.csv",
            time_column="time",
            altitude_column="altitude",
            altitude_unit="m",
            extra=(
                ExtraChannel("vz_logged", "velocity", "m/s", "Vertical velocity (RRC3, logged)"),
            ),
            keep_until_s=30.40,
            keep_until_reason=(
                "The final two records (t = 30.45 s and 30.50 s), written at the drogue "
                "event, read 191.25 and 1158.70 in the pressure column while every "
                "sample in the preceding second reads about 580, a jump no atmosphere "
                "allows in 0.05 s; their altitudes (10,700.59 m and -2,490.543 m) are "
                "therefore excluded."
            ),
        ),
        gnss=GnssSpec(
            path=f"{DATA}/juno3/cots_GNSS.csv",
            time_column="time",
            latitude_column="LAT",
            longitude_column="LON",
        ),
        team_prediction_quote="Last simulated apogee before flight: `3026.054 m`",
        official_apogee_quote="Official recorded apogee: `3213 m`",
    ),
    FlightSpec(
        id="lince-2023",
        name="Lince",
        team="Student Team for Aerospace and Rocketry UC3M",
        event=f"{EUROC} 2023",
        year=2023,
        notebook=f"{EXAMPLES}/lince_flight_sim.ipynb",
        flight_var="flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Lince - Student Team for Aerospace and Rocketry UC3M - 2023",
        log=LogSpec(
            path=f"{DATA}/lince/main_data.csv",
            time_column="ts",
            altitude_column="filtered_altitude_AGL",
            altitude_unit="m",
            extra=(ACCEL_FILTERED,),
        ),
        official_apogee_quote="Official recorded apogee: `3587 m`",
    ),
    FlightSpec(
        id="ndrt-2020",
        name="NDRT 2020",
        team="Notre Dame Rocket Team",
        event="Three Oaks, Michigan 2020",
        year=2020,
        notebook=f"{EXAMPLES}/ndrt_2020_flight_sim.ipynb",
        flight_var="flight",
        importer_var=None,
        title_quote="# Notre Dame Rocket Team Rocket 2020",
        log=LogSpec(
            path=f"{DATA}/NDRT_2020/ndrt_2020_flight_data.csv",
            time_column=" Time (s)",
            altitude_column=" Altitude (Ft-AGL)",
            altitude_unit="ft",
        ),
        official_apogee_quote="Measured Altitude 4,320 ft or 1316.736 m",
    ),
    FlightSpec(
        id="prometheus-2022",
        name="Prometheus",
        team="Western Engineering Rocketry Team",
        event=f"{SA_CUP} 2022",
        year=2022,
        notebook=f"{EXAMPLES}/prometheus_2022_flight_sim.ipynb",
        flight_var="test_flight",
        importer_var="cots_altimeter_flight",
        title_quote="# Prometheus - Western Engineering Rocketry Team 2022",
        log=LogSpec(
            path=f"{DATA}/prometheus/2022-06-24-serial-5115-flight-0001-TeleMetrum.csv",
            time_column="time",
            altitude_column="height",
            altitude_unit="m",
            extra=(
                ExtraChannel("speed_logged", "speed", "m/s", "Speed (TeleMetrum, logged)"),
                ExtraChannel(
                    "accel_logged", "acceleration", "m/s²", "Acceleration (TeleMetrum, logged)"
                ),
            ),
        ),
        gnss=GnssSpec(
            path=f"{DATA}/prometheus/2022-06-24-serial-5115-flight-0001-TeleMetrum.csv",
            time_column="time",
            latitude_column="latitude",
            longitude_column="longitude",
        ),
        team_prediction_quote="**Last Simulated Apogee:** 4190.05 m",
        official_apogee_quote="**Official Recorded Apogee:** 3898.37 m",
    ),
)

EXCLUDED: tuple[Exclusion, ...] = (
    Exclusion(
        f"{EXAMPLES}/defiance_flight_sim.ipynb",
        "No flight log is published; only an apogee number.",
    ),
    Exclusion(
        f"{EXAMPLES}/valetudo_flight_sim.ipynb", "No flight log is published in the repository."
    ),
    Exclusion(
        f"{EXAMPLES}/valkyrie_flight_sim.ipynb",
        "Its weather comes from a live forecast service (Windy, set_atmospheric_model type "
        "'windy'), which returns today's forecast, and its Environment date is 2026-07-26 while "
        "the flight was on 2025-07-26; the ghost would be neither reproducible nor the launch day.",
    ),
    Exclusion(
        f"{EXAMPLES}/hedy_flight_sim.ipynb",
        "Cell 12 fetches the site elevation from a live web service (Open-Elevation), and its "
        "flight-log importer reads data/rockets/tust/, which does not exist at the pinned commit "
        "(the files are under data/rockets/hedy/cats_tust/).",
    ),
    Exclusion(
        f"{EXAMPLES}/halcyon_flight_sim.ipynb",
        "Too expensive to rebuild as published: building its hybrid motor (cell 10, RocketPy "
        "1.13.0 grain-regression ODE in solid_motor.py:603, scipy 1.18.1) ran 6 min and grew past "
        "1.8 GB without finishing, and a 15-min full attempt reached 4.4 GB; calibration would "
        "need about a dozen more simulations on an 8 GB machine. Measured 2026-10-20.",
    ),
    Exclusion(f"{EXAMPLES}/SEB_liquid_motor.ipynb", "A motor test, not a flight."),
)


def by_id(flight_id: str) -> FlightSpec:
    for spec in FLEET:
        if spec.id == flight_id:
            return spec
    raise KeyError(flight_id)
