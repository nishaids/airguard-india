# Claim-evidence matrix

## Inherited checkpoint (12 October 2026)

The following original checkpoint is preserved as historical evidence. Current archive/prospective counts are in the continuation section below.

This continuation makes no primary CAMS improvement or clinical-benefit claim.

| Claim | Evidence | Scope |
|---|---|---|
| Stable deployed application | [results/release/website_deployment_verification.json](results/release/website_deployment_verification.json) | Deployed 35c2ca0; research branch commits do not change this deployment |
| Fresh frontend preflight passes | [results/release/master_continuation_preflight.json](results/release/master_continuation_preflight.json) | Lint, types, 43 unit tests, production build |
| 16 live browser checks pass | [results/research/master_checkpoint.json](results/research/master_checkpoint.json) | Eight routes, desktop and mobile; fresh actual run |
| 6/36 operational chunks verified | [results/research/final_test_readiness.json](results/research/final_test_readiness.json) | GRIB decoded and checksummed; incomplete paired months |
| 7,560 guarded development station-days | [results/research/cams_development_alignment.json](results/research/cams_development_alignment.json) | Final rows filtered before materialisation; rejected/censored targets retained |
| Preliminary Ridge improves climatology, not established against persistence | [results/research/preliminary_latest.json](results/research/preliminary_latest.json) | NON_CAMS_PRELIMINARY; never a raw-CAMS comparison |
| Primary model improvement | [FINAL_TEST_READINESS_REPORT.md](FINAL_TEST_READINESS_REPORT.md) | NOT ESTABLISHED; model selection pending |
| 24 real prospective forecasts | [results/research/prospective_audit.json](results/research/prospective_audit.json) | 2 target days; 0 verified days; no retrospective station binding |
| Six-page IEEE journal development draft | [paper/journal/draft_manifest.json](paper/journal/draft_manifest.json) | Compilation and visual inspection do not establish scientific readiness |
| Final test | [FINAL_TEST_READINESS_REPORT.md](FINAL_TEST_READINESS_REPORT.md) | BLOCKED; no scoring; later fresh explicit approval required |

Full protocol/data hashes: [alignment manifest](results/research/cams_development_alignment.json). Earlier project defense claims remain in [the original matrix](docs/defense/CLAIM_EVIDENCE_MATRIX.md).


<!-- BEGIN CODEX HANDOFF -->

## Submitted paper snapshot

The exact six-page snapshot is `paper/conference_final/main.pdf` (SHA-256 `460d5b85828dd273a4edcb83289ae3392d40bd52b7372f68f297e550761d4598`). Source, bibliography, assets and historical numerical findings are unchanged. Its figures/tables describe non-CAMS development evidence, not a primary CAMS or final-test result. The archived 6/36 statement is the paper's frozen acquisition checkpoint.

## Post-paper project extension

| Claim | Script / artifact | Population and identity | Status |
| --- | --- | --- | --- |
| Current CAMS join | primary_dataset.py; results/research/cams_station_join_manifest.json | 12,960 rows; 180 stations; 72 dates; SHA 0dd0f06987815dc95a4a07ab10d15c33637b37c660928a5a3151b0423e478412 | Guarded; 0 availability violations; no primary fit |
| Severe / interval / warning extension | extensions.py; docs/research/DEVELOPMENT_EXTENSION_AUDIT.md | Run 54efbbe1af8a7e03c30a19060e6d2259b78949f62deb3eabe64e34143ef1a9c2; 31,622 exact history pairs, 306 censored Severe | Exploratory; floor-surrogate excluded; none selected/deployed |
| Frozen-cohort sensitivity | docs/research/STATION_SURVIVORSHIP_SENSITIVITY.md | 158 stations; 92 cities; 36,993 exact pairs; same extension run | Qualitative findings preserved; lost-monitor bias unresolved |
| Provider transport receipts | src/nationwide/providers.py; tests/test_input_receipt.py | Request/response timestamps; raw JSON hash unchanged; initialization remains unknown when unavailable | Tested; production release recorded separately |
| Backend correctness | results/research/test_validation.json; logs/codex-continuation-backend.xml | 658 passed separately; source-bound offline 653 passed / 5 skipped; 4 database integrations | Current source fingerprint verified |
| Frontend correctness | results/release/codex_continuation_preflight.json | 43 unit tests; lint/type/build | PASS |
| Prospective real collection | results/research/prospective_audit.json | 36 forecasts; 3 target days; 0 verified days; 0 bound stations | Immutable; no historical repair; 30-day gate false |
| Primary model improvement / lock | docs/research/MODEL_SELECTION_REPORT.md | No eligible real primary fold | NOT ESTABLISHED / NOT READY |
| Final test | docs/research/FINAL_TEST_READY_FOR_AUTHOR_APPROVAL.md | 10 July–7 October 2026 | SEALED; BLOCKED; fresh later approval required |

The extension audit records raw prediction/source hashes and metadata-only date isolation checks. New analyses cannot replace the submitted-paper snapshot. No clinical, world-first or guaranteed risk-control claim is made.

<!-- END CODEX HANDOFF -->
