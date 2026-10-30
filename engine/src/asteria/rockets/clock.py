"""Where a flight's ghost clock sits in UTC, and what that placement rests on."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from asteria.models import FlightDetail


@dataclass(frozen=True)
class GhostClock:
    t0: datetime  # UTC of ghost time 0
    label: str  # short, for names
    comment: str  # full, for file headers


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def ghost_clock(f: FlightDetail) -> GhostClock | None:
    """Real liftoff when a log records UTC; else the notebook's weather hour; else None."""
    if f.launch is not None:
        lift = _utc(f.launch.utc)
        return GhostClock(
            t0=lift - timedelta(seconds=f.diagnostics.ghost_liftoff_s),
            label="real liftoff time",
            comment=(
                f"Ghost liftoff placed at the real liftoff, {f.launch.utc} "
                f"± {f.launch.uncertainty_s:g} s ({f.launch.source})."
            ),
        )
    if f.weather_time_utc is not None:
        return GhostClock(
            t0=_utc(f.weather_time_utc),
            label="notebook weather hour",
            comment=(
                "Epoch 0 is the notebook's weather time (Environment date, UTC hour), "
                "not a recorded launch time."
            ),
        )
    return None
