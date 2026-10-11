# Operational UI consolidation — 11 October 2026

Existing AirGuard India repository, Next.js app, Python APIs and Supabase project retained. Production remains the previously approved deployment; this UI consolidation is a preview for review. No model was retrained and no historical data/results were rewritten.

## 1. Routes changed

| Route | Final purpose |
| --- | --- |
| `/live`, `/` | Nationwide current/tomorrow summary |
| `/forecast` | Operational Forecast & Advisory |
| `/policy-simulator` | Counterfactual using the selected location's saved tomorrow forecast |
| `/city-atlas` | Operational selected-place summary and optional six-city comparison |
| `/research` | Selected-location operational research, prospective protocol/ledger, historical research links |
| `/historical-replay` | Preserved historical city/cohort/date replay and HAI |
| `/research/historical-policy` | Preserved historical full-record policy experiments |
| `/research/historical-atlas` | Preserved K-Means, ranked risk, seasonality, festival and lockdown analyses |
| `/model-insights` | Retained, explicitly labelled legacy models |
| `/methods` | Unified data flow, source distinctions, timing, scenarios and limitations |

Navigation distinguishes Forecast & Advisory from Historical Replay. Historical research links now point to historical routes.

## 2. Historical functionality preserved

Original replay city/cohort/date controls, 2015-01-01 → 2020-07-01 coverage, next-day historical forecast, pollutant what-if, HAI, history charts and model results remain. Historical replay explicitly states **HISTORICAL REPLAY · 2015–2020 DATA · NOT CURRENT AIR QUALITY**. Historical policy and atlas have their own banners and routes. Existing model files and static data hashes are preserved in `results/ui_integration/audit.json` and checked by preview acceptance. No historical model/data retraining, rewriting or deletion was performed.

## 3. Authoritative operational API

Operational pages consume `/api/air-quality/summary` through one `OperationalProvider`. They do not request historical metadata, evaluation JSON, safe-window files, city rows or historical prediction APIs. The existing current/forecast/search/provider APIs remain. The only new public API is **POST `/api/air-quality/scenario`**. It shares the existing Python policy function through a fixed operational rewrite, preserving the Vercel function allowance and the historical policy endpoint.

There is one CPCB-style engine: `src/nationwide/aqi.py`. No operational frontend breakpoint arrays or alternative current AQI calculations were added.

## 4. Shared location and cohort architecture

The root layout owns one browser provider. A valid deep link overrides versioned localStorage, which overrides the initial Avadi location. Selected location contains coordinates, normalized key, name, region, country and optional district from geocoding. Operational navigation carries location URL parameters. Browser Back restores selection and clears the previous place's displayed AQI while the new summary loads.

Browser cohort preference stays local. It is absent from summary/scenario request bodies, location URLs and operational database records. Shared exposure rules are versioned `exposure-guidance-v1` and preserve the existing guidance; legacy HAI remains historical.

The browser caches at most 24 location summaries for one minute, deduplicates concurrent requests, and reuses the same response across routes. IST midnight clears the cache and comparisons. A request started before midnight cannot populate the new day's cache or overwrite its summary. Backend Supabase/provider caches, leases, freshness rules and budgets remain in use.

## 5. Forecast & Advisory

Uses the shared location, current AQI/category/source/freshness/station context, tomorrow's target date/issue time/mode/dominant pollutant, daily variation, peak and exposure windows. Hourly charts/table use backend values for remaining today and tomorrow. Pollutant selector and current/tomorrow concentration, units, sub-index, coverage and comparison trend are present. Missing concentrations stay unavailable. Trend comparisons disclose that source/aggregation windows can differ.

Seven browser-local cohorts receive current and tomorrow exposure guidance from the same shared module. The disclaimer states: “AirGuard provides environmental information and general exposure guidance, not medical advice.” No clinical probability or fabricated prediction interval is shown. Daily variation is separate from calibrated uncertainty.

## 6. Policy baseline integration

The scenario request identifies an immutable `forecast_run_id` and matching `location_key`. The server reads its saved original provider hourly concentrations and units, including preceding seven-hour support for gas windows. It normalizes and aggregates with the central engine, verifies the baseline reproduces the saved forecast, applies bounded proportional reductions, then recalculates. Zero reductions reproduce the baseline exactly. Wrong location/reference, expired target, invalid reductions, cohort fields and historical date/city inputs are rejected by the operational handler. Missing pollutants are not imputed.

The response includes baseline/scenario AQI, categories, dominant pollutants, pollutant breakdowns, target, issue time, methodology and immutable input reference. It makes no causal policy claim. Scenario calculation does not modify forecast inputs or create model versions.

## 7. Atlas

Selected place uses the same live summary. Users can load Delhi, Mumbai, Chennai, Avadi, Coimbatore and Kochi comparisons two at a time through the shared cache. Rows show current/tomorrow AQI/category, source type, freshness and timestamps; links carry each place into Live, Forecast or Policy. Comparisons are explicitly snapshots when loaded and can be refreshed. Old-day comparisons clear at IST midnight. CAMS grid estimates are never presented as monitoring stations. The historical atlas remains available separately.

## 8. Research

Selected-location details show CAMS baseline, correction/model/interval availability, mode, issued/target time, source, freshness and forecast record. **Station-calibrated correction is under evaluation.** On-demand forecasts and the fixed 20:00 IST prospective ledger remain distinct. Existing readiness gates and prospective evaluation framework are preserved. Historical LightGBM/XGBoost/SHAP/K-Means/model/data cards and HAI remain linked separately.

