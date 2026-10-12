# Model and validation defense

| Question | Viva answer |
| --- | --- |
| Why Ridge? | Stable, interpretable regularised linear baseline; scale on training only and tune alpha inside training dates. |
| Why LightGBM? | Tabular nonlinearities and interactions with controlled complexity; it must beat simpler baselines on identical development rows. |
| Why XGBoost? | Independent boosted-tree implementation for a preregistered learner comparison; similarity to LightGBM does not guarantee gain. |
| Why not Random Forest? | It is a reasonable future comparator, but adding learners after observing final outcomes would break selection discipline. |
| Why not LSTM? | Incomplete station sequences require explicit masks and careful state/time boundaries. We have not demonstrated that recurrent complexity improves the declared tabular baselines. |
| Why not GRU? | Fewer recurrent parameters do not establish spatial transfer or extreme-event skill. A future declared comparison should test it on identical data/windows. |
| Why not Transformer? | Attention can model dependencies but needs suitable data, time masks and capacity. It has not been tested here; complexity is not evidence of better forecasting. |
| Why not an LLM? | It is not a substitute for numerical pollutant forecasts and verified time-series evaluation. No LLM generates the AQI value. |
| Why not use CAMS directly? | The current nationwide product already uses it. Correction is a hypothesis, and raw CAMS must be carried forward if learned models fail to improve the locked development criterion. |
| Why residual correction? | It starts from physics forecast structure and learns measured-minus-CAMS differences; it can fail and must compete with raw CAMS and direct prediction. |
| Why persistence/climatology? | They expose whether complex forecasting beats current conditions or seasonal station averages. |
| Why rolling origin? | Training precedes calibration and testing across global dates; random date splits can leak regime and lag information. |
| Why spatial holdout? | It measures transfer to unseen monitors or clusters rather than memorisation at familiar coordinates. |
| Why ablation? | Test which feature families contribute on identical rows; absence of gain is a valid result. |
| Why conformal? | Separate residual/quantile calibration is auditable; exchangeability and subgroup limitations must still be disclosed. |
| Why not maximise R²? | MAE and severe under-warning affect the use case; R² is variance-relative fit and can be negative. |
| Why Severe is hard? | Sparse extremes, distribution shift and an open-ended label prevent exact upper-range regression scoring. |

Primary development and model selection remain pending archive completeness. Preliminary Ridge findings do not justify deploying a residual correction. Model-selection lock must bind features, preprocessing, parameters, data/archive/protocol/source hashes, calibration rules and software versions before final access.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
