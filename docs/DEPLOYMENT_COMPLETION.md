# Deployment completion — 20 October 2026

**Status: PRODUCTION_DEPLOYED_AND_VERIFIED.** A working deployment is not evidence of forecast accuracy; research status is reported separately.

| Item | Value |
| --- | --- |
| Live URL | https://webapp-phi-taupe.vercel.app (existing project and domain) |
| Deployment ID | `dpl_5r2cg4ZKdAtgRMHo1TpoXh2653L9` (second release of the day; the first was `dpl_4YKByhjbQLA8Z7Tsi9U7PXSP44Bd`) |
| Deployed commit | `7b882fa4b157ab5aa31085652c24999591fef005` (branch `research/station-calibration`, pushed to GitHub) |
| Promoted | 2026-10-20, twice in the early afternoon IST |
| Staged checks | 31 of 31 passed on each protected candidate |
| Public checks | 37 of 37 passed on the live domain after each release |
| Security headers | CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Permissions-Policy present |

## What changed for users

- **Track record.** The home page used to print error figures for any group, however small; on the day of release that meant figures from one or two forecasts on one day (for example, a bias of +249.5 for "Maharashtra, Very Poor"). A group is now scored only once it holds 30 checked forecasts over 7 different days. Today no group qualifies, and the page says so: 48 forecasts checked on 3 target days.
- **Freshness.** When two refreshes of the same place overlapped, the slower one cached two-hour-old CAMS data for up to ten minutes, so the default location showed "STALE" although fresh data existed. Such summaries are now cached for 30 seconds at most.
- **Research status.** The public readiness file reports the CAMS archive as acquiring (it had said paused).
- **How far to trust a modelled value** (second release). The page now states that, on 9,510 station-days of development data, the raw CAMS-based AQI missed measured values by 93 points on average and ran 83 high (repeating the measured value missed by 26), and warns when ozone leads the estimate, since CAMS ozone averaged 2.6 times the measured value. Source: `docs/research/RAW_CAMS_DEVELOPMENT_DIAGNOSTIC.md`. Nothing is corrected.

## How it was released

1. Release preflight: lint, type check, unit tests (44, then 45) and production build pass (`results/release/website_preflight.json`).
2. Python suite 681 passed; source-bound offline validation 672 passed, 5 skipped (`results/research/test_validation.json`).
3. A production candidate was staged without the live domain. **The first candidate was not promoted**: staging showed that summaries cached by the old code carried track-record cells the new page would reject for up to ten minutes. Fixed in `6f4da73`, restaged, re-checked.
4. Promoted, then the public smoke test and a browser check of the track-record section.

No experimental correction, interval, research model, paper or credential is in the upload. The sealed final test was not accessed.

Evidence: `results/release/release_20261020.json`, `results/research/staged_production_acceptance.json`, `results/research/production_acceptance.json`.

## Known issues

- A first visit to an uncached place takes about 20 seconds while providers are fetched; the page shows an honest loading state.
- The official CPCB feed (data.gov.in) still fails: the host now answers but its backend returned HTTP 502 after about 60 seconds.
- Measured outcomes for verification remain scarce, because OpenAQ's copy of CPCB monitors has gaps.
