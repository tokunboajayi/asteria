# Spec: Asteria (MVP)

Asteria is mission control for the gap between prediction and reality.
A physics **ghost** flies first; the **real** flight is laid over it; the
**gap** is measured, mapped across the fleet, corrected (with honest
held-out evaluation), explained in grounded language, and used to choose
what to fly or watch next.

Scope cap (ship mode): one core loop, 6 features, 12 acceptance scenarios.

## Core loop

Select a flight → Ghost / Real / Δ state table + strip charts + 3D track →
events show where the gap opened → Reality Gap Map across the fleet →
correction toggle with held-out result → grounded debrief → Next Best Flight.

## Features

### F1 — Fleet of real flights with provenance (Rockets)
- Source: RocketPy repository, tag `v1.13.0`, commit
  `9bd6ad3af8f97bafa3201d4e70eba2877e66e040`, fetched by script with a
  commit check; every input file recorded with SHA-256.
- A flight is included only if its notebook executes headless offline at the
  pinned commit and it has a published real flight log. Exclusions are listed
  with the reason.
- **Ghost** = the `Flight` object built by RocketPy's own published notebook
  code, executed unmodified (magic lines stripped, plotting disabled).
  Labelled "post-flight reconstruction (reanalysis weather)".
- **Real** = the published flight log, loaded by the notebook's own
  `FlightDataImporter` call; raw samples kept, never extrapolated.
- **Team prediction** = the pre-flight apogee from the team's flight card,
  exactly as quoted in the notebook; stored with the verbatim quote and
  checked against the notebook text by a test. Absent → shown as "not published".

### F2 — Ghost vs Real vs Δ
- Ghost states on a uniform grid (ascent 0.05 s, descent 0.5 s): altitude
  AGL, vertical velocity, speed, Mach, dynamic pressure, latitude/longitude.
- Real states: every logged channel, raw.
- Δ computed only where both exist (overlap); outside it, Δ is null.
- Time base: the raw log keeps its published time base. For Δ and the gap
  map, the real log is aligned to the ghost at **liftoff** (first crossing of
  10 m AGL, linearly interpolated), because a logger's t = 0 is not the
  simulator's ignition time and a 0.5 s offset alone fakes a ~50 m/s
  velocity gap during boost. The offset is shown on screen. Apogee metrics
  and the correction do not depend on alignment.
- Events: ghost rail exit, burnout, max-Q, Mach 1 (if reached), apogee,
  parachute triggers (from RocketPy); real apogee (max of log).

### F3 — Reality Gap Map (fleet)
- Quantity: velocity gap Δvz = vz_real − vz_ghost (m/s), ascent only.
  vz_real is the derivative of the logged altitude via one fixed
  Savitzky–Golay filter (window 1.0 s, order 2) for **every** flight, so the
  method is identical across the fleet. *Revision log:* the first rule used
  the logger's own velocity when published; the smoke build showed single-
  sample spikes in one altimeter's velocity column dominating the result.
  Logged velocity, speed and acceleration are still shown as channels.
- Caveat shown with the map: barometric altitude can misread near the speed
  of sound, so transonic cells may hold sensor error as well as physics error
  (the smoke build found a logger whose own speed channel matched the ghost
  while its barometric altitude did not).
- Coordinates: ghost Mach (0.0–1.6, step 0.1) × ghost altitude AGL
  (0–4000 m, step 250 m), from the ghost state at the same time.
- Per cell: sample count, distinct flights, mean, std. Cells with fewer than
  2 distinct flights are **uncharted** and shown hatched with no colour.
- Flights whose altitude log is coarser than 0.2 s median sample interval
  are kept out of the map (velocity cannot be resolved); they still count
  for apogee and the correction.

### F4 — Bounded learned correction (pre-registered)
- Per flight i, find the drag scale k_i such that the ghost apogee matches
  the real apogee (re-simulate with both drag curves multiplied by k;
  bracketed root find, k ∈ [0.5, 1.5]).
- Fleet model (fixed before any results): **k̂ = median of the other
  flights' k, clipped to [0.8, 1.2]**. No other model is tried.
- Evaluation: leave-one-flight-out. The held-out flight's own k is never
  used for its own correction. Report per flight and in aggregate (median
  absolute apogee error % before vs after). Whatever the result, it is shown.
- "Corrected" track = full re-simulation at the held-out k̂.
- Toggle in the UI: pure physics ↔ corrected.

### F5 — Grounded debrief (no API key)
- Code builds a numbered facts packet per flight (F1…Fn: label, value,
  unit, source path).
- Debrief sentences are rendered from templates; each cites fact IDs.
- Validator: every number in a sentence must equal a cited fact's
  formatted value; a sentence citing a missing fact or carrying an
  unmatched number is rejected. Optional Claude adapter
  (`ANTHROPIC_API_KEY`) passes through the same validator, falling back to
  templates on failure.

### F6 — Next Best Flight
- Score each envelope cell: value = prior variance / (1 + distinct flights),
  prior variance = max cell variance observed in the fleet; charted cells use
  their observed variance.
- Candidates are **reachable** cells only: at least one fleet ghost's ascent
  passes through them. *Revision log (before the full-fleet build):* the first
  rule allowed any cell next to a charted one; a 3-flight smoke build showed it
  can pick cells no climbing rocket can occupy (Mach < 0.5 at 250–500 m).
- Recommend the contiguous top-scoring band as a target envelope (Mach and
  altitude ranges), plus the nearest flown flight to that band.
- States plainly that Asteria names the envelope; it does not yet design
  the vehicle.

### F7 — Storm Ghost (Orbits) — gated on Space-Track credentials
- Ghost: SGP4 propagation from the last element set before storm onset.
- Real: later Space-Track element sets for the same object, evaluated at
  their own epochs ("tracking-based orbit fit").
- Gap: along-track / radial / cross-track difference (km) vs time.
- Storm: NASA SPDF OMNI hourly Kp, Dst, F10.7 for the same window.
- Gap map axes: Kp × altitude. Watch list: objects in uncharted cells.
- Until credentials exist, the Orbits tab says so; no placeholder data.

## Non-functional

- Python engine typed (mypy), linted (ruff), unit tested; API typed with
  pydantic; TypeScript types generated from the API's OpenAPI schema.
- No number in the UI without a source path reachable from the provenance
  panel.
- Console works at 1280–1920 px; usable at phone width (stacked).
- Accessible: real buttons, labels, 4.5:1 contrast for text.

## Later
History (Ghost of Apollo), Open MCT plugin, Unreal replay, live ingest,
vehicle design optimiser, accounts, deploy.
