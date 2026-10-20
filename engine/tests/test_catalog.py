"""The fleet catalog must match the pinned sources word for word."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from asteria.rockets import catalog
from asteria.rockets.notebook import code_cells, markdown_text


def test_ids_unique_and_slugged() -> None:
    ids = [s.id for s in catalog.FLEET]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)


@pytest.mark.parametrize(
    ("quote", "value", "decimals"),
    [
        ("Official recorded apogee: `3443 m`", 3443.0, 0),
        ("Last simulated apogee before flight: `3026.054 m`", 3026.054, 3),
        ("Measured Altitude 4,320 ft or 1316.736 m", 1316.736, 3),
        ("**Last Simulated Apogee:** 4190.05 m", 4190.05, 2),
    ],
)
def test_metres_parsed_from_quote(quote: str, value: float, decimals: int) -> None:
    assert catalog.metres_in_quote(quote) == value
    assert catalog.metre_decimals(quote) == decimals


def test_quote_without_metres_is_rejected() -> None:
    with pytest.raises(ValueError):
        catalog.metres_in_quote("Official Target Altitude 4,444 ft")


@pytest.mark.parametrize("spec", catalog.FLEET, ids=lambda s: s.id)
def test_quotes_are_verbatim_in_pinned_notebook(spec: catalog.FlightSpec, checkout: Path) -> None:
    text = markdown_text(checkout / spec.notebook)
    assert spec.title_quote in text
    for quote in (spec.team_prediction_quote, spec.official_apogee_quote):
        if quote is not None:
            assert quote in text, quote


@pytest.mark.parametrize("spec", catalog.FLEET, ids=lambda s: s.id)
def test_team_prediction_is_explicitly_pre_flight(spec: catalog.FlightSpec) -> None:
    if spec.team_prediction_quote is not None:
        assert re.search(r"before flight|last simulated", spec.team_prediction_quote, re.I)


@pytest.mark.parametrize("spec", catalog.FLEET, ids=lambda s: s.id)
def test_declared_columns_exist(spec: catalog.FlightSpec, checkout: Path) -> None:
    with (checkout / spec.log.path).open(newline="", encoding="utf-8-sig") as fh:
        header = next(csv.reader(fh, delimiter=spec.log.delimiter))
    for col in (spec.log.time_column, spec.log.altitude_column, *(c.column for c in spec.log.extra)):
        assert col in header, col
    if spec.gnss is not None:
        with (checkout / spec.gnss.path).open(newline="", encoding="utf-8-sig") as fh:
            gheader = next(csv.reader(fh))
        for col in (spec.gnss.time_column, spec.gnss.latitude_column, spec.gnss.longitude_column):
            assert col in gheader, col


@pytest.mark.parametrize("spec", catalog.FLEET, ids=lambda s: s.id)
def test_variables_are_defined_by_the_notebook(spec: catalog.FlightSpec, checkout: Path) -> None:
    source = "\n".join(src for _, src in code_cells(checkout / spec.notebook))
    assert re.search(rf"\b{spec.flight_var}\s*=\s*Flight\(", source)
    if spec.importer_var is not None:
        assert re.search(rf"\b{spec.importer_var}\s*=\s*FlightDataImporter\(", source)
    for index in spec.skip_cells:
        assert index in {i for i, _ in code_cells(checkout / spec.notebook)}


def test_exclusions_point_at_real_notebooks(checkout: Path) -> None:
    for e in catalog.EXCLUDED:
        assert (checkout / e.notebook).is_file(), e.notebook
        assert e.reason.strip()
    fleet_notebooks = {s.notebook for s in catalog.FLEET}
    assert not fleet_notebooks & {e.notebook for e in catalog.EXCLUDED}


def test_every_example_notebook_is_used_or_excluded(checkout: Path) -> None:
    examples = {
        p.relative_to(checkout).as_posix() for p in (checkout / "docs/examples").glob("*.ipynb")
    }
    accounted = {s.notebook for s in catalog.FLEET} | {e.notebook for e in catalog.EXCLUDED}
    assert examples == accounted, examples ^ accounted
