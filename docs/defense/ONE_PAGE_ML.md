# ML in one page

Primary ladder: raw CAMS, climatology, persistence, direct Ridge/LightGBM/XGBoost and their residual variants. Residual = exact measured AQI minus the frozen issue-time CAMS index; add the same baseline back at inference. Standardise Ridge inputs and fit imputation/scaling on training rows only. Tune inside each fold’s training dates. Carry forward the lowest mean rolling-fold MAE, preferring simpler learners on ties, or raw CAMS if no learner wins.

Severe targets are >=401 lower bounds: exclude exact regression fitting/error, retain warning/exceedance/shortfall checks. Conformal intervals use separate chronological calibration days and cannot guarantee subgroup or time-dependent coverage. No primary model has been selected while the complete CAMS archive is pending.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
