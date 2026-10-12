# One sentence, thirty seconds, one minute and three minutes

**One sentence:** AirGuard is a source-labelled Indian air-quality planning prototype with a CPCB-style forecast engine and an auditable research workflow.

**Thirty seconds:** We combine measured station context with a modelled next-day forecast, show whether data are missing or stale, and provide environmental exposure guidance. Our own work is the QC, index, integration, interfaces and evaluation infrastructure. A station correction must still beat raw CAMS under the locked experiment; no clinical or street-level accuracy claim is made.

**One minute:** Select a place or coordinates. AirGuard validates the request, reuses bounded caches and calls configured sources. Measurements and forecasts remain labelled separately; the central engine constructs an AirGuard CPCB-style index and explicit insufficient-data states. The research dataset retains QC exclusions and censored Severe labels. Preliminary non-CAMS development results are real, but they are not proof of CAMS correction. Genuine archived forecasts are being acquired before direct and residual comparison. We disclose extreme under-warning, privacy/cost limits and provider dependence.

**Three-minute technical explanation:** AirGuard India addresses a planning question: what information can help someone prepare for tomorrow’s air-quality conditions? Current AQI alone describes a different time. Forecasts are useful only if we explain their source, their spatial scale and what happens when measurements or providers fail. Existing AQI services remain valuable; we are testing an auditable integration rather than claiming to have invented atmospheric forecasting.

The user selects a place or coordinates. The backend validates the input, applies shared request budgets and caches, and retrieves measured station context and modelled forecasts. A central CPCB-style engine constructs the index. The frontend labels measured and modelled information, shows timestamps and missing data, and gives environmental exposure guidance. A coarse CAMS cell does not establish street-level precision. If no valid forecast exists, the system withholds the value instead of inventing clean air.

Our research targets are real OpenAQ-hosted CPCB-provider station measurements. The retained table has 107,280 station-days, including 64,799 valid and 42,481 rejected targets. Raw files and rejection reasons remain available. The locked QC rules reject outage zeros, stuck sequences and unsupported units while retaining flagged spikes and PM2.5-above-PM10 inconsistencies. Severe indices are lower bounds of at least 401, so we exclude them from exact regression fitting/error and evaluate category misses, exceedances and lower-bound shortfall.

The scientific question is whether Indian station correction adds value over raw CAMS. We compare direct and residual Ridge, LightGBM and XGBoost with persistence and climatology. All methods must use the same eligible observations and date windows. Training-only tuning, chronological calibration and spatial holdouts test temporal and geographic transfer. Intervals and advisory policies are evaluated for both under-warning and over-warning, not described as clinical risk guarantees.

The completed preliminary study is explicitly non-CAMS: strict Ridge improved MAE over climatology by 8.96 index units, but history Ridge did not establish improvement over persistence. All strict baseline forecasts on 363 evaluated censored Severe days under-warned. Those failures matter more than a flattering average alone. Genuine archived CAMS files have now passed the probe and initial cube checks; the complete primary comparison remains pending acquisition. Selection must be locked and committed before the final test. Real prospective verification and user studies are still needed before stronger accuracy, health-benefit or commercial-readiness claims.

**Novelty:** An auditable combination of Indian index, station QC, forecast provenance and validation.

**People impact:** Better information may support feasible exposure-aware preparation; benefit is not measured.

**Limitation:** Primary CAMS superiority and extreme-event reliability remain unestablished.

**Future work:** Finish the locked experiment and prospective/user evaluations before a separately approved release.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
