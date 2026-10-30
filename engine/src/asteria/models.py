"""The data contract.

These models are the single schema shared by the engine's artifacts, the API
and (via OpenAPI) the web console's TypeScript types. Field docs say what each
number is and where it comes from; nothing here is optional by accident.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------
class SourceFile(Model):
    path: str = Field(description="Path relative to the pinned source checkout.")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)


class Provenance(Model):
    repo: str
    tag: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    notebook: str = Field(description="Notebook whose code built the ghost.")
    files: list[SourceFile]
    rocketpy_version: str
    engine_version: str
    generated_at: str = Field(description="UTC ISO-8601 time the artifact was built.")


class FleetProvenance(Model):
    repo: str
    tag: str
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    rocketpy_version: str
    engine_version: str
    generated_at: str


# --------------------------------------------------------------------------
# Flight summary
# --------------------------------------------------------------------------
class Quote(Model):
    """A number quoted verbatim from the source notebook's markdown."""

    value_m: float
    quote: str = Field(description="Exact text from the notebook containing the value.")


class LaunchSite(Model):
    latitude_deg: float
    longitude_deg: float
    elevation_m: float


class ApogeeSummary(Model):
    real_m: float = Field(description="Max of the published altitude log (AGL).")
    real_time_s: float
    ghost_m: float = Field(description="RocketPy reconstruction apogee, AGL.")
    ghost_time_s: float
    delta_m: float = Field(description="real − ghost.")
    ghost_error_pct: float = Field(description="(ghost − real) / real × 100.")


class CorrectionSummary(Model):
    k_own: float = Field(
        description="Drag scale that makes this flight's ghost hit its real apogee."
    )
    k_hat: float = Field(
        description="Held-out prediction: median of the OTHER flights' k, clipped."
    )
    corrected_apogee_m: float
    err_before_pct: float
    err_after_pct: float


class FlightSummary(Model):
    id: str
    name: str
    team: str
    event: str
    year: int
    launch_site: LaunchSite
    has_position: bool = Field(description="True only if the log has GNSS latitude/longitude.")
    real_channels: list[str]
    apogee: ApogeeSummary
    team_prediction: Quote | None
    official_apogee: Quote | None
    max_mach_ghost: float
    correction: CorrectionSummary | None


# --------------------------------------------------------------------------
# Series
# --------------------------------------------------------------------------
class GhostSeries(Model):
    t: list[float]
    altitude: list[float] = Field(description="m AGL")
    vz: list[float] = Field(description="m/s, up positive")
    speed: list[float] = Field(description="m/s, magnitude")
    mach: list[float]
    dynamic_pressure: list[float] = Field(description="Pa")
    latitude: list[float]
    longitude: list[float]


class RawSource(Model):
    path: str
    time_column: str
    altitude_column: str
    altitude_unit: Literal["m", "ft"]
    delimiter: str
    keep_until_s: float | None = Field(
        description="Rows with time > this are excluded (declared, evidenced cutoff)."
    )
    keep_until_reason: str | None


class RealChannel(Model):
    name: str
    unit: str
    kind: Literal["measured", "derived"]
    source_column: str | None
    values: list[float | None] = Field(description="null where the logger wrote no number.")


class GnssTrack(Model):
    t: list[float]
    latitude: list[float]
    longitude: list[float]
    source: str


class RealSeries(Model):
    t: list[float] = Field(description="Log time base, s, as published.")
    channels: dict[str, RealChannel]
    gnss: GnssTrack | None
    raw_source: RawSource
    n_raw_samples: int
    decimated: bool


class DeltaSeries(Model):
    """real − ghost on the ghost time grid; null outside the real log's span.

    The real log is placed on the ghost clock by adding `real_time_shift_s`
    (liftoff alignment). The raw log in `RealSeries` keeps its own time base.
    """

    real_time_shift_s: float
    alignment: Literal["liftoff-10m", "none"]
    t: list[float]
    ghost_altitude: list[float]
    real_altitude: list[float | None]
    altitude: list[float | None]
    vz: list[float | None]


