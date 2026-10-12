# AirGuard in one page

AirGuard India combines source-labelled air-quality information, a CPCB-style index engine, next-day modelled forecasts and environmental exposure guidance. Select an Indian place or coordinates; inspect measured versus modelled current data, tomorrow’s forecast, missing data and provenance. Nationwide fallback uses the CAMS global grid and does not establish street-level precision.

Built: bounded ingestion, caching, station selection, mass-unit checks, AQI aggregation, source labels, APIs, frontend, immutable prospective records and research/QC/split/reproduction infrastructure. Still being established: a validated CAMS station correction, operational intervals and a 30-day verified record.

The retained measured table contains 107,280 station-days: 64,799 valid and 42,481 rejected targets, 179 usable stations in 100 parsed cities. Its dates are 2025-02-19 through 2026-10-07; rejection records are retained. The final 90 days, 2026-07-10 through 2026-10-07, remain sealed at this checkpoint. In the NON_CAMS_PRELIMINARY development comparison, strict Ridge minus climatology MAE is -8.96 AQI (95% date-block interval [-12.49, -5.61]). Conditional history Ridge minus persistence is +0.61 ([-0.41, 1.70]); an improvement is not established. Every strict baseline forecast on 363 evaluated censored Severe validation days fell below 401. This serious failure is disclosed prominently. These are not CAMS-comparison or final-test results.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
