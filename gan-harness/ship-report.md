# Ship report — Asteria

**Live:** not deployed — local-only by decision (brief: Deploy local-only).
**Verdict:** SHIPPED WITH GAPS (Rockets complete; Storm Ghost built, waiting for data).

| Gate | Result |
|------|--------|
| Acceptance, API (local) | 10/10 pass; 2 Storm Ghost scenarios skip until orbit data exists |
| Acceptance, UI (local, Playwright) | 13/13 pass: 4 behaviour + 9 layout (incl. 2 mission-replay) (no overlapping text, no sideways scroll, 3D view height, text ≥ 11px, at 1440, 1280, 1024, 768 and 390 px wide) |
| Engine: ruff / mypy --strict / pytest | pass / pass / 109 passed |
| Reproducible rebuild (fresh clone, fresh fetch) | 26/26 artifacts identical apart from timestamps |
| Web: tsc / eslint / next build | pass / pass / pass |
| Artifact integrity (`asteria verify`) | rockets 26/26 hashes match; source commit verified |
| Review findings open | 0 critical, 0 high (see below) |
| Dependency audit | Python: 133 packages, no known vulnerabilities (pip-audit). npm production: 0. npm dev: 5 high, all `braces` in eslint-config-next's linter plugin (GHSA-vfj7-8cjw-p6xm, no patched release; lints only our own config files) |
| Acceptance (live) | n/a — not deployed |

**Mocked or stubbed:** nothing in the product. Unit tests use two real NASA
OMNI records and a real ISS element set; synthetic inputs exist only inside
tests of pure geometry or rules and are named `TEST_ONLY_*`.

**Iterations:** built and audited in place (the earlier work in this workspace
was reviewed, kept and fixed rather than regenerated).

**Cut to Later:** Storm Ghost watch list, Storm Ghost 3D view (km-scale gaps are
invisible at globe scale), History showcase (Ghost of Apollo), Open MCT plugin,
Unreal photoreal replay, vehicle design optimiser, deploy.

**Manual steps left:**
1. Space-Track login in `engine/.env.local`, then `uv run asteria build-orbits`
   and restart the API. The first real run must be checked by eye, and the
   independent acceptance test run with `ASTERIA_SPACETRACK_FILE` set.
2. Optional Cesium ion token in `web/.env.local` (scope `assets:read`,
   allowed URL `http://localhost:3000`), then `npm run build`.

## Review notes

Done against the ship kit's `code-reviewer` / `security-reviewer` checklists
(the agents were not run as separate processes; the review was done in session).

Fixed during review:
- `engine/pyproject.toml` restored (a setup command overwrote it); Python floor
  raised to 3.11 (`datetime.UTC`).
- Halcyon was silently missing from the fleet; now excluded with measured evidence.
- Valkyrie and Hedy exclusion reasons corrected to the verified causes.
- Space-weather window counted the hour starting at the window's end (found by
  real OMNI data); regression test added.
- Acceptance tests: unset `ASTERIA_SOURCE_DIR` meant "current folder", so tests
  that should skip ran against the wrong folder.
- Console: camera framing, overlapping event labels, padded axis values shown
  as data, "−0.0", a no-WebGL crash taking down the whole console.
- React 19 rule: `useApi` no longer sets state synchronously in an effect.
- Rebuilds were not reproducible: RocketPy draws parachute trigger noise from
  unseeded `np.random` (GENESIS, NDRT descent differed by up to 0.46 m). The
  generator is now seeded before every notebook run and re-simulation;
  headline results unchanged; regression test added.

Accepted with reasons:
- Building Rockets artifacts executes RocketPy's notebook code (trust boundary,
  pinned and verified by commit hash).
- No Content-Security-Policy yet (Cesium needs workers, WebAssembly and tile hosts).
- HawkScan (DAST) not run: no `HAWK_API_KEY` in this environment.
