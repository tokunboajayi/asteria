# Test data

Real excerpts only; each file says where it came from.

- `omni2_2024_day132_h00_h03.dat` — two records copied verbatim from
  NASA GSFC SPDF `omni2_2024.dat`
  (https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_2024.dat),
  2024 day 132 (11 May) hours 00 and 03 UTC, the peak of the May 2024
  geomagnetic storm. Downloaded 2026-10-20.

Synthetic inputs used to test pure geometry or a rule are built inside the
test that uses them and are named `TEST_ONLY_*`; they are never artifacts.