class Event(Model):
    name: str
    t: float
    source: Literal["ghost", "real"]
    detail: str


class TimedEvent(Model):
    """One event measured the same way on the ghost and on the real log (ghost clock)."""

    key: Literal["thrust_end", "peak_vz", "apogee", "final_deploy"]
    name: str
    method: str = Field(description="How the event is detected, identically for ghost and real.")
    ghost_t: float
    ghost_altitude_m: float = Field(description="m AGL")
    real_t: float | None = Field(description="Ghost clock; null when not detected.")
    real_altitude_m: float | None
    delta_t_s: float | None = Field(description="real − ghost")
    delta_altitude_m: float | None = Field(description="real − ghost")
    status: Literal["detected", "not_detected"]
    note: str | None = Field(description="Why it was not detected, or a caveat on the timing.")


class DescentRate(Model):
    phase: str
    ghost_mps: float | None = Field(
        description="Median vertical velocity, m/s (negative = down); null for a real-only row."
    )
    real_mps: float | None = Field(description="Slope of the fitted descent segment, m/s.")


class EventTiming(Model):
    events: list[TimedEvent]
    descent: list[DescentRate]
    accelerometer: str | None = Field(
        description="How the logged accelerometer was read (gravity convention, evidence), "
        "or why it was not used; null when the log has none."
    )


class Fingerprint(Model):
    """Exploratory: real ÷ ghost accelerometer readings for the burn and the coast."""

    status: Literal["measured", "not_measured"]
    burn_gain_real_mps: float | None = Field(description="∫ axial specific force over the burn.")
    burn_gain_ghost_mps: float | None
    burn_ratio: float | None = Field(description="real ÷ ghost speed gained in the burn")
    coast_decel_real_mps2: float | None = Field(description="Mean axial specific force in coast.")
    coast_decel_ghost_mps2: float | None
    coast_drag_ratio: float | None = Field(description="real ÷ ghost coast deceleration")
    burn_window_s: tuple[float, float] | None = Field(description="Ghost clock.")
    coast_window_s: tuple[float, float] | None = Field(description="Ghost clock.")
    reason: str | None


class FingerprintRow(Model):
    id: str
    name: str
    ghost_error_pct: float
    fingerprint: Fingerprint


class FleetFingerprint(Model):
    method: str
    not_attempted: str
    rows: list[FingerprintRow]


class Diagnostics(Model):
    real_t_start_s: float
    real_t_end_s: float
    real_liftoff_s: float | None = Field(description="First real sample above 10 m AGL, rising.")
    ghost_liftoff_s: float = Field(description="Ghost time at 10 m AGL.")
    liftoff_offset_s: float | None = Field(
        description="real − ghost liftoff time; used only to align Δ, shown on screen."
    )
    median_sample_interval_s: float
    coarse_log: bool = Field(description="Median interval > 0.2 s: kept out of the gap map.")
    duplicate_timestamps: int = Field(description="Repeated time stamps; first sample kept for Δ.")
    rows_after_cutoff: int
    importer_cross_check: Literal["identical", "no-importer"] = Field(
        description="Asteria's loader reproduced the notebook importer's arrays exactly, "
        "or the notebook used no importer."
    )


class FleetBand(Model):
    """The ghost re-flown at the lowest and highest drag factors the OTHER flights needed.

    Each flight's k_own is the drag scale that makes the ghost reach its real apogee.
    Re-flying this flight at the other flights' extreme k values shows where it would
    have gone had it erred like any of them. With n exchangeable flights, the range of
    n others contains a new one with probability (n - 1) / (n + 1).
    """

    k_low: float
    k_high: float
    n_others: int = Field(description="Other flights with a bracketed k_own.")
    expected_coverage: float = Field(description="(n - 1) / (n + 1) for n = n_others.")
    t: list[float] = Field(description="Ghost time grid, s (same as ghost.t).")
    altitude_low: list[float | None] = Field(description="m AGL; null after either run lands.")
    altitude_high: list[float | None]
    apogee_low_m: float
    apogee_high_m: float
    real_apogee_inside: bool
    coast_s: tuple[float, float] = Field(
        description="Ghost peak vertical speed to ghost apogee, s: where drag sets the band."
    )
    real_outside: list[tuple[float, float]] = Field(
        description="Intervals within the coast (ghost clock, s) where real altitude left the band."
    )


