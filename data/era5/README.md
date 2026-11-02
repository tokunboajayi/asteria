# ERA5 pressure levels, Spaceport America

Two days of ERA5 hourly data on pressure levels (geopotential, temperature, u and v
wind; 37 levels; 36.75°N–29°N, 108.875°W–105.125°W at 0.25°), the same box, levels and
variables as RocketPy's `spaceport_america_pressure_levels_2023_hourly.nc`:

| File | Use |
|---|---|
| `spaceport_america_era5_pl_2022-06-24.nc` | Prometheus's real launch day: the launch-day weather re-fly |
| `spaceport_america_era5_pl_2023-06-24.nc` | Control: the notebook's own date, which must reproduce the notebook apogee within 1 m |

Downloaded from the Copernicus Climate Data Store (dataset
`reanalysis-era5-pressure-levels`) with `uv run asteria fetch-data`, and kept here so the
public demo can be rebuilt without an account.

**Licence:** CC-BY 4.0. Contains modified Copernicus Climate Change Service information
(2022, 2023). Neither the European Commission nor ECMWF is responsible for any use that
may be made of the Copernicus information or data it contains.

Hersbach, H. et al. (2023): ERA5 hourly data on pressure levels from 1940 to present.
Copernicus Climate Change Service (C3S) Climate Data Store (CDS), DOI: 10.24381/cds.bd0915c6
