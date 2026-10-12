# Uncertainty and advisory trade-offs: verified preliminary only

These aggregates are station-day weighted from the existing twelve chronological non-CAMS validation artifacts. They are not CAMS correction, final-test or clinical results. Width uses all rows returned by each method; exact coverage excludes censored labels. Mondrian unsupported rows are listed separately.

| Method | Exact validation pairs | Weighted exact coverage | Weighted mean width (AQI) | Unsupported rows |
| --- | --- | --- | --- | --- |
| split_0.8 | 38382 | 0.782 | 123.6 | 0 |
| split_0.9 | 38382 | 0.876 | 169.2 | 0 |
| cqr_0.9 | 38382 | 0.871 | 162.4 | 0 |
| mondrian_0.9 | 38159 | 0.870 | 166.4 | 223 |

Nominal coverage does not establish conditional reliability. In fold_01 the split-80 interval covered zero of 35 exact Very Poor targets; its Poor-or-worse coverage was also zero among 48 pairs. Inspect every severity/season/region artifact rather than quoting a pooled average alone. Severe upper endpoint >=401 is lower-bound compatibility, not identified coverage of the unknown true index.

| Policy | Validation pairs | Weighted under-warning | Weighted over-warning |
| --- | --- | --- | --- |
| P0 | 38745 | 0.271 | 0.247 |
| P1 | 38745 | 0.264 | 0.236 |
| P2 | 38745 | 0.142 | 0.417 |

P0 uses the point category; P1 the calibrated median; P2 the fixed calibrated 0.75 quantile. P3 selects the smallest candidate satisfying the declared calibration-window empirical target; inspect each fold’s target-specific feasibility and held-out errors in preliminary_latest.json. Dependent days prevent a general finite-sample health-risk guarantee. Lower under-warning can cost more over-warning, and no cohort-specific clinical outcomes were collected.

The moving seven-day date-block intervals and Holm-adjusted paired comparisons remain in the immutable result artifact; this file does not invent a new significance test or recalibrate any policy.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
