"""Reality Gap Map: where across the flight envelope physics and reality disagree.

Domain-agnostic: it bins (x, y, value) samples from many flights onto a fixed
grid and reports, per cell, how many samples and distinct flights back it.
A cell backed by fewer than `min_flights` flights is uncharted: it gets no
mean, so nothing is drawn where there is no evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from asteria.models import GapCell, GapMap

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class FlightSamples:
    flight_id: str
    x: FloatArray
    y: FloatArray
    value: FloatArray


def edges(start: float, stop: float, step: float) -> list[float]:
    n = round((stop - start) / step)
    return [round(start + i * step, 6) for i in range(n + 1)]


def build(
    samples: Sequence[FlightSamples],
    x_edges: list[float],
    y_edges: list[float],
    *,
    quantity: str,
    unit: str,
    coordinates: str,
    x_label: str,
    y_label: str,
    reach: Sequence[FlightSamples] = (),
    caveats: Sequence[str] = (),
    min_flights: int = 2,
) -> GapMap:
    """`samples` carry measured values; `reach` only says where fleet ghosts fly."""
    nx, ny = len(x_edges) - 1, len(y_edges) - 1
    xe, ye = np.asarray(x_edges), np.asarray(y_edges)

    def cells_of(s: FlightSamples) -> list[tuple[int, int, float]]:
        if not (s.x.shape == s.y.shape == s.value.shape):
            raise ValueError(f"{s.flight_id}: sample arrays differ in length")
        ix = np.searchsorted(xe, s.x, side="right") - 1
        iy = np.searchsorted(ye, s.y, side="right") - 1
        # The top edge belongs to the last cell; anything outside the grid is dropped.
        ix = np.where(s.x == xe[-1], nx - 1, ix)
        iy = np.where(s.y == ye[-1], ny - 1, iy)
        inside = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny) & np.isfinite(s.value)
        return [
            (int(i), int(j), float(v))
            for i, j, v in zip(ix[inside], iy[inside], s.value[inside], strict=True)
        ]

    buckets: dict[tuple[int, int], list[tuple[str, float]]] = {}
    for s in samples:
        for i, j, v in cells_of(s):
            buckets.setdefault((i, j), []).append((s.flight_id, v))
    ghosts: dict[tuple[int, int], set[str]] = {}
    for s in reach:
        for i, j, _ in cells_of(s):
            ghosts.setdefault((i, j), set()).add(s.flight_id)

    cells: list[GapCell] = []
    total = 0
    for i in range(nx):
        for j in range(ny):
            entries = buckets.get((i, j), [])
            flights = sorted({fid for fid, _ in entries})
            values = np.array([v for _, v in entries], dtype=np.float64)
            charted = len(flights) >= min_flights
            total += len(entries)
            cells.append(
                GapCell(
                    x_index=i,
                    y_index=j,
                    n_samples=len(entries),
                    n_flights=len(flights),
                    n_ghost_flights=len(ghosts.get((i, j), ())),
                    ghost_flights=sorted(ghosts.get((i, j), ())),
                    reachable=bool(ghosts.get((i, j))),
                    charted=charted,
                    mean=round(float(values.mean()), 3) if charted else None,
                    std=round(float(values.std(ddof=1)), 3)
                    if charted and values.size > 1
                    else None,
                    flights=flights,
                )
            )
    return GapMap(
        quantity=quantity,
        unit=unit,
        coordinates=coordinates,
        x_label=x_label,
        y_label=y_label,
        x_edges=x_edges,
        y_edges=y_edges,
        min_flights=min_flights,
        total_samples=total,
        flights_included=sorted({s.flight_id for s in samples}),
        caveats=list(caveats),
        cells=cells,
    )
