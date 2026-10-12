# Eight-minute technical demo

Budget 35–45 seconds per step, shortening navigation as needed. Use an already checked location.

| What to click | What appears | What to say | Technical concept | Likely question | Answer |
| --- | --- | --- | --- | --- | --- |
| Open /live | Selected Indian place; current/tomorrow cards | We distinguish measured observations from modelled forecasts. | Provenance | Is this official? | No; AirGuard CPCB-style forecast. |
| Search Avadi or known cached city | Validated location results and loading | A national grid fallback does not require a local training-city list. | Location/provider orchestration | Can you predict a street? | Only grid-scale relevance is supported. |
| Inspect current source/freshness | Measured or modelled label and time | No station observation is manufactured when a monitor is absent. | Fallback/QC | What if station offline? | Labelled modelled fallback or unavailable state. |
| Open Forecast & advisory; choose cohort | Tomorrow category and environmental guidance | This is exposure guidance, not personal health risk. | Advisory | Is it medically validated? | No clinical outcome validation. |
| Open hourly text table/chart | Forecast hours, gaps and categories | These concentrations are modelled; the relative exposure window is not a safety label. | Forecast temporal support | Can missing hours be zero? | No. Gaps stay missing. |
| Open measured pollutant context | Station identity/distance/last observation | Measured coverage and individual pollutant age matter. | Station support | Are all sensors current? | Dedicated metadata selection checks dates; old sensor order is not evidence. |
| Open Policy scenarios; choose a small reduction | Original saved forecast baseline and recalculated scenario | This is arithmetic under assumed concentration changes, not policy causality. | Shared engine/immutability | Will this intervention reduce AQI? | The simulator cannot predict actual intervention effects. |
| Open /city-atlas; table/map | Modelled cells distinguished from monitors | Availability across India does not establish calibrated precision everywhere. | Spatial fallback | What about unseen city? | Raw-grid estimate with explicit support limits. |
| Open /research then track record | Readiness and eligible verification count | A 30-day track record requires real elapsed days and paired outcomes. | Prospective audit | Can historical scores stand in? | No; these evidence streams are separate. |
| Open FAILURE_MATRIX.md | Thirty-five fault scenarios | Failure handling includes honest withholding, not fabricated continuity. | Reliability | What if all sources fail? | Unavailable message and backup demonstration. |
| Open CLAIM_EVIDENCE_MATRIX.md | Allowed versus pending claims | The CAMS correction/final results stay pending until their actual experiment. | Scientific integrity | Are you cherry-picking? | All declared folds and negative artifacts remain auditable. |
| Finish with limitations and next gate | MODEL_SELECTION_LOCK pending | Archive, development selection and final evaluation occur in that order. | Reproducibility | Can you change after final? | No retuning or threshold changes in that evaluation. |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
