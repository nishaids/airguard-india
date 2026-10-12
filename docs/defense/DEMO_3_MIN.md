# Three-minute live demo

Budget roughly 30 seconds per step. Rehearse source availability first; never promise a particular AQI value. The commands are in README.md. Do not show credentials, terminal environment dumps or the ADS setup file.

| What to click | What appears | What to say | Technical concept | Likely question | Answer |
| --- | --- | --- | --- | --- | --- |
| Open /live | Selected Indian place; current/tomorrow cards | We distinguish measured observations from modelled forecasts. | Provenance | Is this official? | No; AirGuard CPCB-style forecast. |
| Search Avadi or known cached city | Validated location results and loading | A national grid fallback does not require a local training-city list. | Location/provider orchestration | Can you predict a street? | Only grid-scale relevance is supported. |
| Inspect current source/freshness | Measured or modelled label and time | No station observation is manufactured when a monitor is absent. | Fallback/QC | What if station offline? | Labelled modelled fallback or unavailable state. |
| Open Forecast & advisory; choose cohort | Tomorrow category and environmental guidance | This is exposure guidance, not personal health risk. | Advisory | Is it medically validated? | No clinical outcome validation. |
| Open How was this calculated? | Sources, aggregation and forecast record | The shared engine and immutable record make the calculation auditable. | Method/prospective identity | What did you build? | Integration, QC, index logic, APIs/UI and research infrastructure. |
| Show ONE_PAGE_RESULTS.md | Verified development facts and failures | Strict Ridge beat climatology preliminarily; it did not establish improvement over persistence or CAMS. | Honest evaluation | What negative result? | All strict Severe validation forecasts under-warned. |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
