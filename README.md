# Asteria

**Mission control for the gap between prediction and reality.**

A physics *ghost* flies first. The *real* flight is laid over it. Asteria
measures the gap, maps where across the flight envelope it opens, tests a
learned correction on flights it has never seen, explains each flight in
language that can only use checked numbers, and names the flight that would
teach the model the most.

- **Rockets** (built): 11 real high-power rocket flights from university teams.
  The ghost is RocketPy's own published reconstruction of each flight, run
  unmodified; the reality is each team's published flight log.
- **Orbits · Storm Ghost** (built, waiting for data): SGP4 orbit ghosts vs.
  later tracking across the May 2024 geomagnetic storm, with NASA OMNI
  space-weather indices. Needs a free Space-Track.org login (see below).

## What the data says (Rockets)

Numbers below are read from the built artifacts (`.asteria/artifacts/rockets`).

| | Result |
|---|---|
| Flights | 11 real flights, 2020–2023 (EuRoC, Spaceport America Cup, EPFL, Notre Dame) |
| Physics ghost vs. real apogee | median absolute error **5.2%**; range −10.5% to +7.4% |
| Fleet drag correction, tested leave-one-flight-out | median absolute error **6.5%**: worse; 6 flights closer, 5 further |
| Reality Gap Map | 9 flights with fine-grained logs, 3,783 ascent samples, 40 charted cells |

The headline finding is honest and negative: **a single fleet-wide drag
correction does not transfer between rockets.** Each rocket's error is its
own. The correction model was fixed before any result was seen and no other
model was tried afterwards, so the result is not tuned to the data.

## Run it (Windows, PowerShell)

You need **Git**, **Node.js 20+** and **uv** (which installs Python for you):

```powershell
winget install Git.Git OpenJS.NodeJS.LTS
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then, from this folder, in two terminals:

```powershell
# Terminal 1: the engine API (serves the prebuilt, hash-verified artifacts)
cd engine
uv sync
uv run asteria serve
```

```powershell
# Terminal 2: the flight console
cd web
npm install
npm run build
npm start
```

Open **http://localhost:3000**.

The prebuilt Rockets artifacts are included in `.asteria/artifacts`. To rebuild
them yourself from the pinned sources (about a minute; downloads ~170 MB of
RocketPy data on first run):

```powershell
cd engine
uv run asteria build     # fetches RocketPy v1.13.0 at its pinned commit, then builds
uv run asteria verify    # re-checks the commit and every artifact hash
```

### Optional keys (never commit these files)

| File | Variable | What it does |
|---|---|---|
| `web/.env.local` | `NEXT_PUBLIC_CESIUM_ION_TOKEN` | Real terrain + aerial imagery on the 3D globe. This token is sent to the browser by design: in your Cesium ion account give it only the `assets:read` scope and allow only `http://localhost:3000`. Rebuild (`npm run build`) after adding it. |
| `engine/.env.local` | `SPACETRACK_USER`, `SPACETRACK_PASSWORD` | Unlocks Storm Ghost. Free account at space-track.org. Then run `uv run asteria build-orbits` and restart the API. |

Copy `web/.env.example` and `engine/.env.example` to start.

## How it is built

```
engine/   Python: RocketPy + SGP4 engine, pydantic data contract, read-only FastAPI
web/      Next.js 16 + React 19 console, Cesium 1.146 globe, types generated from the API
gan-harness/
  brief.md, spec.md, eval-rubric.md   the locked brief and the pre-registered rules
  acceptance/                          tests written before the code (API + UI)
docs/contrast.md                       computed WCAG contrast for every text colour
```

- **Physics computes, the learned model corrects, language only explains.**
- The engine builds everything into JSON artifacts with a SHA-256 manifest. The
  API refuses to serve anything that does not match its manifest.
- The console reads only the API. Its TypeScript types are generated from the
  API's OpenAPI schema, so the two cannot drift.

## Data integrity rules (enforced by code, not by promise)

1. **Real published data only.** Rockets: RocketPy repository, tag `v1.13.0`,
   commit `9bd6ad3af8f97bafa3201d4e70eba2877e66e040`, fetched and checked by
   commit hash. Orbits: Space-Track element sets and NASA OMNI.
2. **The ghost is never retyped.** Each flight's ghost comes from executing
   RocketPy's own notebook code; a re-simulation must reproduce the notebook's
   apogee or the build stops.
3. **Asteria's loader must match RocketPy's importer exactly** on every flight
   that has one, or the build stops.
4. **Every quote is verbatim.** Team predictions and flight-card apogees are
   matched character for character against the notebook text.
5. **No invented positions.** A flight with altitude-only logs gets no real 3D
   path; only GNSS-logged flights show one.
6. **Every exclusion has a written, checked reason.** Five notebooks are not
   used (no log published, live web services, a broken data path, and one hybrid
   motor too expensive to rebuild as published); the reasons are in the console's
   provenance panel.
7. **Every debrief number is checked.** A sentence may only contain numbers from
   the facts it cites; otherwise it is rejected, never repaired.
8. **Independent acceptance tests** re-read the raw files themselves (without
   importing the engine) and compare them with what the API serves.
9. **Rebuilds are reproducible.** RocketPy's parachute trigger noise is
   drawn from a fixed seed, so a fresh build matches the shipped artifacts.

## Checks

```powershell
cd engine;  uv run ruff check . ; uv run mypy src ; uv run pytest      # 93 unit tests
cd web;     npm run typecheck ; npm run lint
# Acceptance (API and console running):
$env:API_URL="http://127.0.0.1:8000"; $env:ASTERIA_SOURCE_DIR="..\.asteria\cache\rocketpy-9bd6ad3af8f9"
engine\.venv\Scripts\python -m pytest gan-harness\acceptance\test_api.py
cd web; npx playwright install chromium; npm run test:acceptance
```

## Security

- The API is read-only (GET), binds to `127.0.0.1` by default, and allows
  cross-origin requests only from the console's own origin.
- **Trust boundary:** building the Rockets artifacts executes code from
  RocketPy's example notebooks. Asteria only runs it from a clean checkout of
  the pinned commit (verified by hash before every build).
- Space-Track passwords are read from `engine/.env.local` or the environment,
  sent only to Space-Track's login endpoint, and never logged. Raw Space-Track
  data stays on your machine; its user agreement forbids redistribution.
- No Content-Security-Policy is set yet: Cesium needs workers, WebAssembly and
  tile hosts, and a wrong policy breaks the globe. Basic headers
  (`nosniff`, `no-referrer`, `DENY` framing) are set.

## Limits

- The ghost is a **post-flight reconstruction** with reanalysis weather, not
  the team's pre-flight prediction (shown separately where published).
- Barometric altimeters can misread near the speed of sound; transonic gap
  cells may hold sensor error as well as physics error.
- Storm Ghost's tracked orbits are orbit fits to tracking data, not direct
  measurements. Its view has not been checked against real data until a
  Space-Track login is added.
- Next Best Flight names the envelope to fly; it does not design the vehicle.

## Credits

See [NOTICE.md](NOTICE.md) for every data source, its licence and the teams
whose flights are used.
