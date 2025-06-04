# Changelog

## 0.17.2 – 2025-05-08

- Updated tests for **Atlas v2**.
- Fixed dashboard for latest `bokeh >= 3.7`.

## 0.17.1 – 2025-05-06

- Fixed calendar bug for **proleptic Gregorian** calendar.

## 0.17.0 – 2025-04-29

- Added support for **Atlas v2** data.

## 0.16.1 – 2025-02-26

- Fixed smoke tests.
- Added `beautifulsoup` to requirements.

## 0.16.0 – 2025-02-21

- Switched to **pooch** for test data management.
- Modernized Python code and deployment.
- Removed `roocs-utils`. Now requires:
  - `clisops >= 0.15.0`
  - `daops >= 0.14.0`
- Replaced linting setup with **ruff**.
- Changed default Git branch to `main`.

## 0.15.0 – 2024-11-20

- Improved decadal fixes for **proleptic Gregorian** calendar.
- Provenance now includes local installation "site" name.
- Fixed documentation links.

## 0.14.0 – 2024-10-22

- Added Docker image test step to CI.
- Updated CI workflows and template:
  - New `CODE_OF_CONDUCT.rst`
  - Modernized Dockerfile
  - Documented all processes
  - Switched to `pyproject.toml` with `flit-core`
  - Adopted `src/` layout

## 0.13.1 – 2024-07-22

- Added process: **average over polygon**.
- Updated **CDS domain**.

## 0.13.0 – 2024-02-06

- Added **subsetting support for Atlas v1** datasets.

## 0.12.2 – 2023-12-08

- Fixed `time_components` for **360-day calendar** compatibility.

## 0.12.1 – 2023-12-04

- Patched fill-value issue via updated `clisops`.
- Added smoke test for fill-value handling.

## 0.12.0 – 2023-11-28

- Added **regridding operator** from `clisops`.
- Added tests and smoke tests for regridding.
- CI now uses Conda.

## 0.11.0 – 2023-11-09

- Added **weighted average** operator and WPS process.
- Added WPS regridding process (dummy operator).
- Updated to:
  - `pywps 4.6.0`
  - `clisops` and `daops` with decadal fixes
- Dropped Python 3.8 support.

## 0.10.1 – 2023-07-20

- Updated fix application logic.
- Fixed smoke tests for CMIP5.

## 0.10.0 – 2023-07-12

- Updated `concat` operator to optionally apply subsetting and averaging.
- Applied CMIP6 decadal fixes directly (no ElasticSearch lookup).
- Updated to `clisops 0.10.0`.

## 0.9.3 – 2023-05-16

- Added smoke tests for:
  - `c3s-ipcc-atlas`
  - `c3s-cmip6-decadal`
- Updated `roocs` config for `c3s-ipcc-atlas`.

## 0.9.2 – 2023-02-02

- Updated to `roocs-utils` with `realization` dimension support.
- Updated `concat` operator.

## 0.9.1 – 2022-12-14

- Patched `subset_level_by_values` via `clisops 0.9.5`.

## 0.9.0 – 2022-09-27

- Introduced **initial `concat` operator**.

## 0.8.3 – 2022-09-26

- Updated to `clisops 0.9.2`.
- Updated provenance for **C4I**.

## 0.8.2 – 2022-05-16

- Updated to:
  - `daops 0.8.1`
  - `clisops 0.9.1`
- Added metadata tests.

## 0.8.1 – 2022-04-20

- Updated to `roocs-utils 0.6.1`.
- Fixed `director` for new `average_time` operator.
- Added smoke tests for:
  - `c3s-cmip5`
  - `c3s-cordex`

## 0.8.0 – 2022-04-14

- Added:
  - `average` and `average_time` operators
  - Dashboard updates (for Bokeh 2.4.2)
- Removed: `diff` operator
- Updated to:
  - `clisops 0.9.0`
  - `daops 0.8.0`
  - `pywps 4.5.2`

## 0.7.0 – 2021-11-08

- Added `subset-by-point` process.
- Updated:
  - `clisops 0.7.0`
  - `daops 0.7.0`
  - Dashboard and provenance

## 0.6.2 – 2021-08-11

- Updated:
  - `pywps 4.4.5`
  - Dashboard
  - Provenance types and IDs

## 0.6.1 – 2021-06-18

- Added **initial dashboard**.
- Updated to `clisops 0.6.5`.

## 0.6.0 – 2021-05-20

- Moved catalog functionality to `daops`.
- Updated to:
  - `roocs-utils 0.4.2`
  - `clisops 0.6.4`
  - `daops 0.6.0`
- Added initial `usage` process.

## 0.5.0 – 2021-04-01

- Updated:
  - `pywps 4.4.2`
  - `clisops 0.6.3`
  - `roocs-utils 0.3.0`
- Introduced `FileMapper` and intake catalog support.

## 0.4.2 – 2021-03-22

- Updated to `clisops 0.6.2`.

## 0.4.1 – 2021-03-21

- Switched to `pywps 4.4.1` and linked storage.
- Added:
  - Storm tests (via Locust)
  - Improved smoke tests
- Cleaned requirements and YAML warnings.
- Fixed average output behavior.

## 0.4.0 – 2021-03-04

- Removed unused dependencies.
- Updated to `daops >= 0.5.0`.
- Renamed `axes` input to `dims` in `wps_average`.
- Fixed test data and added smoke tests.

## 0.3.1 – 2021-02-24

- Pinned `cf_xarray < 0.5.0` for compatibility.

## 0.3.0 – 2021-02-24

- Fixed test data using GitPython.
- Updated:
  - `pywps 4.4.0`
  - Provenance structure
  - Subset alignment
  - CI (moved to GitHub Actions)
- Added `director` module.
- Improved CMIP6 support.

## 0.2.0 – 2020-11-19

- Built on `cookiecutter` template via `cruft`.
- Processes available: `subset`, `orchestrate`.
- Integrated `daops`, Metalink output, and provenance.

## 0.1.0 – 2020-04-03

- Initial release.
