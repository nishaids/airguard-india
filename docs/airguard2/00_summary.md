# Summary

## What this document is

The brief asked for the existing AirGuard India system to be audited, compared with what the rest of the world has built, and redesigned into a research-grade platform, in that order, and without claiming novelty that the evidence does not support.

This document is the result of the first three steps of that order — **audit, prior art, research gap** — together with the full design for everything that follows. No part of AirGuard 2.0 has been built. The deployed application is unchanged.

Three kinds of statement appear here and are kept apart: what was **measured** (on the repository, the live site, or in a pilot experiment), what was **read from a cited source**, and what is **proposed**.

## What was done

- The repository and the live deployment were audited, including latency, error handling and the correctness of what the site tells users.
- **Forty-seven external systems were reviewed**: government forecasting systems, commercial products, health-impact tools, methods papers, Indian forecasting papers and open student projects. Each is recorded with its source in `prior_art_corpus.csv`.
- **Every proposed live data source was tested with a real request.** Three work today without a key; one official source could not be reached.
- **Five pilot experiments** were run on the existing 2015–2020 record to check whether each gap named in the brief is real.

## Six findings that change the plan

1. **None of AirGuard's features is new on its own.** Next-day forecasting, cohort-specific advice, explanation, exposure windows and percentage-reduction scenarios all exist in operational systems. India already has 400-metre physical-model forecasting for Delhi and district-level forecasts nationwide.
2. **The closest prior art is stronger than AirGuard's advisory index.** Forecaster.health issues forecast-driven mortality-risk alerts by age and sex across 31 European countries from epidemiological models. AirGuard's cohort weights are hand-set.
3. **The live site's "confidence" is wrong.** 41% of forecasts are shown as at least 95% confident; 89% of those are correct. The model that was swapped in to fit the hosting limit is the cause.
4. **Prediction intervals work on average and fail when the air is worst.** At 90% nominal coverage, three standard methods cover 57–75% of *Severe* days.
5. **Letting the model abstain when uncertain is unsafe.** It declines four in five *Severe* days, because uncertainty and pollution rise together. This idea from the brief is rejected on the evidence.
6. **Cross-city generalisation is a smaller problem than assumed.** Removing a city from training costs 3.5% in error on average.

## The gap that survives

Of the 47 systems reviewed, eight combine a forecast with cohort advice and three combine a forecast with uncertainty. **None combines all three, and none attaches a stated error rate to the advice it gives.**

The pilot shows why that matters. An advisory issued from the point forecast fails to warn on 18% of polluted days. Issued from the 75th percentile it misses 9%, and over-warns on 24% of days instead of 14%. Where to sit on that curve is a decision about whose errors cost more, and it differs for a healthy adult and a cardiac patient.

**The proposed research contribution** is to make that decision explicit and controlled: each cohort's advisory is issued at a risk level calibrated to hold under-warning below a declared target on future data. Whether that is new to the literature is not yet established and is not claimed.

## What happens next

Five decisions are needed before work continues (Part 5): API keys, a database, approval to correct the live site, a target date, and a reviewer for the health text. One of them is urgent: the high-pollution season begins within weeks, and data collection that starts after it has passed will not contain the severe days the study depends on.

## Where each requested deliverable is

| Deliverable | Location |
| --- | --- |
| A — Existing project audit | Part 1, A |
| B — Global prior-art analysis | Part 1, B; `prior_art_corpus.csv` |
| C — Competitive matrix | Part 1, B.2 and C |
| D — Research-gap matrix | Part 1, D |
| E — Research hypothesis | Part 1, E |
| F — Novelty statement | Part 1, F |
| G — Architecture | Part 3, G |
| H — Dataset strategy | Part 2, H |
| I — Preprocessing pipeline | Part 2, I |
| J — Model benchmark plan | Part 2, J |
| K — Evaluation plan | Part 2, K |
| L — Advisory index methodology | Part 2, L |
| M — Interface redesign specification | Part 4, M |
| N — Page wireframes | Part 4, N |
| O — Design system | Part 4, O |
| P — Backend and API | Part 3, P |
| Q — Database schema | Part 3, Q |
| R — MLOps | Part 3, R |
| S — Implementation roadmap | Part 5, S |
| T — Research-paper outline | Part 5, T |
| U — Startup and SaaS roadmap | Part 4, U |
| V — Competition demonstration | Part 4, V |
| W — Risks and mitigation | Part 5, W |
| X — Acceptance criteria | Part 5, X |
