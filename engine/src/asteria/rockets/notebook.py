"""Execute a pinned RocketPy example notebook, unmodified, and keep its objects.

The ghost must be RocketPy's own published reconstruction, not our retyping
of it. So we run the notebook's code cells as published, with only these
mechanical changes, all recorded:

* IPython magic lines (``%...`` / ``!...``) are removed — they are not Python.
* Plotting is sent to a non-interactive backend and ``plt.show`` is a no-op.
* Cells listed in the catalog's ``skip_cells`` are not run; each skip carries
  a written reason and is reported in the build log.

Every ``Flight(...)`` constructed while the notebook runs is recorded with
the exact arguments it was given, so it can be re-simulated later (for the
drag-scale correction) with nothing changed except the drag curve.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FLIGHT_ARGS_ATTR = "_asteria_init_kwargs"


@dataclass
class CellRecord:
    index: int
    seconds: float
    skipped_reason: str | None = None
    magics_removed: int = 0


@dataclass
class NotebookRun:
    notebook: str
    namespace: dict[str, Any]
    cells: list[CellRecord] = field(default_factory=list)

    def get(self, name: str) -> Any:
        if name not in self.namespace:
            raise KeyError(f"{self.notebook}: notebook did not define {name!r}")
        return self.namespace[name]


class NotebookError(RuntimeError):
    def __init__(self, notebook: str, cell: int, cause: BaseException) -> None:
        super().__init__(f"{notebook} cell {cell}: {type(cause).__name__}: {cause}")
        self.cell = cell


def code_cells(notebook_path: Path) -> list[tuple[int, str]]:
    """(cell index in the notebook, source) for every code cell."""
    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    return [
        (i, "".join(c["source"])) for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code"
    ]


def markdown_text(notebook_path: Path) -> str:
    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")


def _strip_magics(source: str) -> tuple[str, int]:
    kept, removed = [], 0
    for line in source.splitlines():
        if line.lstrip().startswith(("%", "!")):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


@contextlib.contextmanager
def _headless_plotting() -> Iterator[None]:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    original_show = plt.show
    plt.show = lambda *a, **k: None
    try:
        yield
    finally:
        plt.show = original_show
        plt.close("all")


@contextlib.contextmanager
def _recording_flight() -> Iterator[type]:
    """Swap rocketpy.Flight for a subclass that remembers its arguments."""
    import rocketpy
    import rocketpy.simulation
    import rocketpy.simulation.flight as flight_module

    original = flight_module.Flight
    signature = inspect.signature(original.__init__)

    class RecordingFlight(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            recorded = {k: v for k, v in bound.arguments.items() if k != "self"}
            setattr(self, FLIGHT_ARGS_ATTR, recorded)
            super().__init__(*args, **kwargs)

    RecordingFlight.__name__ = "Flight"
    RecordingFlight.__qualname__ = "Flight"
    targets = (rocketpy, rocketpy.simulation, flight_module)
    for module in targets:
        module.Flight = RecordingFlight
    try:
        yield original
    finally:
        for module in targets:
            module.Flight = original


@contextlib.contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def run_notebook(
    checkout: Path, notebook_rel: str, skip_cells: dict[int, str] | None = None
) -> NotebookRun:
    """Run every code cell of `notebook_rel` (relative to `checkout`).

    Must run in its own process: it changes the working directory and patches
    `rocketpy.Flight` for the duration of the call.
    """
    skip_cells = skip_cells or {}
    notebook_path = checkout / notebook_rel
    run = NotebookRun(notebook=notebook_rel, namespace={"__name__": "__asteria_notebook__"})
    cells = code_cells(notebook_path)
    unknown = set(skip_cells) - {i for i, _ in cells}
    if unknown:
        raise ValueError(f"{notebook_rel}: skip_cells {sorted(unknown)} are not code cells")
    sink = io.StringIO()
    with (
        _working_directory(notebook_path.parent),
        _headless_plotting(),
        _recording_flight(),
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
    ):
        for index, source in cells:
            if index in skip_cells:
                run.cells.append(CellRecord(index, 0.0, skipped_reason=skip_cells[index]))
                continue
            code, removed = _strip_magics(source)
            start = time.perf_counter()
            try:
                exec(compile(code, f"{notebook_rel}#cell{index}", "exec"), run.namespace)
            except Exception as exc:
                raise NotebookError(notebook_rel, index, exc) from exc
            finally:
                import matplotlib.pyplot as plt

                plt.close("all")
            run.cells.append(CellRecord(index, time.perf_counter() - start, magics_removed=removed))
    return run


def flight_init_kwargs(flight: Any) -> dict[str, Any]:
    """The exact arguments a recorded Flight was constructed with."""
    kwargs = getattr(flight, FLIGHT_ARGS_ATTR, None)
    if kwargs is None:
        raise ValueError("flight was not constructed under run_notebook()")
    return dict(kwargs)
