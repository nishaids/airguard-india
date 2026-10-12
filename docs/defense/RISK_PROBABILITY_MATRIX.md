# Risk and qualitative probability matrix

Likelihood levels: Rare, Unlikely, Possible, Likely, Very Likely. Impact: Low, Moderate, High, Critical. No percentage is supported without a monitored denominator and time horizon.

| Risk | Likelihood | Impact | Rating | Mitigation | Residual risk |
| --- | --- | --- | --- | --- | --- |
| Data outage | Likely | High | HIGH | Caches, budgets, status and bounded retries | Concurrent provider/network failure |
| Station malfunction | Possible | High | HIGH | Locked QC, rejection ledger and provenance | Unflagged instrument drift |
| CAMS latency | Likely | High | HIGH | Resume job IDs; freeze run policy | ADS delay and historical release uncertainty |
| Distribution shift | Likely | High | HIGH | Temporal/season/region monitoring | New regimes may invalidate calibration |
| Extreme underprediction | Likely | Critical | CRITICAL | Report Severe misses and threshold diagnostics | Already observed in strict preliminary baselines |
| Over-warning | Possible | High | HIGH | Joint under-/over-warning evaluation | Alert fatigue and lost work/activity |
| Missing city coverage | Very Likely | High | CRITICAL | Label raw-grid fallback | Unknown local station error |
| Provider dependency | Likely | High | HIGH | Replaceable adapters and explicit outages | No data if essential sources fail |
| Model drift | Likely | High | HIGH | Frozen prospective verification before releases | Sparse delayed measured outcomes |
| Security incident | Possible | Critical | HIGH | Server secrets, RLS, quotas and safe errors | Penetration testing/retention review incomplete |
| API/compute cost | Possible | High | HIGH | Grid caching and commercial terms review | No measured national capacity budget |
| Network failure | Possible | High | HIGH | Timeout/error state and manual retry | Offline forecast cannot be invented |
| Database outage | Possible | Critical | HIGH | Bounded queries and incident recovery | Core ledger/cache unavailable |
| Uncertainty miscalibration | Likely | High | HIGH | Conditional diagnostics and time-separated calibration | Dependence and extreme-event failures |
| False confidence | Likely | Critical | CRITICAL | Source/status/limitations prominent | Users may still misread AQI as safety |


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
