# Third-party data and software

Asteria's own code is under the MIT licence (see LICENSE). It uses:

## Rocket flights

- **RocketPy** (MIT licence, © 2018 Giovani Hidalgo Ceotto and contributors),
  tag v1.13.0, commit `9bd6ad3af8f97bafa3201d4e70eba2877e66e040`:
  the simulation library, its example notebooks, motor files and the flight
  logs it publishes. https://github.com/RocketPy-Team/RocketPy
- Flight data published in RocketPy's repository with each team's permission,
  as recorded in the notebooks:
  - Andromeda: Aristotle Space and Aeronautics Team (permission: Antoniadis Panos, 2024)
  - Astra and GENESIS: Faraday Rocketry UPV (permission: Nacho Coello, 2024)
  - Bella Lui: EPFL Rocket Team (permission: Antoine Scardigli, 2020)
  - Camões: Rocket Experiment Division (permission: Gonçalo Machado, 2024)
  - Cavour: PoliTo Rocket Team (permission: Edoardo Viglietti, 2024)
  - EREBUS-11: BME Suborbitals Rocket Team (permission: Tomi, 2024)
  - Juno III: Projeto Jupiter, University of São Paulo (permission: Juliana Carloni, 2023)
  - Lince: Student Team for Aerospace and Rocketry UC3M (permission: Saúl Hidalgo, 2024)
  - NDRT 2020: Notre Dame Rocket Team (permission: Brooke Mumma, 2020)
  - Prometheus: Western Engineering Rocketry Team (permission: Giorgio Chassikos, 2024)
- Reanalysis weather files in RocketPy's repository are ECMWF ERA5 data:
  contains modified Copernicus Climate Change Service information.

## Orbits

- **Space-Track.org** (US Space Force): historical element sets. Used under
  the Space-Track user agreement; raw data is not redistributed.
- **NASA OMNI2** hourly data, NASA Goddard Space Flight Center, Space Physics
  Data Facility: https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/
- **CelesTrak**: used once to check the satellite catalog numbers.
- **sgp4** Python package (MIT licence), Brandon Rhodes, implementing
  Vallado et al.'s SGP4.

## Console

- **CesiumJS** (Apache-2.0). Imagery without a token: Esri World Imagery
  (Esri, Maxar, Earthstar Geographics), under Esri's terms of use. With a
  Cesium ion token: Cesium ion terms apply.
- Next.js and React (MIT); IBM Plex fonts (SIL Open Font Licence).
