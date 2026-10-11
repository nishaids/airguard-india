# Research upgrade acceptance report

Status: COLLECTING_NOT_RESEARCH_READY. 3/17 readiness checks have evidence. This is not a forecast accuracy score.

## A — Architecture audited

Existing Next.js/Vercel Python/Supabase application retained. Source inventory and baseline are results/research/repository_audit.json. Nationwide live sources, SQL cache, budgets, leases and legacy models preserved.

## B — Scientific inconsistencies

Live forecast explicitly labels CAMS nationwide mode and unvalidated station correction. Historical research moved to /research/legacy. Prior past-fields backtest is exploratory, not archived day-ahead validation. The original city-ordered row CV trains through 2019 against 2015-era validation rows in all four folds; its temporal-validation claim is invalid. Future splitters require explicit date metadata and whole-date embargoed splits; original weights and scores remain preserved and labelled. Fold-specific preprocessing/selection still needs nested evaluation. R², SHAP, counterfactual policy and HAI retain their limited meanings.

## C — Protocol

airguard-dayahead-20ist-v1: 20:00 IST daily; next IST calendar day; <=20:00 availability cutoff; measured station-only target; minimum three pollutants including PM, 16 hourly bins, complete eight-hour gas windows. No late backdating.

## D — Dataset

Operational pairs 0, eligible stations 0, cities 0, dates []. Historical station-day rows 108035, stations 110, cities 26, dates ['2015-01-01', '2020-07-01']; these reported daily AQIs are a separate dataset. Source coverage, missingness and rejected target days are generated JSON files.

## E — Baselines

Climatology, measured persistence and raw CAMS implemented, with ridge, LightGBM, XGBoost and direct-AQI comparison. Legacy B3 is not applicable to the new operational rows until separately validated.

## F — Models

Offline residual correction: measured target minus raw CAMS; add predicted residual back. Physical nonnegative floor recorded. No new research model trained or activated on real operational pairs yet.

## G — Primary results

{"n": 0, "MAE": null, "RMSE": null, "bias": null, "category_metrics": null}

## H — CAMS improvement

{"absolute": null, "percentage": null, "CI": null, "p_value": null, "reason": "No eligible evaluation pairs"}

## I — Rolling-origin

Date-blocked rolling and expanding implementation tested. Operational fold results pending.

## J — Spatial

Leave-city and leave-station framework implemented. Operational results pending; deployment support denies unvalidated stations.

## K — Severe events

Numeric Severe error cannot be fabricated from censored >=401 targets. Exact target regression excludes lower bounds; category-only ledger verification retains them. Severe-support evidence is absent.

## L — Ablation

A0–A4 implemented for CAMS/weather/station/spatial groups. A5 FIRMS pending captured fire features and evidence; excluded from predictor. No winning feature set claimed.

## M — Uncertainty

CQR 80%/90% framework implemented and tested. Empirical/conditional coverage and widths pending real pairs. No operational calibrated interval.

## N — Advisory

Versioned seven-cohort experimental calibration screen, under/over-warning and severity-distance metrics implemented. No cohort risk control or clinical validation claimed.

## O — Prospective

Immutable variable-time CAMS records exist. Fixed-time local tasks are installed; four Supabase cloud schedules are now active following explicit user approval on 11 October 2026. The exact Vault-authenticated enqueue function returned HTTP 200 / SUCCESS from the production endpoint. First actual 20:00 IST issuance and fixed-time outcomes remain pending; no retrospective record counts as prospective. Future scheduled triggers are not represented as completed runs.

## P — Migrations

20261010174656_research_forecast_protocol.sql (15 private tables and initially inactive schedules); 20261010180429_research_ledger_guards.sql (stronger period/station/outcome/error guards); 20261011075204_research_scheduler_timeout.sql (Vault-authenticated HTTP timeout aligned to the bounded 300-second function). Canonical application migration history retained. The 19:50 IST cloud prefetch now forces fresh inputs across twelve research locations; ordinary hourly warming remains bounded to two.

## Q — API/UI

/api/research/status, /research, /research/track-record, /research/legacy added. Existing /live and nationwide APIs preserved. Consumer values remain CAMS while correction is unsupported.

## R — Tests

