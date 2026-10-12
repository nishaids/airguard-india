# Claim-evidence ledger

Status vocabulary: VERIFIED, DEVELOPMENT ONLY, FINAL TEST VERIFIED, PROSPECTIVE ONLY, PENDING, UNSUPPORTED. No row currently receives FINAL TEST VERIFIED. Confidence is a qualitative audit judgment, not a forecast probability. Paths below are repository-relative.

| Claim | Evidence | Source artifact | Confidence | Status | Can say in demo? | Can say in viva? |
| --- | --- | --- | --- | --- | --- | --- |
| Measured targets built with v3.1 QC | Verified measured report and rejection ledger | results/research/measured_dataset.json | High within audited scope | VERIFIED | Yes, with counts/date scope | Yes |
| Dataset reproducible in fresh checkout | Raw-input reconstruction report | results/research/non_cams_clean_clone_reproduction.json | High; reused runtime | VERIFIED | Yes, disclose scope | Yes |
| Strict Ridge beats climatology | Paired development MAE/CI | preliminary_latest.json | Development only | DEVELOPMENT ONLY | Yes, label non-CAMS | Yes, label non-CAMS |
| History Ridge beats persistence | CI includes zero | preliminary_latest.json | Not established | UNSUPPORTED | No | Explain negative result |
| CAMS probe is an operational forecast | Decoded run/lead/valid/PM/grid checksum | cams_ads_probe.json | High for one field | VERIFIED | Yes if verified status | Yes |
| Complete primary CAMS archive/baseline | Collection manifest incomplete | cams_development_acquisition.json | Pending | PENDING | No completion claim | Explain status |
| AirGuard correction improves CAMS | No primary comparison yet | primary.py is infrastructure only | Unknown | PENDING | No | State experiment pending |
| Final test verified | No committed selection lock/evaluation | MODEL_SELECTION_LOCK absent | Not established | PENDING | No | State sealed |
| Thirty-day prospective skill | Real verified-day count below requirement | prospective_audit.json | Not established | PENDING | No | Quote actual count |
| Live prospective forecasts exist | Immutable ledger audit | prospective_audit.json | Within audit scope | PROSPECTIVE ONLY | Yes, not skill | Yes |
| Street-level precision | Coarse grid and no validation | providers.py / CAMS grid | Unsupported | UNSUPPORTED | No | Explicitly deny |
| Medical benefit | No clinical outcome study | advisory methods only | Unsupported | UNSUPPORTED | No | Explicitly deny |
| World first | No completed exhaustive novelty proof | literature review access limitations | Unsupported | UNSUPPORTED | No | Explicitly deny |
| Failure handling is tested | Unit/component/E2E artifacts | results/project_hardening/verification.json | Within tested scope | VERIFIED if tests pass | State actual checks only | Yes, with limits |
| Million-user production ready | No load benchmark | cost/scalability plan | Unknown | UNSUPPORTED | No | Describe required capacity tests |
| Research Severe performance adequate | All strict preliminary Severe forecasts below 401 | preliminary_latest.json | Evidence against claim | UNSUPPORTED | No; disclose failure | Disclose failure |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
