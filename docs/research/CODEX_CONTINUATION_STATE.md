# Codex continuation state

## Current branch

research/station-calibration

## Last commit at recovery

b41022197f31cd5b7375dfc2e8077550ac4048e3

## Uncommitted files

```text
M FINAL_TEST_READINESS_REPORT.md
 M docs/research/OPERATIONAL_CONTINUATION.md
 M results/project_hardening/all_python_tests.json
 M results/release/secret_audit.json
 M results/research/cams_development_acquisition.json
 M results/research/cams_development_alignment.json
 M results/research/cams_raw_baseline_derivation.json
 M results/research/final_test_readiness.json
 M results/research/test_validation.json
 M scripts/verify_live_release.py
 M src/research/calibration/cams_acquisition.py
 M src/research/calibration/primary.py
 M src/research/calibration/primary_dataset.py
 M src/research/calibration/validation.py
 M tests/test_calibration_cams_acquisition.py
?? CLAIM_EVIDENCE_MATRIX.md
?? logs/
?? paper/conference/main.blg
?? paper/conference_final/
?? paper/journal/main.blg
?? paper/station_calibration_skeleton.pdf
?? results/release/current_live_route_smoke.json
?? results/release/master_continuation_preflight.json
?? results/research/cams_archive_validation_checkpoint.json
?? results/research/development_extensions.json
?? results/research/extensions/
?? results/research/master_checkpoint.json
?? results/research/primary_development/
?? results/research/primary_development_preflight.json
?? results/research/test_validation_snapshots/20261012T152257Z-44fbb25a9daf.json
?? scripts/record_master_checkpoint.py
?? src/research/calibration/extensions.py
?? src/research/calibration/primary_experiments.py
?? src/research/calibration/primary_uncertainty.py
?? tests/test_development_extensions.py
?? tests/test_primary_experiments.py
?? tests/test_primary_uncertainty.py
```

## Completed Claude work

The new `paper/conference_final/` submission snapshot, measured-data analyses and development-only extension artifact `54efbbe1...` are present. The existing measured semantic hash and locked protocol are preserved. Seven operational CAMS chunks are verified, with a sequential worker running under existing IDs. The partial v3 alignment has 12,960 station-days over 72 dates. Earlier production release and test evidence are present.

## Partial work

Primary experiment and uncertainty modules, transport-error recovery, extension tests, current archive/alignment reports and the paper snapshot are not yet committed. The primary preflight references the older 42-date join and needs refresh against the current 72-date join. No model-selection lock exists.

## Remaining work

Audit inherited code and immutable artifacts; preserve the six-page paper; complete current backend/frontend/browser/security and provenance checks; record exploratory findings separately; update reproducibility, limitation and final-gate reports; commit logically and push the research branch. Release only independently tested production-safe changes.

## Blockers

The incomplete CAMS archive supplies no protocol-eligible temporal validation fold. Primary comparisons, primary model selection and the selection lock remain blocked by coverage. Prospective station bindings and verified outcomes require actual new issue-time records; historical records cannot be repaired after the outcome. The final interval remains sealed and this handoff does not authorize scoring.

## Preservation evidence

`results/research/codex_continuation_recovery.json` captures initial status and checksums for the paper, protocol and measured summary. No reset, deletion, restoration or duplicate download request was performed.


<!-- CONTINUATION COMPLETION -->

## Completed since recovery

The six-page snapshot was committed unchanged (98c39ed). Guarded primary infrastructure and independently audited exploratory extensions were committed (e02f23c); the exact-401 surrogate is excluded from future fitting. Receipt provenance and current-source validation evidence were committed and pushed (9ac8b5a), then safely deployed and verified. Backend/full offline/database, frontend/build and 37 public/28 browser checks passed. The stopped ADS worker was re-polled under its existing ID and resumed as one finite 24-hour worker. No duplicate request, final scoring or paper rewrite occurred.

Primary archive coverage remains 7/36 with one running job; the current 72-date join cannot support a legitimate model lock. See AIRGUARD_FINAL_COMPLETION_REPORT.md and FINAL_TEST_READY_FOR_AUTHOR_APPROVAL.md for the evidence-backed blocked gate. Generated local diagnostics and prediction caches remain on disk; important structured evidence is committed separately.

## Current checkpoint: 14 October 2026, existing requests only

This checkpoint supersedes the acquisition counts in the historical recovery notes above. All nine author-reported ADS successes were reconciled against original request IDs and rechecked server-side: eight complete development GRIB chunks and the original 134-byte probe. All nine artifacts are local, content-valid and checksum-verified. The probe is one complete GRIB1 PM2.5 operational forecast containing nine grid values; it is accepted as a probe and excluded from the 36 primary chunks. Overall archive: **8/36**.

The earlier worker had also submitted request `0ffdede7-1a5c-4ea7-a58e-2eafaf510a76` at 01:14:54 IST before this reconciliation. It covers June 2025 surface fields, is preserved separately and was not polled or downloaded in this run. Thus the repository knows ten request IDs including the probe, while this run's scope is the nine reported successes. The submission worker is stopped; `submission_control.new_requests_authorized=false` persists the author's prohibition. No new request, duplicate window or replacement was submitted by this run.

The rebuilt development join has **18,540 rows, 180 stations, 100 cities and 103 dates** (19 February–1 June 2025): 11,634 exact targets, 7 censored Severe outcomes and 6,899 retained rejected targets. All rows pass the strict availability guard under the disclosed nominal dissemination/feed-latency assumptions; violations and target-support mismatches are zero. Alignment SHA-256: `e9ecca99412bf916fe4ba6e7fc65eee0dd758409f1d490b866a8522b9d9f646d`.

Preflight `5c98aa20410529a6439903bd05b18d529d1a15c693142e7aa56934fdd89c4c27` reports **zero eligible primary folds**. The 120-valid-training-days station requirement and complete declared evaluation windows are not satisfied. No model was fitted or selected and no `MODEL_SELECTION_LOCK` was created. Final test **2026-07-10 through 2026-10-07 remains sealed**. All 64 protected paper/protocol/measured-summary hashes match the recovery baseline; the measured dataset's full-file checksum is unchanged. Current source-bound offline tests: 664 passed, 5 skipped, 4 deselected.

The required stop at an insufficient-fold checkpoint applies now. See `CAMS_ARCHIVE_STATUS.md`, `MODEL_SELECTION_REPORT.md`, `FINAL_TEST_READY_FOR_AUTHOR_APPROVAL.md` and `results/research/cams_archive_status.json`. New ADS acquisition remains paused unless the author explicitly changes that instruction; final-test approval is not requested while the development gate is blocked.
