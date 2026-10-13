# Post-paper extension audit

Checkpoint: 2026-10-13T19:16:03.423817+00:00. Research branch; code checkpoint `9ac8b5a607246ced7150bfa47591c3398d72b5d8`. Final test remains sealed.

Reused immutable run `54efbbe1af8a7e03c30a19060e6d2259b78949f62deb3eabe64e34143ef1a9c2`; development predictions and source checksums passed. No experiment was rerun. All accepted learners were fitted independently of the excluded floor surrogate. Their scores remain post-paper exploratory findings, not primary CAMS results.

| Method | Exact MAE | Exact pairs | Poor+ exact MAE | Severe reaches 401 |
| --- | --- | --- | --- | --- |
| persistence | 27.474 | 31622 | 64.983 | 147/306 |
| ridge_weather_same_rows | 44.475 | 31622 | 163.554 | 0/306 |
| ridge_history | 28.089 | 31622 | 87.393 | 1/306 |
| ridge_persistence_residual | 28.081 | 31622 | 87.334 | 1/306 |
| lgbm_history | 26.360 | 31622 | 87.118 | 0/306 |
| lgbm_persistence_residual | 26.360 | 31622 | 86.357 | 0/306 |
| lgbm_tail_weighted | 27.709 | 31622 | 81.731 | 0/306 |
| max_persistence_ridge | 28.095 | 31622 | 63.857 | 147/306 |
| ridge_weather_all_pairs | 43.857 | 38382 | 162.699 | 0/363 |

LightGBM history has lower point MAE than persistence, but its paired 95% interval includes zero. It reaches none of the 306 Severe lower bounds. The maximum of persistence and History Ridge preserves 147 threshold reaches and slightly reduces Poor+ MAE, while worsening overall MAE with a positive paired interval. No model is selected.

**Method exclusion:** `lgbm_censored_floor` trains on 401 as an exact label. Its original source and result are retained for audit, but it is excluded from accepted comparisons and future v2 fitting. The v2 runner fits every regression/quantile learner only on uncensored targets; a new regression test enforces this. Never run `source_v1.py` as an approved experiment.
