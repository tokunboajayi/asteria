# Evaluation rubric — Asteria

acceptance_gate: required

Any failing acceptance scenario caps the total at 5.0.

| Criterion | Weight | 10 means |
|---|---|---|
| Functionality | 0.45 | All 12 acceptance scenarios pass; every number in the UI matches the API, and the API matches the raw published files. |
| Craft | 0.25 | Typed end to end (mypy, pydantic, generated TS types); no dead code; modules with one job each; unit tests on every computation; reproducible from a clean checkout with one command. |
| Design | 0.20 | Reads as a flight-dynamics console: dense, legible telemetry, event markers on a shared time axis, uncertainty and provenance visible; contrast ≥ 4.5:1; usable at phone width. |
| Originality | 0.10 | Ghost-vs-reality loop, held-out correction and Next Best Flight presented as one coherent instrument, not a generic dashboard. |

## Integrity checks (any failure caps total at 3.0)

- A number shown as measured that does not come from a published log.
- A real position drawn where the log has no position data.
- The correction evaluated in-sample (held-out flight's own k used).
- A debrief sentence with a number not present in its cited facts.
