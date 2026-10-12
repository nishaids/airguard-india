# Novelty and remaining limits

The contribution is a reproducible combination to evaluate, not proof of a world first.

| Comparator | Capability | Limitation relevant here | AirGuard addition | Evidence | Remaining limitation |
| --- | --- | --- | --- | --- | --- |
| CPCB/current portals | Measured current conditions | Not this prototype’s day-ahead experiment | Explicit forecast/provenance flow | src/nationwide/service.py | Non-official, incomplete monitor coverage |
| OpenAQ | Open station data access | Does not constitute this AQI forecast system | QC/rejection ledger and target reconstruction | measured_dataset.json | Upstream faults and missing ingestion time |
| CAMS | Physics forecast | Coarse grid bias may exist | Test station correction versus raw CAMS | CAMS archive plan; primary factories | Superiority pending |
| Weather apps | Weather and sometimes AQI | Capabilities vary by product | Audit issue-time and Indian AQI conventions | availability.py; aqi.py | No universal app superiority |
| AQI dashboards | Situation display | Presentation alone cannot validate forecasting | Rolling/spatial/severity protocol | locked v3.1; preliminary results | CAMS primary pending |
| Generic ML AQI projects | Learned predictions | Random splits may overstate transfer; not all do | Chronology, final seal and matched rows | splits.py; tests | Does not invent a learner |
| Station-only models | Local measured history | No-monitor transfer can weaken | Nationwide modelled fallback | service.py | Fallback accuracy differs |
| Weather-only models | Meteorological relationship | May lack atmospheric transport/composition baseline | CAMS/direct/residual comparison | primary.py | Comparison unfinished |
| Spatiotemporal systems | Transfer across time/space | Existing sophisticated methods | India-specific reproducible deployment/evaluation | preliminary spatial artifacts | No claim of new spatial theory |
| Uncertainty-aware systems | Intervals/probabilities | Average coverage may hide failures | Severity/region/season interval diagnostics | preliminary uncertainty | No dependent-day guarantee |
| Advisory systems | Exposure communication | Risk thresholds and costs differ | Measured under-/over-warning trade-offs | preliminary advisory | No clinical outcomes |

Literature review access and acceptance remain incomplete: see `docs/research/LITERATURE_FULLTEXT_REVIEW.md`. Do not interpret this feature comparison as a systematic novelty proof.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