294 Python tests passed after three new cloud schedule checks verified prefetch coverage and issuance before any new fetch. The earlier 8 component tests and 12 real local Playwright HTTP checks passed. Before release, previews passed 47 checks across two deployments. The staged production build passed 21 checks; the public production domain passed 27, including eight cities, remote coordinates, PIN search, research routes, Supabase, current next-day target dates and refresh authorization. Scoped lint, strict TypeScript and production builds passed. The secret scan checked 530 Git objects, the working tree and browser assets with zero configured-secret hits. Synthetic fixtures exercise software only and never produce paper metrics. Browser visual/mobile QA remains outstanding. Detailed evidence: results/research/verification.json, staged_production_acceptance.json, production_acceptance.json and cloud_ingestion_activation.json.

## S — Build

The approved production build dpl_61LbwsPHksTqtR5Xk6A5YL3Y6ad1 was staged, tested and promoted in the existing webapp project. The [public live page](https://webapp-phi-taupe.vercel.app/live) and [public research ledger](https://webapp-phi-taupe.vercel.app/research/track-record) passed requests without a Vercel bypass or login. The previous production deployment is recorded for rollback in results/research/previous_production_deployment.json. The Hobby function limit is respected by routing the public research status URL through the existing read-only provider-status function.

## T — Readiness

3/17 evidence checks; NOT RESEARCH READY. Detailed booleans and evidence hashes in research_readiness.json.

## U — Limitations

Zero eligible operational training pairs currently. The archive experiment is PENDING — ADS credential/terms required and was explicitly skipped by the user. No reanalysis/current past-days substitute. Sparse modern measured data lacks three eligible pollutants at each audited station-day. CAMS grid is 0.4 degrees (~45 km), provider-interpolated from native three-hour values. Severe open concentration bands yield >=401 lower bounds; exact Severe MAE is not identifiable under this method. Legacy city daily data and modern station hourly records are mismatched for drift attribution. FIRMS remains optional context. Hindi/Tamil guidance remains disabled. No automatic retraining. Browser visual/mobile review remains outstanding; automated component and HTTP tests are not certification. Supabase pg_net's platform-owned PUBLIC privileges and extension placement warning remain; AirGuard tables and secret functions are private.

## V — Supported claims

The project provides labelled nationwide raw CAMS estimates, secure Supabase storage, immutable pre-target baseline records and a tested issue-time research framework.

## W — Unsupported claims

AirGuard ML beats CAMS; correction generalises nationwide; calibrated Severe uncertainty; controlled cohort under-warning; prospective 30/90-day skill; clinical benefit; novelty.

## X — Manual actions

Archive access was skipped per user instruction: **PENDING — ADS credential/terms required**. It does not block prospective collection or the implemented schema, baselines, issue-time feature pipeline, uncertainty/advisory framework or tests. Explicit production approval was granted and fulfilled on 11 October 2026. Cloud jobs run at 19:50/20:00/07:00 IST, plus hourly at minute 47, independently of the PC. Local tasks are also retained and need an awake logged-in PC. The first eligible scheduled issuance is 11 October 2026 at 20:00 IST, targeting 12 October; it has not been backdated. Calendar time and adequate measured station data are needed for experiments; no credential substitutes can manufacture them.

## Live integration and storage evidence

DATABASE_URL was checked without printing it, migrations were applied, and Supabase connectivity passed. OpenAQ measured records, Open-Meteo weather, raw CAMS air-quality forecasts and NASA FIRMS fire detections succeeded. CPCB/data.gov.in failed independently: **ConnectionError / NewConnectionError: [WinError 10061] No connection could be made because the target machine actively refused it**, on **api.data.gov.in:443**. Full credential-redacted network details are in results/optional_provider_checks.json. No substitute is labelled CPCB.

The audited ingestion tables contain 1,594 air-quality observations, 5,680 weather forecast rows and 1,523 fire detections. All have nonempty provenance; all three natural-key duplicate-group counts are zero. Separately, the nationwide store contains 13,300 environmental records (239 measured, 13,061 modelled), 57 immutable research provider snapshots and 56 on-demand forecast records. There are zero valid fixed-time issue/target pairs, zero trained research model versions and zero verified fixed-time outcomes. These counts are separate tables of the same Supabase database, not additive unique-observation totals. Current-state artifacts: results/live_integration_acceptance.json and results/research/database_status.json.

Real station-calibrated tomorrow-AQI prediction still requires eligible measured hourly targets paired with pre-cutoff forecasts, sufficient chronology under the locked protocol, then baseline/residual training, untouched temporal/spatial validation, uncertainty/advisory calibration and prospective verification. The existing tomorrow value is explicitly a raw CAMS estimate. No legacy model was retrained and no forecast skill was invented.
