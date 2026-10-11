# Research upgrade acceptance report

Status: COLLECTING_NOT_RESEARCH_READY. 5/17 readiness checks have evidence. This is not a forecast accuracy score.

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

Immutable variable-time CAMS records exist. Fixed-time local tasks installed; first actual issuance pending. Fixed-time outcomes zero. No retrospective record counts as prospective. Cloud cron remains inactive.

## P — Migrations

20261010174656_research_forecast_protocol.sql (15 private tables and inactive schedules); 20261010180429_research_ledger_guards.sql (stronger period/station/outcome/error guards). Canonical application migration history retained.

## Q — API/UI

/api/research/status, /research, /research/track-record, /research/legacy added. Existing /live and nationwide APIs preserved. Consumer values remain CAMS while correction is unsupported.

## R — Tests

See results/research/verification.json for final executed checks. Synthetic fixtures exercise software only and never produce paper metrics.

## S — Build

See final verification artifact; production replacement requires explicit approval. Preview deployment belongs to the existing webapp project.

## T — Readiness

5/17 evidence checks; NOT RESEARCH READY. Detailed booleans and evidence hashes in research_readiness.json.

## U — Limitations

Zero eligible operational training pairs currently. The archive experiment is PENDING — ADS credential/terms required and was explicitly skipped by the user. No reanalysis/current past-days substitute. Sparse modern measured data lacks three eligible pollutants at each audited station-day. CAMS grid is 0.4 degrees (~45 km), provider-interpolated from native three-hour values. Severe open concentration bands yield >=401 lower bounds; exact Severe MAE is not identifiable under this method. Legacy city daily data and modern station hourly records are mismatched for drift attribution. FIRMS remains optional context. Hindi/Tamil guidance remains disabled. No automatic retraining. Browser visual/mobile review remains outstanding; automated component and HTTP tests are not certification. Supabase pg_net's platform-owned PUBLIC privileges and extension placement warning remain; AirGuard tables and secret functions are private.

## V — Supported claims

The project provides labelled nationwide raw CAMS estimates, secure Supabase storage, immutable pre-target baseline records and a tested issue-time research framework.

## W — Unsupported claims

AirGuard ML beats CAMS; correction generalises nationwide; calibrated Severe uncertainty; controlled cohort under-warning; prospective 30/90-day skill; clinical benefit; novelty.

## X — Manual actions

Archive access was skipped per user instruction and remains optional pending ADS credentials/terms. Production deployment and cloud schedule activation require explicit approval. Calendar time and adequate measured station data are needed for experiments; no credential substitutes can manufacture them.
