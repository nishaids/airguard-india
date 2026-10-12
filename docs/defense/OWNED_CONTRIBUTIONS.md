# What did you actually build?

| External resource | What it supplies | AirGuard-owned work | Evidence |
| --- | --- | --- | --- |
| OpenAQ / CPCB upstream | Station measurements and metadata | Resumable acquisition, QC ledger, station selection and daily targets | src/research/calibration/measured.py |
| CAMS / Copernicus | Physics-based atmospheric composition forecast | Archived-run checks, grid matching and CPCB-style transformation; correction is pending | src/research/calibration/cams_acquisition.py |
| Open-Meteo / GFS | Air-quality access and weather forecasts | Provider validation, time cutoffs, cache/budget/orchestration | src/nationwide/providers.py |
| NASA FIRMS | Satellite active-fire detections | Optional proximity context; withheld as strict historical predictor | src/nationwide/optional_ingestion.py |
| Supabase/Postgres | Database service | Application schema, request leases/budgets, snapshots and immutable forecast pairing | src/nationwide/store.py; src/research/storage.py |
| Next.js / sklearn / boosting libraries | Frameworks and learners | Frontend/API integration, tests and research evaluation protocol | webapp/app; src/research/calibration |

These resources are dependencies and must be credited. We did not build CAMS, operate CPCB monitors, invent Ridge/conformal prediction, establish causal source attribution or validate a clinical decision system.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
