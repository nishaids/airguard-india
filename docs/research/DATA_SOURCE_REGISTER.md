# Data source register

Generated 2026-10-20T07:31:09Z by `scripts/build_data_source_register.py` from committed evidence and read-only database counts. Machine-readable copy: `results/research/data_source_manifest.json`. Licences and attribution: `docs/LICENSES.md`; provider quotas: `docs/DATA_SOURCES.md`.

Every source carries one of five kinds and none stands in for another: **OBSERVED**, **HISTORICAL_REANALYSIS** (none is used), **ARCHIVED_OPERATIONAL_FORECAST**, **LIVE_FORECAST**, **MODELLED_OUTPUT**.

| Source | Kind | Provider | Coverage | Issue-time status | Evidence |
| --- | --- | --- | --- | --- | --- |
| `A_B_station_observations` | OBSERVED | OpenAQ v3, upstream provider CPCB (Central Pollution Control Board monitoring network) | ['2025-02-19', '2026-10-07'] | see notes | `results/research/measured_dataset.json`, `results/research/data_manifests/openaq_hours_manifest.json` |
| `A_direct_cpcb_feed` | OBSERVED | CPCB via data.gov.in | - | UNAVAILABLE: no successful response recorded | `docs/airguard2/live_data_implementation.md`, `database: airguard.ingestion_runs` |
| `C_weather_archive` | ARCHIVED_OPERATIONAL_FORECAST | Open-Meteo (NOAA GFS, model gfs_seamless) | ['2025-02-01', '2026-10-08'] | valid | `results/research/data_manifests/weather_archive_manifest.json` |
| `D_cams_operational_archive` | ARCHIVED_OPERATIONAL_FORECAST | Copernicus Atmosphere Monitoring Service (ECMWF), via the Atmosphere Data Store | ['2025-02-17', '2025-05-31'] | valid | `results/research/cams_development_acquisition.json`, `results/research/cams_development_alignment.json` |
| `D_cams_short_lead_proxy` | MODELLED_OUTPUT | CAMS global via Open-Meteo | ['2025-02-01', '2026-10-08'] | NOT valid | `results/research/data_manifests/cams_archive_manifest.json` |
| `E_station_metadata` | OBSERVED | OpenAQ locations, with versioned AirGuard corrections | - | see notes | `results/research/data_manifests/station_selection.json`, `results/research/data_manifests/station_metadata_corrections.v2.json` |
| `F_legacy_aqi` | OBSERVED | Kaggle export of CPCB data (2015-2020) | - | see notes | `data/raw/PROVENANCE.json` |
| `G_live_inputs` | LIVE_FORECAST | Open-Meteo (CAMS global air quality, GFS weather), OpenAQ, NASA FIRMS | - | see notes | `docs/DATA_SOURCES.md`, `database: airguard.provider_events` |
| `H_prospective_records` | LIVE_FORECAST | AirGuard (issued forecasts) and OpenAQ (later outcomes) | - | see notes | `database: airguard.forecast_runs / research_forecast_runs and their verification tables` |
| `satellite_fire` | OBSERVED | NASA FIRMS | ['2025-02-01', '2026-10-08'] | see notes | `results/research/data_manifests/firms_archive_manifest.json` |

## What the numbers say

- **Station observations** come from CPCB-network monitors **through OpenAQ**: 179 usable stations in 100 Indian cities, 2025-02-19 to 2026-10-07. This is not official CPCB data and the targets are AirGuard's CPCB-style daily AQI from PM2.5, PM10 and ozone, not the bulletin AQI.
- Missing data: of 107,280 station-days, 42,481 (39.6%) have no valid target. Of 6,331,429 raw hourly rows, 851,125 fall in under-covered hours.
- **The official CPCB feed** (data.gov.in) has never returned data to this project: 0 successful and 187 failed recorded ingestions.
- **Archived operational CAMS**: 9 of 36 planned ADS files verified, covering 104 initialisation dates with both surface and model-level fields (2025-02-17 to 2025-05-31). Current join: 18,540 station-days, 180 stations, 103 dates. Reanalysis substitution is prohibited.
- **The Open-Meteo CAMS past-hours series is not an archived forecast**: its values come from runs initialised after the issue time, so it is kept as exploratory modelled output only.
- **Weather predictors** use Open-Meteo's previous-runs archive at a two-day lead, which is older than what an operator would have had, so it handicaps rather than flatters the weather features. Boundary-layer height is not archived at any previous-run lead.
- **Fire detections** are archived but withheld from the strict models: acquisition time does not prove publication time.
- **Prospective records**: 108 fixed-time research forecasts over 9 target days with 10 verified outcomes; 532 on-demand nationwide forecasts with 77 station pairs over 3 verified target days.
- **Live inputs**: 5,353 recorded provider events.

Per-source details (endpoint, units, sampling, licence, quality control, issue-time rule) are in the JSON manifest.
