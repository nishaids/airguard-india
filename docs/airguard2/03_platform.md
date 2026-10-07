# Part 3 — Platform architecture

Everything in this part is **Proposed**. The single largest change from 1.0 is that the forecast is no longer computed when a user asks for it.

## G. AirGuard 2.0 architecture

### G.1 Batch first

In 1.0 every page view runs the model inside a serverless function, which is why the function must fit 250 MB, why the classifier had to be swapped for a smaller one, and why the first request takes five seconds. In 2.0 a scheduled job computes tomorrow's forecast for every station once, stores it, and the website reads a row.

```
 Providers            Ingestion (scheduled)         Storage                Batch ML (scheduled)        Serving
 ---------            ---------------------         -------                --------------------        -------
 CPCB / OpenAQ  --->  connector -> validate    ---> observations     --->  feature snapshot      --->  read API
 CAMS (Open-Meteo)    -> normalise units/time       weather_forecasts      (point-in-time)             (rows only)
 Weather forecast     -> quality flags              cams_forecasts    <--- forecast + interval    --->  Next.js app
 FIRMS fires          -> de-duplicate               feature_snapshots      + cohort advisories
                      -> record run                 forecasts              verification (next day)     on-demand:
                                                    forecast_verification  drift report (weekly)       what-if,
                                                    model_versions         retrain + gate (monthly)    scenarios
```

Consequences: any model that can run in a scheduled job can be used, with no bundle limit; the calibrated classifier problem disappears, because there is no separate serving model; page loads take one database read; and every forecast ever issued is kept, so the system can show how accurate it has been.

Only two things still compute on demand, because they depend on user input: the what-if sliders and the policy scenarios.

### G.2 Component choices

| Component | Choice | Alternatives considered | Why | What would change the choice |
| --- | --- | --- | --- | --- |
| Scheduler | GitHub Actions scheduled workflows | Vercel Cron; database cron; a small always-on server | The pipeline already lives in the repository; free; logs and secrets are built in; independent of the hosting plan | Schedule delays long enough to miss the issue time; inactivity rules on scheduled workflows |
| Serving database | PostgreSQL (managed free tier) | Static JSON in the repository (1.0); TimescaleDB; SQLite | Concurrent writes, time-range queries, constraints that prevent duplicates. Volume is small: a few hundred stations hourly | Row counts beyond the free tier; then partitioning or TimescaleDB |
| Training store | Parquet snapshots in object storage, hashed | Training directly from the serving database | Training data must be immutable and reproducible; a live table is neither | — |
| Read API | Route handlers in the existing Next.js app | Separate FastAPI service | One deployment; reads are trivial | A need for Python on the read path |
| Compute API | The two existing Python functions | Container service | Already working and verified | Models that cannot be evaluated without ML libraries |
| Model registry | A `model_versions` table plus hashed artefacts | MLflow | No server to run; enough for one model family | Many concurrent experiments |
| Maps | Vector tiles with a light open-source renderer | Embedded third-party map | Control over severity encoding and accessibility | — |

## P. Backend and API

### P.1 Endpoints

All under `/api/v1`. Reads are `GET` and cacheable.

| Endpoint | Returns |
| --- | --- |
| `GET /cities` | Covered cities with station counts and data freshness |
| `GET /stations?city=` | Stations with coordinates, source, last reading time, quality status |
| `GET /live?city=` or `?station=` | Latest valid measurement per pollutant, each with source, `observed_at`, `retrieved_at`, quality flag, `is_modelled` |
| `GET /forecast?city=&cohort=` | Tomorrow's expected AQI, range, band probabilities, dominant pollutant, cohort advisory, confidence word, issue time, model version |
| `GET /forecast/history?city=&days=` | Past forecasts beside what happened: the system's own track record |
| `GET /advisory?city=&cohort=&lang=` | Advisory text with the published source of each sentence |
| `GET /outdoor-window?city=&cohort=` | Lowest-exposure window, relative reduction, absolute level, or "none identified" |
| `POST /policy/simulate` | Scenario result with sensitivity range |
| `POST /forecast/what-if` | Counterfactual forecast for adjusted inputs |
| `GET /model/explanation?forecast_id=` | Grouped driver contributions and the plain-language sentence |
| `GET /model/health` | Rolling error, rolling interval coverage, drift status, last retrain, last ingestion run |
| `GET /data/provenance` | Sources, licences, attribution text, last successful retrieval per source |

### P.2 Contract rules

- **Every response says how fresh it is**: `data_as_of`, `issued_at`, `model_version`, `sources`.
- **Errors are typed**, in one envelope, with correct status codes: 400 malformed request, 404 unknown city, 422 out-of-range value, 503 data unavailable with `retry_after`. The 1.0 behaviour of returning 500 with an exception string on malformed JSON is removed.
- **Inputs are validated against a schema** at the boundary. What-if adjustments are bounded to the range the interface offers.
- **Caching**: live data five minutes; a forecast until the next issue time.
- **Rate limiting** per client on the compute endpoints; CORS restricted to the application's own origin for `POST`.
- **Versioning** in the path; a breaking change is a new version.

