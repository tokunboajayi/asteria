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


class CorrectionReport(Model):
    model: str
    clip: tuple[float, float]
    k_bracket: tuple[float, float]
    evaluation: Literal["leave-one-flight-out"]
    per_flight: list[CorrectionRow]
    aggregate: CorrectionAggregate


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