class LaunchTime(Model):
    utc: str = Field(description="Real liftoff, UTC (midpoint of the interval the log allows).")
    uncertainty_s: float = Field(description="Half-width of that interval, s.")
    source: str
    weather_offset_days: float | None = Field(
        description="Notebook weather time minus real liftoff, days (null if no weather date)."
    )


class WeatherGhost(Model):
    """The ghost re-flown with only the weather replaced by the launch day's ERA5."""

    reason: str
    weather_time_utc: str = Field(description="ERA5 hour used: the real liftoff's hour.")
    source: str
    files: list[str] = Field(description="ERA5 files with SHA-256: launch day, then control.")
    control_apogee_m: float = Field(
        description="Re-flown on a fresh download of the notebook's own date (must match)."
    )
    notebook_apogee_m: float
    apogee_m: float = Field(description="Re-flown on the launch day's weather.")
    real_apogee_m: float
    gap_change_m: float = Field(description="(real − weather ghost) − (real − notebook ghost).")
    t: list[float]
    altitude: list[float | None] = Field(description="m AGL on the ghost grid; null after landing.")


class FlightDetail(Model):
    summary: FlightSummary
    provenance: Provenance
    ghost: GhostSeries
    corrected: GhostSeries | None
    real: RealSeries
    delta: DeltaSeries
    events: list[Event]
    timing: EventTiming
    fingerprint: Fingerprint
    diagnostics: Diagnostics
    band: FleetBand | None = Field(
        description="Null when fewer than two other flights have a bracketed k_own."
    )
    launch: LaunchTime | None = Field(
        description="Real liftoff time, only where a log records UTC; null otherwise."
    )
    weather_ghost: WeatherGhost | None = Field(
        description="Null unless the notebook's weather date differs from the real launch "
        "date and the launch day's ERA5 is cached."
    )
    weather_time_utc: str | None = Field(
        description="UTC hour of the notebook's weather data (Environment date); the ghost's "
        "clock origin. Not a recorded launch time. Null if the notebook set no date."
    )


class Excluded(Model):
    notebook: str
    reason: str


class Fleet(Model):
    flights: list[FlightSummary]
    excluded: list[Excluded]
    provenance: FleetProvenance


# --------------------------------------------------------------------------
# Fleet analyses
# --------------------------------------------------------------------------
class GapCell(Model):
    x_index: int
    y_index: int
    n_samples: int
    n_flights: int
    n_ghost_flights: int = Field(description="Fleet ghosts whose ascent passes through this cell.")
    ghost_flights: list[str]
    reachable: bool = Field(description="At least one fleet ghost flies through this cell.")
    charted: bool
    mean: float | None
    std: float | None
    flights: list[str]


class GapMap(Model):
    quantity: str
    unit: str
    coordinates: str
    x_label: str
    y_label: str
    x_edges: list[float]
    y_edges: list[float]
    min_flights: int
    total_samples: int
    flights_included: list[str]
    caveats: list[str]
    cells: list[GapCell]


class CorrectionRow(Model):
    id: str
    k_own: float
    k_hat: float
    real_apogee_m: float
    ghost_apogee_m: float
    corrected_apogee_m: float
    err_before_pct: float
    err_after_pct: float


class CorrectionAggregate(Model):
    median_abs_err_before_pct: float
    median_abs_err_after_pct: float
    n_improved: int
    n_worse: int


