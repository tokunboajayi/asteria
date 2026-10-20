"""Grounded debrief: sentences may only carry numbers from the facts they cite.

`validate` is the single gate every sentence passes, whether a template or a
language model wrote it. A rejected sentence is dropped and counted; it is
never repaired by guessing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from asteria.models import Fact, Sentence, Validation

NUMBER = re.compile(r"[-−+]?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[str]:
    return NUMBER.findall(text)


def check_sentence(sentence: Sentence, facts: dict[str, Fact]) -> str | None:
    """None if grounded, else the reason it is not."""
    if not sentence.fact_ids:
        return "cites no facts"
    allowed: set[str] = set()
    for fid in sentence.fact_ids:
        fact = facts.get(fid)
        if fact is None:
            return f"cites unknown fact {fid}"
        allowed.update(numbers_in(fact.display))
        allowed.update(numbers_in(fact.label))
    for number in numbers_in(sentence.text):
        if number not in allowed:
            return f"number {number!r} is not in its cited facts"
    return None


def validate(
    candidates: Sequence[Sentence], facts: Sequence[Fact]
) -> tuple[list[Sentence], Validation]:
    by_id = {f.id: f for f in facts}
    kept: list[Sentence] = []
    notes: list[str] = []
    for s in candidates:
        reason = check_sentence(s, by_id)
        if reason is None:
            kept.append(s)
        else:
            notes.append(f"rejected: {reason}: {s.text}")
    passed = bool(kept) and len(kept) == len(candidates)
    return kept, Validation(passed=passed, rejected=len(candidates) - len(kept), notes=notes)
