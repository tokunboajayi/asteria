"""Next Best Flight: the part of the envelope where one more flight teaches most.

Rule (spec F6, fixed before results):
* Each cell's uncertainty is its observed variance when charted, else the
  prior variance (the largest variance observed anywhere in the map).
* value = variance / (1 + distinct flights in the cell).
* Candidates are the reachable cells: at least one fleet ghost's ascent
  passes through them, so a vehicle of the kind already flown can get there.
  (Revised from a "frontier" rule before the full-fleet build: the frontier
  could pick cells no rocket can occupy while climbing, e.g. very low Mach at
  low altitude.)
* The target is the bounding box of the largest connected group of
  top-value candidates (ties: lower x first, i.e. the cheaper flight).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from asteria.models import GapCell, GapMap, NearestFlight, NextBest, NextBestTarget

RATIONALE = (
    "Rockets like the ones in the fleet fly through these cells, but too few real logs "
    "have measured them, so one more flight there removes more uncertainty than anywhere else."
)
LIMITATION = "Asteria names the envelope to fly; it does not yet design the vehicle that flies it."


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    max_x: float


def _neighbours(i: int, j: int) -> list[tuple[int, int]]:
    return [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)]


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    seen: set[tuple[int, int]] = set()
    groups = []
    for start in sorted(cells):
        if start in seen:
            continue
        group, stack = set(), [start]
        while stack:
            c = stack.pop()
            if c in seen or c not in cells:
                continue
            seen.add(c)
            group.add(c)
            stack.extend(_neighbours(*c))
        groups.append(group)
    return groups


def recommend(gap: GapMap, flights: Sequence[Candidate]) -> NextBest:
    grid: dict[tuple[int, int], GapCell] = {(c.x_index, c.y_index): c for c in gap.cells}
    charted = {k for k, c in grid.items() if c.charted}
    if not charted:
        raise ValueError("no charted cells: nothing to extend from")
    variances = [grid[k].std ** 2 for k in charted if grid[k].std is not None]  # type: ignore[operator]
    prior = max(variances) if variances else 1.0

    def value(k: tuple[int, int]) -> float:
        c = grid[k]
        var = c.std**2 if c.charted and c.std is not None else prior
        return var / (1 + c.n_flights)

    reachable = {k for k, c in grid.items() if c.reachable}
    if not reachable:
        raise ValueError("no reachable cells: the fleet ghosts never enter the grid")
    best = max(value(k) for k in reachable)
    top = {k for k in reachable if abs(value(k) - best) <= 1e-12 * max(1.0, best)}
    group = sorted(_components(top), key=lambda g: (-len(g), min(i for i, _ in g)))[0]
    xs = [i for i, _ in group]
    ys = [j for _, j in group]
    target = NextBestTarget(
        mach=(gap.x_edges[min(xs)], gap.x_edges[max(xs) + 1]),
        alt_m=(gap.y_edges[min(ys)], gap.y_edges[max(ys) + 1]),
    )
    through = sorted({fid for k in group for fid in grid[k].ghost_flights})
    by_id = {f.id: f for f in flights}
    if through:
        # A flight whose own ghost already flies through the target envelope.
        nearest = by_id[through[0]]
    else:
        nearest = min(flights, key=lambda f: (abs(f.max_x - target.mach[0]), f.id))
    return NextBest(
        target=target,
        score=round(best, 6),
        cells=sorted(group),
        ghost_flights=through,
        nearest_flight=NearestFlight(
            id=nearest.id, name=nearest.name, max_mach_ghost=nearest.max_x
        ),
        rationale=RATIONALE,
        limitation=LIMITATION,
    )