class BandCoverage(Model):
    """How often each flight's real apogee fell inside its own leave-one-out FleetBand."""

    flights: int
    inside: int
    expected_inside: float = Field(description="Sum over flights of (n - 1) / (n + 1).")
    outside_ids: list[str]


class CorrectionReport(Model):
    model: str
    clip: tuple[float, float]
    k_bracket: tuple[float, float]
    evaluation: Literal["leave-one-flight-out"]
    per_flight: list[CorrectionRow]
    aggregate: CorrectionAggregate
    band_coverage: BandCoverage | None


class NextBestTarget(Model):
    mach: tuple[float, float]
    alt_m: tuple[float, float]


class NearestFlight(Model):
    id: str
    name: str
    max_mach_ghost: float


class NextBest(Model):
    target: NextBestTarget
    score: float
    cells: list[tuple[int, int]]
    ghost_flights: list[str] = Field(
        description="Fleet flights whose ghost flies through the target "
        "(their logs did not chart it)."
    )
    nearest_flight: NearestFlight
    rationale: str
    limitation: str


# --------------------------------------------------------------------------
# Debrief
# --------------------------------------------------------------------------
class Fact(Model):
    id: str
    label: str
    value: float
    unit: str
    display: str = Field(description="The exact formatted string a sentence may use.")
    source: str


class Sentence(Model):
    text: str
    fact_ids: list[str]


class Validation(Model):
    passed: bool
    rejected: int
    notes: list[str]


class Debrief(Model):
    flight_id: str
    facts: list[Fact]
    sentences: list[Sentence]
    generator: Literal["template", "claude"]
    validation: Validation


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------
class Health(Model):
    ok: bool
    rocket_flights: int
    orbits_available: bool
    engine_version: str


class OrbitsStatus(Model):
    available: bool
    reason: str


# --------------------------------------------------------------------------
# Orbits: Storm Ghost
# --------------------------------------------------------------------------
class OmniSource(Model):
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    downloaded_at: str


class OrbitProvenance(Model):
    spacetrack_query: str = Field(description="Space-Track gp_history query (no credentials).")
    spacetrack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    spacetrack_downloaded_at: str
    omni: list[OmniSource]
    sgp4_version: str
    engine_version: str
    generated_at: str


class GapSeries(Model):
    """Tracked − ghost at each later element set's epoch, in the ghost's R/I/C frame (km)."""

    base_epoch: str = Field(description="Epoch of the element set the ghost starts from (UTC).")
    base_mean_altitude_km: float
    epochs: list[str]
    days: list[float]
    radial_km: list[float]
    in_track_km: list[float]
    cross_track_km: list[float]
    max_kp: list[float | None] = Field(
        description="Highest hourly Kp between the ghost's epoch and each tracked epoch."
    )
    ghost_lat: list[float]
    ghost_lon: list[float]
    ghost_alt_km: list[float]
    tracked_lat: list[float]
    tracked_lon: list[float]
    tracked_alt_km: list[float]
    stopped_by_maneuver_at: str | None = Field(
        description="Epoch of the first maneuver after the ghost's epoch; no gap is shown past it."
    )


class OrbitObjectSummary(Model):
    norad_id: int
    name: str
    note: str
    element_sets: int = Field(description="Element sets in the downloaded window.")
    storm: GapSeries | None
    quiet: GapSeries | None
    excluded_reason: str | None


class SpaceWeatherSeries(Model):
    source: str
    times: list[str]
    kp: list[float | None]
    dst_nt: list[int | None]
    ap_nt: list[int | None]
    f107_sfu: list[float | None]


class StormInfo(Model):
    name: str
    onset: str
    follow_days: float
    quiet_start: str | None
    quiet_end: str | None
    quiet_max_kp: float
    maneuver_rise_m: float
    peak_kp: float | None
    min_dst_nt: int | None


