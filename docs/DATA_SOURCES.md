# AirGuard production data sources

Reviewed 2026-10-10. This is the existing non-commercial research project. A
commercial release needs a fresh licence review; no paid service was introduced.

| Provider | Purpose / nature | Endpoint / key | Terms and attribution | Cache / fallback |
|---|---|---|---|---|
| Open-Meteo / CAMS global | Six pollutant concentrations; modelled conditions and forecasts, not stations | `air-quality-api.open-meteo.com/v1/air-quality`, `domains=cams_global`; no key for non-commercial tier | [API methodology](https://open-meteo.com/en/docs/air-quality-api), [terms](https://open-meteo.com/en/terms), [pricing/licence](https://open-meteo.com/en/pricing). Attribute Open-Meteo and CAMS / Copernicus; identify AirGuard's derived AQI modification. CC BY 4.0 data; hosted free API restricted to non-commercial use. | 1h shared 0.4° grid cache; explicitly stale up to 6h on failure, then unavailable. Raw forecast inputs preserved in immutable issued artifacts. No fabricated model run timestamp. |
| Open-Meteo weather | GFS seamless forecast, including supported boundary-layer height | `api.open-meteo.com/v1/forecast`; no key for non-commercial use | Same terms. Attribute Weather data by Open-Meteo.com. Variables, returned units and configured model retained. | 2h cache; visibly stale to 6h, then unavailable. Optional context; no AQI adjustment. |
| Open-Meteo / GeoNames | India place and provider-dependent PIN-code search | `geocoding-api.open-meteo.com/v1/search`, `countryCode=IN`; no key | [Geocoding documentation](https://open-meteo.com/en/docs/geocoding-api), [GeoNames](https://www.geonames.org/). Attribute both. | 7d cache, stale results up to 30d. Empty postal result stays empty; no city guess. Coordinates accepted within the disclosed regional service box. |
| OpenAQ v3 / named upstream owners | Station discovery and actual hourly pollutant measurements | `api.openaq.org/v3/locations`, `/sensors/{id}/hours`; server-side `OPENAQ_API_KEY` in `X-API-Key` | [Terms](https://docs.openaq.org/about/terms), [hours](https://docs.openaq.org/resources/measurements), [limits](https://docs.openaq.org/using-the-api/rate-limits). Attribute OpenAQ AND provider/owner. Per-station licence metadata retained; redistribution must respect each upstream licence. Hosted API must complement OpenAQ, not duplicate its core offerings. | Small 0.01° discovery cache for 30m; distances rechecked per requested coordinate. At most two stations and one sensor per pollutant. Station series, raw unit/value, hourly coverage, flags and retrieval time retained. Missing/stale/insufficient measured AQI falls back to labelled CAMS. No ppb/ppm conversions without actual conditions. |
| CPCB via data.gov.in | Optional government feed; raw measured context, not a complete time-series AQI | Existing data.gov resource; server-side `DATA_GOV_API_KEY` | [India open-data licence](https://www.data.gov.in/government-open-data-license-india), [CPCB report](https://airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf). Attribute CPCB and data.gov.in. | Legacy ingestion preserved. Current local network refuses `api.data.gov.in:443` with WinError 10061, before any HTTP response. Never rename another feed CPCB. |
| NASA FIRMS | Satellite thermal/fire detections only | Existing NASA VIIRS area CSV endpoint; server-side `NASA_FIRMS_MAP_KEY` | [FIRMS data use](https://firms.modaps.eosdis.nasa.gov/faq/), [NASA Earthdata policy](https://www.earthdata.nasa.gov/engage/open-data-services-and-software/data-and-information-policy). Attribute NASA FIRMS / LANCE and VIIRS product. | Existing hourly local ingestion retained. Nationwide API displays stored detections from the preceding 24h within 50km, with acquisition time. It never changes AQI using hotspots. No detections is not proof of no fires. |

Provider quotas are enforced in shared PostgreSQL budgets. Open-Meteo calls
across air, weather and geocoding share caps of 500/minute, 4,000/hour and
9,000/day, below the published non-commercial hosted limits. OpenAQ is capped at
55/minute and 200/hour by this product. At most 50 previously uncached CAMS
grid cells can be fetched per UTC day. Cached locations remain available when
new-grid limits are reached. These conservative limits can reject bursts and
are not a capacity guarantee. Retries are bounded; 429 is respected.

Coordinates of searched/selected places are cached in the private database;
there are no user profiles or persisted health cohorts. Provider requests can
be logged by the provider under its own privacy terms. Browser geolocation is
requested only after a user action. Health cohort selection stays client-side.

No upstream data is sold or presented as official CPCB AQI. Raw hourly records
remain private with RLS and no public policies. Issued forecast artifacts and
valid verification evidence are append-only. A future retention policy must
preserve issued artifacts and their evidence while budgeting Supabase storage;
automatic destructive pruning is intentionally not part of this release.

## AQI derivation and guidance

Authoritative implementation: `src/nationwide/aqi.py`, methodology
`airguard-cpcb-2014-v1`. CPCB final report Table 3.11, sections 3.5 and 3.7:
continuous interpolation between the closed upper concentration breakpoints,
maximum sub-index, minimum three pollutants including PM, minimum sixteen
distinct hourly bins per pollutant. CO/O3 need eight consecutive valid hours.
High ozone's mathematical bands use one-hour concentration. Above the last
closed severe threshold AirGuard reports a **lower bound ≥401**, not an
invented upper concentration endpoint or exact AQI.

Current values use trailing windows. Tomorrow is the full IST calendar day;
24-hour pollutants use that day's valid hourly mean, and CO/O3 use the maximum
complete trailing eight-hour mean ending in the day. This daily forecast gas
maximum and the two-hour instantaneous relative-exposure selection within 06:00–21:00 IST are disclosed AirGuard
conventions, not official CPCB forecast bulletins. Hourly AQI is rolling, not
an instantaneous concentration index. Source resolution is approximately 45km;
hourly API data interpolate native three-hour CAMS output.

General English exposure rules are deterministic and reviewable in
`webapp/app/lib/i18n.ts`. They draw on CPCB category health statements and
[WHO personal interventions guidance](https://www.who.int/news-room/questions-and-answers/item/personal-interventions-and-risk-communication-on-air-pollution).
They are not a diagnostic or individual clinical risk model. Hindi/Tamil are
disabled scaffolds pending explicit translation review; no translated health
advice ships automatically.
