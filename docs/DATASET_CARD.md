# AirGuard operational/research dataset card

Regenerate `results/data_coverage.json` and `results/qa_summary.json` with `python -m src.research.reproduce data`. They report actual Supabase source coverage, candidate daily completeness, hashes and matched-pair counts. `results/release/database_audit.json` reports persisted record counts, duplicates, provenance and RLS. No monitor count is presented as a CPCB national census.

The current database includes OpenAQ station measurements, CAMS modelled forecast concentrations, issued Open-Meteo weather and satellite fire detections. Stations retain source IDs, coordinates, upstream provider/owner and available licence metadata. Full authoritative commissioning dates/agency metadata and a licensed hourly CPCB archive since 2019 have not been supplied. Different station/grid/temporal resolutions are not silently merged.

Local `data/interim/qa_measured_export.json` is ignored and private; its SHA-256 input identity is in the versioned QA report. Source rows remain immutable. Flags cover negative/nonfinite/zero-suspect values, consecutive six-hour flatlines, trailing rolling-MAD changes, explicitly evidenced event-review windows, PM2.5 exceeding PM10, unit mismatches, duplicates and unique-hour completeness. Flags require review and never silently delete observations. Quality decisions for training need their own versioned inclusion manifest.

Hourly measurements can be stale or insufficient even when the API connects. Stations are urban-biased and are not population-representative; nearby observations are not neighbourhood truth. Current CAMS has a coarse 0.4° native grid and provider-interpolated hourly output. Retrieval time is observed; upstream CAMS initialization is unavailable from the current live API. Retain this limitation.

Actual daily targets need measured-only station binding, averaging windows and gas support. Study training requires genuine matched issue-time forecasts; archived ADS retrieval is **PENDING — ADS credential/terms required**, explicitly skipped by the user. Legacy Kaggle 2015–2020 daily AQIs remain a separate historical baseline and do not satisfy this hourly study.

Licences and attribution are in `docs/DATA_SOURCES.md` and `docs/LICENSES.md`; MIT applies to code only. Data rights, provider terms, retrieval dates and dataset versions must be preserved before redistribution or commercial use. Public APIs expose limited summaries; private raw data and credentials are not copied into browser artifacts.