class OrbitFleet(Model):
    storm: StormInfo
    objects: list[OrbitObjectSummary]
    provenance: OrbitProvenance


# --- Orbits: ephemerides, arcs and modelled density ------------------------------
class GeoPoint(Model):
    lat: float
    lon: float
    alt_km: float


class StateVector(Model):
    """TEME position (km) and velocity (km/s) from SGP4, as Space-Track's elements define."""

    epoch: str
    r_km: tuple[float, float, float]
    v_km_s: tuple[float, float, float]


class ObjectEphemeris(Model):
    norad_id: int
    name: str
    step_s: float
    source: str = Field(
        description="How the states were made: each from the latest element set at or before it."
    )
    states: list[StateVector]
    period_min: float = Field(description="From the latest element set's mean motion.")
    arc_epoch: str = Field(description="Start of both one-revolution arcs (last tracked epoch).")
    ghost_arc: list[GeoPoint] = Field(description="Ghost's element set, one revolution.")
    tracked_arc: list[GeoPoint] = Field(description="Latest tracked element set, one revolution.")


class Ephemerides(Model):
    frame: Literal["TEME"]
    objects: list[ObjectEphemeris]


class ObjectDensity(Model):
    norad_id: int
    name: str
    mean_altitude_km: float
    times: list[str] = Field(description="Hourly, UTC.")
    density_kg_m3: list[float] = Field(description="Orbit-averaged, real indices.")
    quiet_density_kg_m3: list[float] = Field(
        description="Same positions and F10.7, geomagnetic ap held at its quiet-window mean."
    )
    ratio: list[float] = Field(description="density / quiet_density")
    peak_ratio: float
    peak_time: str


class DecayBin(Model):
    start: str
    end: str
    status: Literal["measured", "below_noise", "no_fit"]
    note: str | None = Field(description="Why there is no fit (maneuver, too few sets).")
    n_sets: int = Field(description="Element sets used for the two end estimates.")
    measured_ratio: float | None = Field(description="Density ÷ quiet, from orbit decay.")
    measured_err: float | None = Field(description="1-sigma, from the two fits.")
    model_ratio: float | None = Field(description="NRLMSIS 2.1 over the same two intervals.")
    snr: float | None = Field(description="Decay over the interval ÷ its standard error.")


class ObjectDecay(Model):
    norad_id: int
    name: str
    status: Literal["measured", "not_measurable"]
    reason: str | None
    quiet_start: str | None = Field(description="Quiet fit interval actually used.")
    quiet_end: str | None
    quiet_decay_m_per_day: float | None
    quiet_snr: float | None
    bins: list[DecayBin]
    peak: DecayBin | None = Field(description="Interval with the highest measured ratio.")


class AccelCheck(Model):
    start: str
    end: str
    accel_ratio: float | None = Field(description="Accelerometer density ÷ quiet, same intervals.")
    decay_ratio: float | None
    decay_err: float | None
    model_ratio: float | None


class AccelDensity(Model):
    """GRACE-FO 1 accelerometer density: the independent check."""

    norad_id: int
    source: str
    files: list[str] = Field(description="Input files with SHA-256.")
    times: list[str] = Field(description="Hourly, same as the model series.")
    measured_kg_m3: list[float | None] = Field(description="Orbit-mean, valid samples only.")
    model_kg_m3: list[float] | None = Field(description="Null when no model is configured.")
    median_model_over_measured: float | None
    checks: list[AccelCheck]


class DensityReport(Model):
    model: str | None = Field(description="Null by default: measured density only.")
    model_licence: str | None
    method: str | None
    quiet_ap: float = Field(description="Mean daily Ap over the quiet window.")
    sample_step_s: float
    objects: list[ObjectDensity]
    caveats: list[str]
    decay_method: str
    decay_caveats: list[str]
    decay: list[ObjectDecay]
    accelerometer: AccelDensity | None = Field(
        description="Null when the GRACE-FO files are not in the local cache."
    )
