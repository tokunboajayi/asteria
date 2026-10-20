# Brief: Asteria

**Idea (verbatim):** "a rocket that remembers every flight it has ever taken" —
mission control for the gap between prediction and reality: a physics ghost,
the real flight, the gap mapped and learned, and the next flight chosen to
teach the model the most.

**User:** rocketry and space-operations engineers (and the judges and hiring
managers evaluating them) · **Job:** see exactly where physics predictions
diverge from reality, and decide what to fly or watch next.

**Core loop:** pick a flight → see Ghost vs Real vs Δ for every state →
see where the gap opened (events + Reality Gap Map) → toggle the learned
correction and see its held-out effect → read the grounded debrief →
see the Next Best Flight / Watch List.

**Stack:** `next-fastapi` (Python engine + FastAPI, Next.js console) ·
**Features:** none required (`ai` optional, off by default)
**Deploy:** local-only

## Locked decisions

1. **Real published data only.** Rockets: the flight logs, rocket
   definitions and reanalysis weather published in RocketPy's repository at
   tag `v1.13.0` (commit `9bd6ad3af8f97bafa3201d4e70eba2877e66e040`).
   Orbits: Space-Track element sets (US Space Force) + NASA SPDF OMNI
   space-weather indices. No synthetic data is ever presented as measured.
2. **Every number traces to a source.** Each artifact records source file,
   pinned commit or download time, and SHA-256. Anti-forgery tests recompute
   headline numbers independently from raw files.
3. **Ghost = RocketPy's own published reconstruction**, executed from the
   pinned notebook code — never retyped by us. Labelled honestly as a
   post-flight reconstruction with reanalysis weather, not a pre-flight
   prediction. The team's pre-flight apogee (from their flight card, as
   quoted in the notebook) is shown separately when published.
4. **Physics computes, the learned model corrects, language only explains.**
   The correction is bounded, evaluated leave-one-flight-out, reported
   whatever the result is, and can be switched off.
5. **No position is ever invented.** Flights with altitude-only logs show the
   real flight as altitude data, not as a fabricated 3D path.
6. **No API key required.** Debriefs are rendered from a numbered facts
   packet and validated (every number must exist in the packet). A Claude
   adapter is optional behind `ANTHROPIC_API_KEY` and goes through the same
   validator.
7. **No database in the MVP.** Inputs are immutable published files;
   outputs are versioned JSON artifacts with checksums. (Deviation from the
   `next-fastapi` playbook's Postgres, recorded here on purpose.)

## Success looks like

- The console lists the fleet of real flights with provenance on each.
- For any flight, the real apogee shown equals the maximum of the raw
  published log, and Ghost/Real/Δ are shown for every logged state.
- The Reality Gap Map, the correction's held-out result and the Next Best
  Flight are computed from the fleet, with empty (uncharted) cells marked.
- Every debrief sentence cites fact IDs, and every number in it exists in
  the facts packet.
- Storm Ghost shows predicted vs later-tracked orbits across a real
  geomagnetic storm, with NASA OMNI indices (blocked on Space-Track login).

## Later (out of MVP)

History showcase (Ghost of Apollo), Open MCT plugin, photoreal Unreal
replay, live telemetry ingest, accounts, deploy.

## Credentials needed

- Rockets: none.
- Orbits: `SPACETRACK_USER`, `SPACETRACK_PASSWORD` (space-track.org, free).
- Optional: `ANTHROPIC_API_KEY`, `CESIUM_ION_TOKEN` (terrain).

## Preflight (2026-10-20)

`preflight.js --stack next-fastapi --local-only` → CLIs node, npm, git,
python, uv all present. Only `DATABASE_URL` reported missing, which is the
playbook's Postgres requirement this project removes on purpose (locked
decision 7). Rockets phase: ready. Orbits phase: blocked until
`SPACETRACK_USER` / `SPACETRACK_PASSWORD` exist in `.env.local`.
