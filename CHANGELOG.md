# Changelog

## 0.2.0 (2026-10-30)

### Added
- **Storm density measured from orbit decay** for 12 satellites, with error bars,
  over the storm's main phase and recovery.
- **Independent check against GRACE-FO 1's accelerometer** (ESA, optional): agrees
  with the decay method within 1 sigma; the acceptance suite enforces 3 sigma.
- **Real launch time** from a flight log's own GPS clock (Prometheus: 2022-06-24
  15:17:17.5 UTC ± 0.44 s). The console flags the notebook's weather being a year off.
- **Launch-day weather re-fly** (Copernicus ERA5, optional), gated by a control
  that must reproduce the notebook apogee within 1 m.
- **Fleet band**: each ghost re-flown at the drag factors the other flights
  needed; coverage counted (9 of 11, expected 9.0).
- **Exports**: CCSDS OEM (orbits in TEME with velocities; rocket ghosts
  Earth-fixed) and a NASA Open MCT dictionary and telemetry.
- **Deployment**: API and console Docker images, docker-compose, CI image build
  with a no-secrets check; `asteria fetch-data` for the optional data.

### Changed
- `/ready` (503 until artifacts load) for orchestrators; `/health` now says why
  data failed to load. Artifacts from 0.1.0 must be rebuilt.
- NRLMSIS model comparison is **optional and off by default** (`model` extra,
  `ASTERIA_DENSITY_MODEL`): NRL licenses MSIS2 for non-commercial use only.
- One Space-Track element set per epoch (the latest issue).

### Removed
- Earlier "Monte Carlo 3-sigma" tube, density formula and synthetic orbit arc:
  they showed numbers not computed from data. Replaced by the items above.

## 0.1.0 (2026-10-29)
- First public release: RocketPy ghosts vs. 11 real flights, Storm Ghost orbits,
  event timing, fingerprint, mission replay, held-out correction.
