# Part 5 — Programme

## S. Implementation roadmap

Estimates assume a team of three working part-time. The order follows the brief: evidence, then data, then models, then the product. Interface work does not start until the numbers it will display exist.

| Phase | Weeks | Work | Exit criterion | Class |
| --- | --- | --- | --- | --- |
| 0 — Evidence | done | Audit, prior-art corpus, five pilot experiments, this blueprint | This document | ER |
| 1 — Corrections | 1 | Fix the seven items in Part 1 A.3 on the live site and in the reports | No statement on the site exceeds its evidence | EP |
| 2 — Data access | 1 | Register keys; confirm the official feed; decide the measured-data source | A real station reading retrieved and stored with full provenance | ER |
| 3 — Ingestion | 1–3 | Connectors, validation, quality flags, storage, scheduler | Seven days unattended, ≥ 95% of runs successful, staleness visible | EP |
| 4 — Backfill | 2–4 | Station history from 2020; archived forecasts from 2024; CAMS from 2022; feature snapshots | A training table in which every feature is provably available at issue time | ER |
| 5 — Benchmark | 4–6 | Reference forecasts, model tiers, ablation | H2 and H4 answered with confidence intervals | ER |
| 6 — Uncertainty and advisory | 6–8 | Predictive distribution, conditional coverage, risk-controlled advisory, unseen-city tests | H1, H3 and H5 answered | ER |
| 7 — Advisory index, window, scenarios | 7–9 | Index sensitivity and anchoring; hourly window; scenario ranges | Sensitivity table published; window beats climatology or is withdrawn | ER / EP |
| 8 — Serving | 8–10 | Batch forecasts, read API, daily verification, drift report | Forecast for every station by issue time; yesterday verified each morning | EP |
| 9 — Interface | 9–12 | New information architecture, design system, accessibility, three languages | First-click test passed; WCAG 2.2 AA audit passed | EP |
| 10 — Track record and paper | 12–14 | Thirty days of live verified forecasts; dedicated novelty search; manuscript | Paper tables regenerate from result files | ER |
| Later | — | Schools and workforce pilots; API; satellite and traffic inputs; health-outcome validation | — | HV / FW |

**One thing is time-sensitive.** The pilot's weakest point is the sample of severe days. Northern India's post-monsoon and winter pollution season begins within weeks. Ingestion started now captures it; ingestion started in January does not. Phases 2 and 3 should begin immediately, ahead of everything else.

## T. Research paper outline

The manuscript is written only after Phases 5–7 produce results. No figure in it is typed by hand.

1. Abstract
2. Introduction — the two-sided error of an air-quality advisory
3. Problem statement — advisories as decisions under uncertainty
4. Related work — operational forecasting in India; health-based indices; impact-based warning; uncertainty and conformal methods; cost-loss decision models
5. Research gap — from the reviewed corpus, with its scope stated
6. Contributions
7. Data sources and provenance
8. Data quality and preprocessing
9. Feature engineering and the prediction-time contract
10. Forecasting architecture and benchmark
11. Vulnerability-aware advisory method — two layers, risk-controlled issuance
12. Uncertainty estimation and conditional coverage
13. Scenario analysis
14. Explanation
15. Experimental design — rolling origin, unseen cities, regime slices
16. Baselines — persistence, climatology, CAMS, one-band shift
17. Results
18. Ablation
19. Cross-city generalisation
20. Error analysis, with the abstention finding
21. Discussion
22. Limitations
23. Ethical considerations — over-warning fatigue, unreviewed health text, who sets the risk level
24. Future work
25. Conclusion

### Which of the brief's candidate contributions survive

| Candidate | Verdict on the evidence | Form it may take |
| --- | --- | --- |
| C1 Real-time multimodal next-day forecasting for India | Not novel: operational systems exist | A measured comparison against CAMS, nothing more |
| C2 Uncertainty-aware prediction | Not novel alone | **Conditional coverage on extreme days** as the evaluated quantity |
| C3 Vulnerability-aware advisory integrated with forecasts | Exists (Forecaster.health, tiered official advice) | Only through risk-controlled issuance |
| C4 Dynamic lower-exposure window | Exists commercially | Product feature |
| C5 Unified forecast → explanation → scenario workflow | Integration | Product contribution |
| C6 Cross-city generalisation and trust monitoring | Protocol exists; pilot effect is small | Reported honestly; the abstention analysis is the interesting part |

**Retained for the paper:** one methodological contribution (risk-controlled cohort advisories, H1) and four experimental ones (conditional coverage on extremes; evidence that uncertainty-based abstention silences severe days; the value of forecast meteorology at true lead time; skill against CAMS and in unseen cities), with an open, reproducible pipeline and a public track record as the artefact.

