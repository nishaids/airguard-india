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