## 9. Tests

Before changes: **294 Python tests, 8 frontend tests, production build PASS**.

Final local checks: **311 Python tests, 19 frontend tests, 14 real HTTP Playwright acceptance tests; typecheck and lint PASS**. Final backend-focused checks also pass. Frontend flow tests mount the actual Live, Forecast and Policy route components under one provider, search/select Avadi, navigate between them, assert identical headline values and one summary request, change cohort locally, and submit the same forecast reference for a scenario.

Coverage includes all six requested places, additional nationwide cities, remote coordinates with no eligible station, OpenAQ failure/modelled fallback, CAMS failure with measured current retained, stale labels, missing pollutants, denied/granted geolocation, URL persistence, old location response races, IST midnight and pre-midnight in-flight responses. Historical Replay still loads its date controls; operational Forecast contains no date input or historical fetch. Preview acceptance additionally checks SSR routes, real Supabase-backed summaries, central scenarios, invalid requests, research state, preserved historical APIs and static metadata.

Browser visual/click-through QA was **not executed**: browser navigation was blocked by the environment. No alternative browser was used to bypass that block. React DOM route-flow tests and Playwright HTTP tests are not being represented as browser-driven E2E.

## 10. Build and database

Production build passes for all 14 application routes plus the not-found page. Vercel preview build uses the existing project/team, Next.js app and Python functions. No schema migration is needed for this UI change. `DATABASE_URL` availability is checked as a boolean; its value is never printed. Supabase connectivity and preserved provenance/duplicate checks pass. Exact database snapshot and build/deployment evidence are in `results/ui_integration/`.

## 11. Preview and production

Preview: https://webapp-l9hixysol-nishanth-s-projects-e335f110.vercel.app/forecast?lat=13.1147&lon=80.10981&name=Avadi

Vercel Authentication protects previews; the project owner can open this while signed in. Protection was not disabled. Production alias https://webapp-phi-taupe.vercel.app remains deployment `dpl_61LbwsPHksTqtR5Xk6A5YL3Y6ad1`; it has not been replaced. Explicit approval is required before releasing this UI consolidation to production. Scheduled ingestion continues on the existing production endpoint and Supabase cache; it is not switched to a preview.

## 12. Remaining limitations

Tomorrow's operational output is a real CAMS-based CPCB-style forecast, whose station-calibrated skill/uncertainty has not yet been established. No correction model or calibrated interval has been activated. Eligible measured issue-time forecast/outcome pairs, rolling/spatial validation, held-out calibration and prospective evidence are still required before claiming AirGuard correction improves tomorrow-AQI prediction. CAMS grid resolution cannot describe street/personal exposure. Clinical outcomes and causal policy effects are not predicted.

Historical CAMS archive/backfill remains **PENDING — ADS credential/terms required**, skipped at the user's request. No reanalysis or newly retrieved past-day fields substitute for archived issue-time forecasts. The prior independent CPCB test failed at `api.data.gov.in:443` with `ConnectionError / NewConnectionError: [WinError 10061] No connection could be made because the target machine actively refused it`; the full redacted error is `results/optional_provider_checks.json`. Modelled data is never labelled as CPCB measurements. OpenAQ can be connected while lacking enough recent nearby pollutants to produce measured AQI. FIRMS remains satellite context rather than an AQI adjustment. Initial loading waits for the bounded summary aggregation; cached values remain available during same-place refreshes.

## Exact Avadi flow evidence

The final verified deployment snapshot, source times and values are appended from `results/ui_integration/preview_acceptance.json`. Values change with provider updates; the architecture and tests ensure all operational routes reuse the same selected-location summary rather than independent historical or provider calculations.

Verification snapshot: 2026-10-11T09:15:01.843477+00:00. **29 final-preview HTTP checks passed.**

| Flow step | Coordinates | Current AQI | Tomorrow baseline | Forecast record |
| --- | --- | --- | --- | --- |
| Live | 13.1147, 80.10981 | 101 | 137 | 186 |
| Forecast & Advisory | same shared selection | 101 | 137 | 186 |
| Policy Scenarios | same shared selection | 101 | 137 | 186 |

Source: Open-Meteo / CAMS global · MODELLED · FRESH. Current valid timestamp: 2026-10-11T07:30:00+00:00. Tomorrow target: 2026-10-12; issue time: 2026-10-11T09:02:06.386624+00:00; mode: CAMS_BASED_NATIONWIDE. Method: airguard-cpcb-2014-v1. No nearby station had sufficiently complete recent hourly pollutants to replace this modelled estimate.

PM2.5 −20% scenario: baseline 137 → scenario 137. The headline is unchanged because O3 remains dominant; a reduction in a non-dominant pollutant does not necessarily change the maximum eligible sub-index. The original input reference and record remain unchanged. This scenario is not a claim about the effect of a real policy.

Supabase final checkpoint: 14,432 environmental records with provenance and 73 immutable operational forecast records; natural forecast duplicates 0; missing provenance 0. Database connected; DATABASE_URL availability checked without disclosure. No cohort records or model training artifacts were created by this consolidation.

Evidence: `results/ui_integration/audit.json`, `dependency_audit.json`, `database_check.json`, `deployment.json`, `preview_acceptance.json`, `avadi_summary.json`; Playwright HTTP output: `webapp/test-results/nationwide-api.json`. The real HTTP source snapshot and actual route-component navigation tests establish the shared result; visual browser navigation remains unverified as stated above.