**Candidate venue types**, to be matched to the strength of the results rather than chosen now: environmental modelling and atmospheric-science journals for the forecasting and evaluation; applied machine-learning and AI-for-social-impact tracks for the decision method; a climate-and-AI workshop as an early, low-risk route for the pilot findings.

## W. Risks and mitigation

| Risk | Likelihood | Effect | Mitigation |
| --- | --- | --- | --- |
| No reliable, permitted source of live station measurements | Medium — the official API could not be verified | Product cannot claim measured live data | Confirm in Phase 2 before anything else; fall back to modelled CAMS, labelled as modelled; never relabel |
| Too few severe days for firm conclusions | High | Weak claims on the cases that matter | Start ingestion before winter; pool stations; report intervals; do not over-read |
| Weather adds less than expected | Medium | H2 negative | Report it; the advisory method does not depend on it |
| Risk-controlled rule does not beat the one-band shift | Medium | H1 negative | Pre-declared; the simpler rule is adopted and the comparison is the result |
| Guarantee fails under drift | Medium | Under-warning exceeds target in some seasons | Rolling calibration; monitor realised rate; show it publicly |
| Advisory index challenged as arbitrary | High | Credibility | Two-layer design; sensitivity analysis; professional review; the word "validated" is never used |
| Over-warning fatigue | Medium | People stop listening | Over-warning is measured and shown beside under-warning |
| Health text causes harm or liability | Low, severe | Serious | Published-source tiers only; reviewed translations; disclaimer; no diagnosis |
| Free-tier and licence limits | Medium | Outage or breach of terms | Terms read before use; attribution automated; commercial tier before revenue |
| Scope exceeds a student team | High | Nothing finished | The roadmap is ordered so that stopping after Phase 6 still yields a complete paper |
| Concept drift | Certain | Accuracy decays | Daily verification, weekly drift report, monthly retrain with a human gate |

## Limitations, stated in advance

- Live coverage will be uneven: stations fail, report late, and vary in quality.
- A station represents its location, not the exposure of everyone in a city.
- Weather forecasts are themselves uncertain, and that uncertainty passes into the air-quality forecast.
- Extreme episodes remain the hardest cases and have the least data.
- The advisory index is evidence-informed and not validated against health outcomes.
- Scenario results are arithmetic on concentrations; they predict no intervention.
- The CAMS grid is about 45 km and cannot see a neighbourhood.
- Satellite columns are not surface concentrations and are missing under cloud.
- Lockdown and festival comparisons are descriptive until weather-normalised.
- The prior-art review covers 47 sources and supports "among the systems reviewed", not "first".

## X. Acceptance criteria

The sixteen questions the brief requires the system to answer, each with the test that decides whether it does. A question the system cannot answer responsibly is shown as future work rather than answered badly.

| Question | Accepted when |
| --- | --- |
| What is the air quality right now? | A measured value with station and source, or an explicit "unavailable" |
| How fresh is that measurement? | Age shown beside every value; stale after three hours |
| What is tomorrow's predicted AQI? | Issued daily for every covered station by the issue time |
| What is the uncertainty? | A range whose realised coverage is within five points of nominal over the last 30 days |
| Which category is most likely? | Band probabilities with calibration error ≤ 0.03 |
| Which pollutant is driving it? | Dominant pollutant computed from the forecast concentrations |
| Why did the model predict this? | Grouped drivers for that forecast, in a sentence generated from them |
| How does advice differ by group? | Advisory per cohort with its risk level; realised under-warning at or below target |
| When might exposure be lower? | A window that beats the climatological one on held-out days, with the absolute level, or "none identified" |
| How does this city compare? | Ranked map layer from the same forecasts |
| What happens under a reduction? | Scenario with a range and the non-causal statement |
| How accurate has it been on unseen future data? | A public rolling track record from stored forecasts |
| Does it generalise? | Unseen-city and excluded-city results published, including the failures |
| Is the model drifting? | Rolling error and coverage against reference, with a stated alert threshold |
| What source produced this? | Source, licence and retrieval time on every value |
| What are the limitations? | The list above, in the product, one click from every page |

## Decisions needed before Phase 2

1. **API keys.** Register on data.gov.in, OpenAQ and NASA FIRMS (each free), and confirm whether the official CPCB feed is actually available. This decides whether the product may say "measured".
2. **Database.** Approve a managed PostgreSQL free tier, and authorise the connector for it.
3. **Corrective deploy.** Approve pushing the seven corrections in Part 1 A.3 to the live site.
4. **Target and date.** Which competition or venue comes first, and when. It sets where the roadmap is cut.
5. **A reviewer.** One clinician or public-health professional willing to read the advisory text, and one fluent reviewer each for Tamil and Hindi.
