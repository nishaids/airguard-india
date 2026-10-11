# AirGuard nationwide implementation handover

Status: **implemented and tested locally and on Vercel preview; production approval pending**.
The existing public domain has not been replaced. This is not a completed
production acceptance claim. No models were retrained. No paid dependency or
new Supabase/Vercel project was introduced. Credentials were never printed.

## A–Q acceptance report

| Item | Result |
|---|---|
| A. Architecture detected | Existing Next.js App Router, Python Vercel HTTP functions, Supabase Postgres, Streamlit/historical ML research. Next upgraded from 16.3.7 to patched 16.3.8. Existing project is Vercel Hobby. |
| B. Files changed | `src/nationwide/*`; Python adapters in `webapp/api/`; shared nationwide dashboard/chart/types/guidance; root/live/Atlas/research/method pages and research banners; ingestion HTTP/settings; SQL migrations; deployment/dev config; tests and source documentation. Vendored API bundle regenerated from canonical source. |
| C. Database migrations | Four additive timestamp migrations applied after the existing ingestion baseline, listed below. Existing data preserved; private RLS and immutable issued forecast/verification evidence. |
| D. Live providers | CAMS/Open-Meteo air, GFS weather, India geocoding, OpenAQ hourly measurements and existing FIRMS feeds work. CPCB remains an independently reported network failure. |
| E. OpenAQ measured result | Real hourly observations validated and stored; flags/low coverage, stale stations and unsupported gas units excluded. Nearby Avadi station context is insufficient for a complete current measured AQI, so the displayed AQI is MODELLED. |
| F. Open-Meteo result | Real CAMS global concentrations for PM2.5, PM10, NO2, SO2, CO, O3; direct CPCB-style conversion, not the historical predictor. Weather is contextual and does not adjust AQI. |
| G. CPCB-style validation | Official final report Table 3.11 and sections 3.5/3.7 checked; all pollutant breakpoint boundaries, unit conversion, averaging windows and completeness tested. Severe open-ended bands return ≥401, not invented exact values. Daily gas maximum and fractional continuous interpolation are documented AirGuard conventions. |
| H. Nationwide search | Geocoder uses `countryCode=IN`, exposes district/state where present, accepts coordinates and provider-dependent PIN searches. No fixed training-city restriction. Empty PIN results stay empty. |
| I. Current AQI | Hosted preview returns 124 MODELLED for Avadi with source/time/freshness. Adequate nearby hourly measured AQI takes precedence when available. |
| J. Tomorrow AQI | Hosted preview returns 139 Moderate for 2026-10-11, with 24 IST hours, pollutant breakdown, peak and relative windows. |
| K. Supabase persistence | 8791 new-pipeline records (8640 modelled, 151 measured), 13 immutable forecast artifacts, 0 eligible verification pairs. Repeat retrieval preserves record identity; no missing provenance or late issuance found. |
| L. Cron/refresh | Supabase job `airguard-nationwide-refresh`, UTC schedule `17 * * * *`, active=false. Hosted authorized refresh SUCCESS; anonymous POST=401, GET=405. Activation waits for production deployment and smoke tests. Existing local hourly ingestion remains operational. |
| M. Tests | Baseline 106 Python tests; final 258 Python tests, 6 component tests, 11 real local HTTP E2Es, 39 hosted preview checks. Lint and strict typecheck for new TS components pass. Dependency audits find no known vulnerabilities in resolved API requirements or npm packages. Secret scan: 530 Git objects and working/browser files, zero configured-secret hits. |
| N. Production build | Local optimized Next.js 16.3.8 build and Vercel preview build succeed. Eleven Python endpoint functions detected after adapter detection fix. |
| O. Deployment URL | [Validated preview](https://webapp-6uzvl15es-nishanth-s-projects-e335f110.vercel.app/live). [Existing production](https://webapp-phi-taupe.vercel.app/live) is unchanged and still awaits deployment of this transformation. |
| P. Limitations | Coarse CAMS grid; sparse suitable measured coverage; no calibrated statistical confidence intervals or live accuracy score yet; PIN coverage varies; regional coordinate box is not an India boundary polygon; browser/mobile visual acceptance remains pending because browser recovery was blocked by the tool policy. |
| Q. Manual actions | Explicit approval to deploy to the existing production domain and activate the cloud schedule. No credentials need to be pasted. Optional CPCB network investigation and reviewed translations are separate follow-ups. |

## Real hosted preview example — not a production example

| Field | Actual result |
|---|---|
| Location | Avadi, Thiruvallur District, Tamil Nadu, India (13.1147, 80.10981) |
| Current AQI/source | 124 / MODELLED — Open-Meteo / CAMS global |
| Current forecast valid time | 10 Oct 2026, 05:00 PM IST |
| Current retrieval/freshness | 10 Oct 2026, 06:55 PM IST / FRESH |
| Tomorrow | 2026-10-11, AQI 139, Moderate |
| Tomorrow dominant pollutant | O3 |
| Peak | AQI 139, 11 Oct 2026, 05:00 PM IST |
| Relatively lower-exposure window | 11 Oct 2026, 01:00 AM IST to 11 Oct 2026, 04:00 AM IST; forecast AQI 44–44 |
| Forecast provider | Open-Meteo / CAMS global; modelled atmospheric concentrations |
| AirGuard issue time | 10 Oct 2026, 06:55 PM IST; upstream model initialization time is not exposed by the API |
| Method | airguard-cpcb-2014-v1; not an official CPCB AQI/forecast |

## Architecture and scientific contract

Browser → same-origin Python APIs → shared Supabase cache/budgets → independent
fixed-host providers → unit/coverage validation → one AQI engine → provenance
records and immutable forecast artifact → current/tomorrow/hourly response.
The frontend performs no alternate AQI calculation. Historical ML remains
under Research/Historical Replay, with visibly separate metrics and noncausal
policy scenarios. Retired `/api/live_forecast` returns 410.

Current uses trailing 24h concentrations (CO/O3 complete trailing 8h), at least
three eligible pollutants including PM, and sixteen distinct hourly bins per
pollutant. Tomorrow uses the IST daily mean for non-gases and the maximum full
trailing 8h gas window ending during that day. High ozone uses the report's
one-hour mathematical bands. Hourly AQI is rolling, not instantaneous. NH3/Pb
are explicitly missing from CAMS global. CO mass units divide µg/m³ by 1000;
ppb/ppm are rejected without actual conversion conditions. No imputation.

The official [CPCB technical report](https://airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf)
is archived with extracted text. Exact AQI is never claimed in the open-ended
severe range. Daily min/max is variation, not a confidence interval.

## Persistence, migrations and scheduling

Applied timestamp migrations (mirrored in `db/migrations` and `supabase/migrations`):

1. `20261010121553_nationwide_live_product.sql`: locations/sensors, shared cache,
   provider events/budgets, normalized environmental records, issued forecasts,
   station verifications, indexes/RLS/immutability.
2. `20261010123357_secured_supabase_cron.sql`: pg_cron/pg_net, Vault-backed secured
   fixed production endpoint and hourly schedule registered inactive.
3. `20261010123539_cron_extension_schema.sql`: attempted pg_net privilege
   restriction; platform owner ACL caveat below.
4. `20261010125521_index_ingestion_foreign_keys.sql`: five missing FK indexes and
   300-second scheduler HTTP timeout. Function duration is 300 seconds; distributed
   leases are 360 seconds, retries bounded to two attempts.

This repository's canonical migration runner is `python -m src.ingestion.db migrate`.
Do not blindly `supabase db push` the existing schema: its older baseline/history
is tracked by `airguard.schema_migrations`, not the CLI migration history.

The configured connection is a Supabase **session pooler**, SSL required, client
TLS verified. It is not a guessed or manually constructed host. Short-lived
connections close after each transaction; no per-invocation application pool,
named prepared statements or session locks in the nationwide service. At scale,
obtain the actual transaction-pooler DSN from the existing project's settings
and load-test it; do not invent its host or print the URL.

Cloud scheduling warms the two most recently requested locations and verifies
one eligible ended-day forecast per run; arbitrary other locations fetch on
demand. Verification waits six hours after the target ends and uses matching
station hourly periods only. No modelled truth or retrospective issuance.
Metrics expose pair count, MAE/RMSE/bias and category agreement by region/lead/
predicted category. No real eligible pairs exist yet; a populated score requires
target days to elapse AND adequate observed station data.

The Windows task `AirGuard 2.0 Live Ingestion` continues hourly for legacy
OpenAQ/CPCB/FIRMS/weather ingestion using the isolated patched runtime. It needs
the user's logged-in, awake computer. Exit 1 reflects CPCB's partial-source
failure while other sources still ingest. Cloud FIRMS ingestion is not added;
its contextual record freshness is disclosed.

## Security, budgets, licences and known review limits

Only server-side environment variables/Vault hold credentials. Supabase tables
are private, RLS enabled with no public policies; anon has no `airguard` schema
usage and cannot execute the secret-backed refresh function. Queries are
parameterized; refresh authorization is constant-time, request input is bounded,
provider hosts fixed, CORS is same-origin, client budgets use salted hashes.
Browser cohorts are not persisted. Geolocation needs explicit browser permission.

Supabase's security advisor reports one [pg_net extension-in-public warning](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public).
The hosted extension is non-relocatable and owned by `supabase_admin`; postgres
REVOKE attempts do not remove owner-created public network-function ACLs.
This standard extension permission remains; AirGuard's secret-bearing function
and data schema are restricted. Do not drop/reinstall the live extension to
silence the advisory. Owner-level hardening can be reviewed separately.
RLS-with-no-policy notices are intentional for private server-only tables.
No missing FK indexes remain; unused-index INFO notices are retained while
traffic is new.

Shared budgets count **every HTTP attempt including retries**: Open-Meteo family
500/min, 4000/hour, 9000/day; OpenAQ 55/min, 200/hour, 4000/day; at most 50 new
CAMS grid cells/day. These free-first bounds can reject demand; this is not
unlimited public capacity. TTLs: air 1h, weather 2h, stations 30m, geocoder 7d.
Failure fallbacks are explicitly stale to 6h air/weather or 3h measured context,
then unavailable. Measured freshness thresholds come from configuration.

[Data source/licence review](../DATA_SOURCES.md) covers CC BY attribution,
Open-Meteo's non-commercial free hosting terms, station-specific OpenAQ licences,
NASA and Indian government data. A commercial release needs licence review;
no paid service was enabled. Raw source data is not universally CC0.

English guidance is deterministic and reviewable, with seven sensitivity groups.
Hindi/Tamil are disabled scaffolds pending reviewed translations. Guidance is
not a clinical risk model. Accessible controls, focus, labels, chart table
alternative, category text and reduced-motion styles are implemented. Component
permission tests are mocks; actual browser permission, mobile screenshots and
WCAG conformance have **not** been certified by these API checks.

## Exact CPCB failure

`requests.exceptions.ConnectionError`, wrapping `urllib3.exceptions.NewConnectionError`:

> HTTPSConnection(host='api.data.gov.in', port=443): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it

This occurred before any HTTP response, not an HTTP authentication error. The
full credential-redacted request error is in `results/optional_provider_checks.json`.
No substitute was labelled CPCB. Other sources continued; no network change was made.

## Reproduction and production gate

Development on this machine:

```powershell
.\.venv-live\Scripts\python.exe -m pytest tests/ -q
.\.venv-live\Scripts\python.exe -m scripts.audit_secret_history
.\.venv-live\Scripts\python.exe -m src.ingestion.db migrate
.\.venv-live\Scripts\python.exe -m src.deploy.vendor_for_vercel
cd webapp
..\.venv-live\Scripts\python.exe dev_api_server.py # separate terminal
npm run dev # separate terminal
npm run lint
npm run typecheck
npm test
npm run test:e2e
npm run build
```

`.venv-live` isolates Requests 2.34.2 while using this machine's existing research
dependencies. Fresh deployments resolve the pinned API requirements independently.
Do not run research training as part of deployment.

After explicit production approval: deploy the tested files to the **existing**
Vercel project with production environment secrets already securely configured;
smoke-test the preserved domain and API, then activate the named Supabase Cron
job and verify its HTTP response/run log. Keep Cron disabled if smoke tests fail.
Production Avadi acceptance and public UI validation remain required; this
report deliberately supplies a real preview example instead of a false production one.

Evidence: `results/nationwide_staging_acceptance.json`,
`results/nationwide_database_acceptance.json`, `results/nationwide_acceptance.json`,
`results/optional_provider_checks.json`, `results/python_runtime_audit.json`,
and `webapp/test-results/nationwide-api.json`.
