# AirGuard 2.0 live integration acceptance — 10 October 2026

This is the earlier ingestion-only milestone. The nationwide transformation
and current deployment status supersede it in `nationwide_handover.md`.

The existing AirGuard models and forecast pages are unchanged. The new live
section on the overview page displays validated Supabase records, their actual
source, observation time, current freshness, upstream provider and quality flags.
It does not claim to make a new measured-input tomorrow-AQI prediction.

## Source verification

| Source | Actual result | Stored after verification |
| --- | --- | ---: |
| CPCB/data.gov.in | Connection refused; no HTTP response | 0 observations |
| OpenAQ v3 | Live API; 10 currently usable PM2.5 readings across a subset of cities | 1,510 observations |
| NASA FIRMS | Live VIIRS NOAA-20 and NOAA-21 feeds | 1,512 detections |
| Open-Meteo | Live GFS weather forecasts for 12 city reference points | 1,356 forecast hours |

There are 133 stations and 1,976 quality flags. Counts are cumulative, including
the pre-existing records. The first full acceptance cycle added 10 OpenAQ
readings, 738 detections and 732 forecast hours; a second cycle added two newer
OpenAQ readings. A third cycle added zero rows for all three successful sources,
with 1,498, 738 and 732 duplicates correctly reported, respectively.

Most of OpenAQ's government-monitor readings remain dated 7 October, and some
gas unit labels are suspect. Old values remain archived with their quality flags
and are excluded from the current usable measurement count. The current sample
is PM2.5 from AirGradient, Clarity and AirNow upstream providers. OpenAQ records
remain labelled **OpenAQ**, including records whose upstream provider is CPCB.

FIRMS thermal detections are regional context, not AQI or smoke concentration.
The bounding box includes neighbouring countries. Weather forecasts retain run,
valid and first-retrieval timestamps; fetching the same run does not overwrite
the previously archived vintage.

## Exact CPCB network failure

`requests.exceptions.ConnectionError`, wrapping `urllib3.exceptions.NewConnectionError`:

> HTTPSConnection(host='api.data.gov.in', port=443): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it

The configured data.gov.in resource was requested using the local API key;
the key is redacted in logs and responses. This is a TCP connection failure,
not an HTTP 401/403 response, an empty dataset, or proof that the key is invalid.
No substitute was stored under CPCB's name. A different network or a permitted
cloud execution environment is needed to distinguish local network restrictions
from service-side rejection. No network settings were changed.

## Implemented and verified

- `DATABASE_URL` presence verified without displaying its value; migration runner
  executed and confirmed the schema is up to date. Direct SSL Supabase connection
  and the serverless vendored package both read the real data successfully.
- Database uniqueness keys checked for air observations, weather vintages and
  fire detections. Replaying existing records creates no duplicate rows. Quality
  flags are inserted only with new records. Provenance completeness is recorded
  in `results/live_integration_acceptance.json`.
- Freshness is recalculated on every `/api/live` request: fresh through 90
  minutes, delayed through 180 minutes, stale through 24 hours, unavailable
  beyond that. Excessively future-dated observations cannot appear fresh.
  Expiry is tested against the real stored data with a later clock.
- `GET /api/live` reads the private `airguard` schema through the server. It
  returns source run statuses, cumulative totals, bounded latest measurement
  samples, weather and regional fire context. Optional `?city=Delhi`; unsupported
  cities return HTTP 400. Database errors return HTTP 503 without connection
  details. Responses use `Cache-Control: no-store` in the deployed handler.
- Browser → Next.js development rewrite → Python handler → Supabase → frontend
  verified, including city filtering and source labels. No browser console errors
  were observed. Configured secret values were checked absent from the API response.
- Local Windows task **AirGuard 2.0 Live Ingestion** is enabled hourly. Its action
  uses the existing Python interpreter and project working directory. Four
  providers run independently, with one DB connection each, a session advisory
  lock to prevent overlap, and Task Scheduler's `IgnoreNew` policy. The configured
  DATABASE_URL uses Supabase's session pooler, compatible with this lock.
- The registered task was launched and completed real ingestion. Exit code 1
  means a source failed (CPCB here); individual success/failure and duplicate
  counts remain in `airguard.ingestion_runs` and the rotating redacted
  `results/ingestion.log`. Log output and exception tracebacks redact secrets.
- All **106 tests passed** with real database checks. `npm run build` completed
  successfully. No training command ran and no model artifacts changed.

The scheduler runs while this Windows user is logged in and the computer is
awake. `StartWhenAvailable` handles missed triggers after the machine returns.
It is not an always-on cloud scheduler. Reinstall or update safely with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_ingestion_task.ps1
Start-ScheduledTask -TaskName 'AirGuard 2.0 Live Ingestion'
python scripts/verify_live_integration.py
```

## Deployment readiness and security

The Vercel project `nishanth-s-projects-e335f110/webapp` was inspected through
the authenticated CLI. Its production `DATABASE_URL` was configured as a Vercel
**Secret**, supplied through stdin from the local `.env` without printing it or
putting its value in process arguments. Only the database secret is needed by
the public read endpoint; source API keys remain local to the ingestion worker.
Python runtime dependencies now include Requests and psycopg2. The live Python
function and its bundled ingestion package are included in `vercel.json`.

No deployment was created or promoted. The new production secret will be used
by the next approved deployment, not automatically by an already-built deployment.
Hosted `/api/live` still needs verification after production deployment approval.

Supabase's security advisors reported only informational notices for the eight
private tables with RLS enabled and no policies. This intentional server-only
schema remains closed to anonymous/authenticated Data API clients; no public
RLS policies or privileged database functions were added. Existing historical
orphan `RUNNING` audit entries were left intact; new tests use rollback-only
transactions and do not persist synthetic ingestion runs.

## Before a real tomorrow-AQI prediction

1. Restore a dependable, current government-monitor source and verify CPCB's raw
   value semantics/units. Resolve suspect OpenAQ gas unit labels against upstream
   documentation or station evidence.
2. Collect/backfill sufficiently complete pollutant history and forecast
   vintages. Current coverage is only 10 usable PM2.5 readings, not a complete
   multi-pollutant dataset for 12 cities.
3. Validate cross-source station matching with real paired records; build
   point-in-time features with explicit gaps, city aggregation and issue cutoffs.
4. Evaluate tomorrow-AQI predictions against future measured outcomes and
   persistence baselines before connecting these inputs to the production model.
   Model retraining is a separate future phase.
5. Move the already-tested ingestion worker to an approved always-on runtime and
   monitor delivery, coverage and quality over multiple days. Approve a Vercel
   production deployment when ready to publish the new live section/API.