```json
{
  "city": "Chennai",
  "forecast_for": "2026-10-08",
  "issued_at": "2026-10-07T12:30:00Z",
  "data_as_of": "2026-10-07T12:00:00Z",
  "aqi": { "expected": 92, "range_80": [74, 118] },
  "band_probability": { "Satisfactory": 0.61, "Moderate": 0.34, "Good": 0.05 },
  "dominant_pollutant": "PM10",
  "confidence": "moderate",
  "advisory": { "cohort": "asthma_copd", "band": "Moderate", "issued_from_quantile": 0.85,
                "target_under_warning_rate": 0.05 },
  "model_version": "2026.10-lgbm-cqr-3",
  "sources": ["OpenAQ (originating from CPCB)", "CAMS via Open-Meteo", "Open-Meteo forecast"]
}
```

The numbers in this example are illustrative of the format only.

## Q. Database schema

```sql
create table sources (
  source_id      text primary key,           -- 'openaq', 'cams_open_meteo', ...
  display_name   text not null,
  licence        text not null,
  attribution    text not null,
  is_official    boolean not null,           -- true only for a government feed
  is_modelled    boolean not null
);

create table stations (
  station_id     bigserial primary key,
  source_id      text references sources,
  source_key     text not null,              -- the provider's own identifier
  name           text, city text, state text,
  latitude       double precision, longitude double precision,
  first_seen     timestamptz, last_seen timestamptz,
  unique (source_id, source_key)
);

create table observations (
  station_id     bigint references stations,
  pollutant      text not null,
  averaging      text not null,              -- 'hour', 'day'
  observed_at    timestamptz not null,
  value          double precision,
  unit           text not null,
  retrieved_at   timestamptz not null,
  quality_flag   text not null,              -- 'ok','stale','flatline','out_of_range','spike'
  primary key (station_id, pollutant, averaging, observed_at)
) partition by range (observed_at);

create table weather_forecasts (
  latitude double precision, longitude double precision,
  variable text, valid_at timestamptz, run_at timestamptz,   -- run_at makes lead time explicit
  value double precision, source_id text references sources,
  primary key (latitude, longitude, variable, valid_at, run_at)
);

create table feature_snapshots (
  snapshot_id    bigserial primary key,
  station_id     bigint references stations,
  issue_time     timestamptz not null,
  feature_version text not null,
  features       jsonb not null,             -- exactly what the model saw; never rewritten
  unique (station_id, issue_time, feature_version)
);

create table model_versions (
  model_version  text primary key,
  trained_from   date, trained_to date,
  data_hash      text not null, feature_version text not null,
  hyperparameters jsonb, metrics jsonb,
  artefact_uri   text not null, artefact_sha256 text not null,
  deployed_at    timestamptz, is_active boolean not null default false
);

create table forecasts (
  forecast_id    bigserial primary key,
  station_id     bigint references stations,
  issue_time     timestamptz not null,
  target_date    date not null,
  model_version  text references model_versions,
  snapshot_id    bigint references feature_snapshots,
  expected       double precision, quantiles jsonb, band_probability jsonb,
  status         text not null,              -- 'issued','withheld_stale_data','low_confidence'
  unique (station_id, target_date, model_version)
);

create table forecast_verification (
  forecast_id    bigint primary key references forecasts,
  observed       double precision, absolute_error double precision,
  inside_interval boolean, band_error integer, verified_at timestamptz
);

create table ingestion_runs (
  run_id bigserial primary key, source_id text references sources,
  started_at timestamptz, finished_at timestamptz,
  status text, rows_written integer, error text
);
```

`alert_subscriptions`, `alert_events` and `evaluation_results` are added with the alerting and research-lab features.

## R. MLOps

| Cadence | Job | Output | Gate |
| --- | --- | --- | --- |
| Hourly | Ingest, validate, flag | `observations`, `ingestion_runs` | Retries with exponential back-off; failure recorded, never papered over |
| Daily, issue time | Feature snapshot → forecast → advisories | `feature_snapshots`, `forecasts` | Stations with stale data are marked withheld |
| Daily, next morning | Verify yesterday's forecast | `forecast_verification` | — |
| Weekly | Drift report: rolling MAE, rolling coverage, feature distribution shift | `/model/health` | Alert if coverage falls more than five points below nominal |
| Monthly | Retrain a challenger on the extended window; rolling-origin evaluation | Candidate in `model_versions` | **Promotion needs a person to approve** it, and requires the challenger to be no worse on *Poor*-or-worse days |
| On demand | Rollback | `is_active` flipped to the previous version | One command |

Recorded for every model: version, training window, data hash, feature version, hyperparameters, metrics, artefact hash, deployment time.

### Reproducibility

Retained from 1.0: one command rebuilds everything; seeds are fixed; no reported number is typed by hand. Added: a locked environment file; configuration separated from code; a data snapshot hash in every result file; and a `paper` build target that regenerates every table and figure in the manuscript from result files, so the paper cannot disagree with the experiments.

## Security and privacy

- **No account and no health record is needed** to use the product. The cohort is chosen from seven broad options and kept on the device.
- If alerts are added, the only personal datum is a contact address, stored with consent, encrypted at rest, and deletable by the user.
- Secrets live in the scheduler's and host's secret stores, never in the repository. Provider sample keys are not used in production.
- Response headers: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy (1.0 sends only HSTS).
- Dependencies are audited in continuous integration; 1.0 already moved off a Next.js release with a published vulnerability.
- The advisory is separated from clinical advice in the interface and in the API, and every advisory carries the disclaimer.
