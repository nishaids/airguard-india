# CAMS operational archive status

Checkpoint: 20 October 2026 (IST). Supersedes the 13 October checkpoint, which is preserved in git history. Final test sealed.

**Current manifest: 10 of 36 planned files verified, 2 running, 24 not yet submitted.** Frozen plan SHA-256 `952325f75dfc11e773dda90cbfe4ec4e883cda045a30d03c17578980ababeb6a` (unchanged): 507 00 UTC operational runs, 2025-02-17 to 2026-07-08, surface plus lowest model level, area 30.8 N / 70.8 E / 8.4 N / 94.0 E, 0.4-degree grid. Reanalysis and missing-month substitution are prohibited.

## What changed today

- The only request pending since 13 October (`0ffdede7`, June 2025 surface) returned **HTTP 404** when re-polled: the ADS server had deleted the result before anyone downloaded it. It was retired through a new reviewed path that keeps its ID on record (`retired_requests`); no other failure kind can be retired that way.
- The author **re-authorised submissions** of the remaining frozen jobs on 2026-10-20, one or two at a time (`submission_control.max_active = 2`). The worker polls every minute and downloads each result at once, so a finished result can no longer sit until it expires.
- June and July 2025 were submitted; both surface files are verified, both model-level files are running. Model-level files are slow: one earlier took 28.5 hours.

## Request table

| Month | Field group | Request ID | Status | Bytes | SHA-256 (prefix) |
| --- | --- | --- | --- | --- | --- |
| 2025-02 | surface | `30cb6db9` | VERIFIED_GRIB | 10,454,784 | 353a103e97ec |
| 2025-02 | model level | `a0e3264d` | VERIFIED_GRIB | 7,805,791 | c8fbc18b64b4 |
| 2025-03 | surface | `679e52de` | VERIFIED_GRIB | 27,008,192 | cddfa21527dd |
| 2025-03 | model level | `2e4f2f0c` | VERIFIED_GRIB | 20,194,737 | b1d310ab7a3c |
| 2025-04 | surface | `d0f52b0c` | VERIFIED_GRIB | 26,136,960 | 5b19907596dd |
| 2025-04 | model level | `3ba0572d` | VERIFIED_GRIB | 19,511,974 | e703d43b301d |
| 2025-05 | surface | `1d4a865b` | VERIFIED_GRIB | 27,008,192 | 025949192a64 |
| 2025-05 | model level | `819b3723` | VERIFIED_GRIB | 20,106,460 | 7783be665634 |
| 2025-06 | surface | `d07238c3` | VERIFIED_GRIB | 26,136,960 | e3c9bd339c0f |
| 2025-06 | model level | `dc0ac7fb` | running | — | — |
| 2025-07 | surface | `c7bc38cb` | VERIFIED_GRIB | 27,008,192 | d5879fc1379e |
| 2025-07 | model level | `97ecdff2` | running | — | — |
| 2025-06 | surface (retired) | `0ffdede7` | HTTP 404, provider-deleted | — | — |
| 2025-02-18 | probe (not a plan job) | `33a7789e` | VERIFIED (134-byte GRIB1, PM2.5, 3×3 cells) | 134 | see `cams_archive_status.json` |

Every verified file is re-hashed and decoded before use: forecast type, reference time, leads, valid times, fields, units, hybrid coefficients and grid are checked. Only months whose two halves are both verified enter station extraction.

## Counts the brief asks for

| | Count |
| --- | --- |
| Expected chunks | 36 |
| Verified | 10 |
| Running | 2 |
| Not yet submitted | 24 |
| Failed (unresolved) | 0 |
| Retired (provider-deleted, ID kept) | 1 |
| Duplicate requests | 0 |
| Paired months usable for the join | 4 (Feb-May 2025; June and July await their model-level halves) |
| Eligible development dates in the join | 103 (2025-02-19 to 2025-06-01) |

**External blocker:** ADS queue time. The first protocol-eligible fold (fold_05) needs CAMS through 2025-11-16, i.e. 10 more verified files (`CAMS_STATION_MATCHING_REPORT.md`).

**To continue acquisition** (resumable, never duplicates, never submits beyond the frozen plan):

```
.venv-live\Scripts\python.exe -m src.research.calibration.cams_acquisition --worker-hours 24
```

Then, after new pairs verify: `python -m src.research.calibration.cams_baseline`, `python -m src.research.calibration.primary_dataset`, `python -m src.research.calibration.primary_experiments` (preflight) and `python -m scripts.build_cams_matching_report`.
