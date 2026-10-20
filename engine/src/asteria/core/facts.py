"""Numbered facts: the only numbers any debrief sentence may use."""

from __future__ import annotations

from dataclasses import dataclass, field

from asteria.models import Fact

MINUS = "−"  # typographic minus, used everywhere a number is negative


def _signed(text: str, value: float, always_sign: bool) -> str:
    if value < 0:
        return MINUS + text.lstrip("-")
    return ("+" + text) if always_sign and value > 0 else text


def fmt_m(value: float, digits: int = 1) -> str:
    return _signed(f"{abs(value):,.{digits}f}", value, False) + " m"


def fmt_delta_m(value: float) -> str:
    return _signed(f"{abs(value):,.1f}", value, True) + " m"


def fmt_pct(value: float) -> str:
    return _signed(f"{abs(value):.1f}", value, True) + "%"


def fmt_plain(value: float, digits: int) -> str:
    return _signed(f"{abs(value):.{digits}f}", value, False)


def fmt_signed_unit(value: float, digits: int, unit: str) -> str:
    return _signed(f"{abs(value):,.{digits}f}", value, True) + f" {unit}"


@dataclass
class FactSheet:
    """Builds facts F1, F2, … in insertion order."""

    facts: list[Fact] = field(default_factory=list)

    def add(self, label: str, value: float, unit: str, display: str, source: str) -> str:
        fid = f"F{len(self.facts) + 1}"
        self.facts.append(
            Fact(id=fid, label=label, value=value, unit=unit, display=display, source=source)
        )
        return fid

    def display(self, fid: str) -> str:
        for f in self.facts:
            if f.id == fid:
                return f.display
        raise KeyError(fid)
