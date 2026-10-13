# CAMS operational archive status

Checkpoint: 2026-10-13T20:05:39.026617+00:00. Research branch; code checkpoint `106c33eafac531a04dae99f19ec0005ae808ff6a`. Final test remains sealed.

Current manifest: **8/36 verified**, statuses `{'VERIFIED_GRIB': 8, 'running': 1}`. The submission worker is stopped and new requests are persistently paused. Original request IDs are retained; no new or replacement request was submitted by this reconciliation. Frozen plan SHA-256: `952325f75dfc11e773dda90cbfe4ec4e883cda045a30d03c17578980ababeb6a`.

The readiness audit independently rehashed and decoded each verified GRIB. Forecast type, reference time, leads, valid times, fields, mass units, hybrid coefficients and the 0.4-degree grid are checked. Only paired surface/model-level months enter station extraction. Reanalysis and missing-month substitution are prohibited.

Current join: 18,540 retained station-days, 180 stations, 100 cities, 103 dates, 11,634 exact targets and 7 censored Severe targets; 6,899 rejected targets remain visible. Availability violations: 0.

Availability guards pass under the disclosed nominal 00 UTC dissemination and observation-feed latency assumptions. Historical per-run publication times are not empirically verified.

| Nine reported ADS requests | Count |
| --- | --- |
| Server successful | 9/9 |
| Downloaded locally | 9/9 |
| Content-valid | 9/9 |
| Checksum-verified | 9/9 |
| Protocol-accepted primary archive chunks | 8/9 |

The remaining valid artifact is the accepted original probe, excluded from the 36 primary chunks. Total known request IDs: 10; nine reported successes plus the additional pre-existing request below.

| Request ID | Scope | Bytes | Initialization dates | Content |
| --- | --- | --- | --- | --- |
| 819b3723-5f98-41f4-a190-fe2bd386c851 | development_chunk | 20106460 | 2025-05-01 to 2025-05-31 | VALID |
| 1d4a865b-e61b-4213-9e5c-ebc373a915f6 | development_chunk | 27008192 | 2025-05-01 to 2025-05-31 | VALID |
| 3ba0572d-52ca-45c9-bb7d-c5599c308499 | development_chunk | 19511974 | 2025-04-01 to 2025-04-30 | VALID |
| d0f52b0c-4597-477c-820d-894b14c369f4 | development_chunk | 26136960 | 2025-04-01 to 2025-04-30 | VALID |
| 2e4f2f0c-d537-435f-8eb5-17f81c8c0532 | development_chunk | 20194737 | 2025-03-01 to 2025-03-31 | VALID |
| 679e52de-7e10-4653-b606-36b0543ab515 | development_chunk | 27008192 | 2025-03-01 to 2025-03-31 | VALID |
| a0e3264d-c34c-46bb-a111-bab4bacb7af8 | development_chunk | 7805791 | 2025-02-17 to 2025-02-28 | VALID |
| 30cb6db9-0e4f-4da5-94c9-fb53a702afc8 | development_chunk | 10454784 | 2025-02-17 to 2025-02-28 | VALID |
| 33a7789e-bdec-47b4-9f9e-9d92ed41c976 | probe | 134 | 2025-02-18 | VALID |

Additional pre-existing request(s): [{"request_id": "0ffdede7-1a5c-4ea7-a58e-2eafaf510a76", "job_sha256": "82b88b23bc42bbd17d1e9832f967a9814155527c61920655874a8b7069cbb31a", "status": "running", "submitted_at_utc": "2026-10-13T19:44:54.415976+00:00", "reference_date_range": ["2025-06-01", "2025-06-30"], "reason": "Pre-existing request outside the nine reported successes; preserved, not polled or downloaded by this reconciliation."}]. These were not polled or downloaded by this reconciliation; status is last recorded.

Invalid/unverified artifacts: [].

The 134-byte probe is a complete GRIB edition 1 message: `GRIB` header, length 134, `7777` terminator, ECMWF centre `ecmf`, CAMS class `mc`, operational stream `oper`, forecast type `fc`, surface PM2.5 (`paramId=210073`, kg m**-3). It contains nine finite nonmissing values on a 3 by 3, 0.4-degree grid covering 29.2–28.4 N and 76.8–77.6 E. Initialization: 2025-02-18 00:00 UTC; lead: 24 h; valid: 2025-02-19 00:00 UTC. Packing: grid_simple, 24 bits/value. It contains binary forecast data, no HTML/XML/error response.

Exact decoded values and all 134 bytes in hexadecimal, per-request checksums, server timestamps, parameter units and valid-time ranges are recorded in `results/research/cams_archive_status.json`.

Evidence: `results/research/final_test_readiness.json`, `cams_station_join_manifest.json`, and the existing acquisition/alignment manifests. Only explicit existing IDs may be re-polled; new submissions remain paused until the author changes this instruction.
