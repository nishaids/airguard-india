# Public-impact evaluation plan

**Status: PLAN ONLY — NOT AUTHORISED TO RUN.** No participant has been approached and no response exists. Nothing here may be reported as a finding. Running it needs institutional ethics approval (Rajalakshmi Engineering College's ethics committee or equivalent) and written informed consent, as set out in [`docs/USER_STUDY.md`](../USER_STUDY.md), which remains the consent, privacy and data-handling protocol. This plan updates the *tasks and measures* to the product as deployed on 20 October 2026.

## What it can and cannot show

It can show whether people **understand** what the site tells them: which number is tomorrow's, whether it is measured or modelled, how far to trust it, whether air is getting worse, and what a cautious person might do. It cannot show that AirGuard improves health, changes behaviour over time, or reduces exposure. No such claim is made.

## Design

Moderated, task-based usability session, about 20 minutes, on the participant's own phone or a lab laptop at 375 px and 1280 px. Within-subject comparison of two scenarios, order randomised:

- **Scenario A** — a city with a recent nearby station (measured current value) and a clear category change tomorrow.
- **Scenario B** — a place with no nearby station (modelled only), a stale input and no published track record.

Scenarios are fixed screenshots plus a live walk-through, so every participant sees the same data. Target n = 30 adults, recruited without reference to health status. This is enough to describe comprehension rates with an interval, not to compare against another product.

## Tasks and measures

| # | Task | Measure | Scored against |
| --- | --- | --- | --- |
| 1 | "What will the air quality be tomorrow here?" | time to a correct answer; correct / incorrect | the tomorrow card's value and category |
| 2 | "Is today's value measured at a station or estimated by a model?" | correct interpretation of the MEASURED / MODELLED label | label shown |
| 3 | "How sure is this forecast?" | states that no interval or track record is available yet (Scenario B), or describes the shown evidence | interface text |
| 4 | "Will tomorrow be better or worse than today?" | correct direction | today vs tomorrow values |
| 5 | "Which pollutant drives it?" | correct dominant pollutant | dominant pollutant field |
| 6 | "When was this updated?" | finds the timestamp; notices STALE when shown | freshness label |
| 7 | "Someone with asthma is planning tomorrow. What does the page suggest?" | paraphrase matches the general guidance; does not read it as personal medical advice | guidance text and disclaimer |
| 8 | "Search for your own city and find tomorrow's category." | task completion, time, errors | — |

After the tasks: System Usability Scale (10 items), a 5-point perceived-clarity item per card, and two misreading probes (what "no error figure yet" means; what "modelled" means). Accessibility observations: keyboard-only completion of task 8, and zoom to 200%.

**Pre-registered success thresholds** (set before any data): tasks 1, 2 and 4 correct for at least 80% of participants; task 7 read as medical advice by no more than 10%. Missing a threshold is reported as a finding about the interface, not hidden.

## What will not be collected

No names, contact details, health conditions, precise location or analytics. Responses carry a random ID. Cohort in task 7 is a scenario to read for, not a question about the participant. Details: `docs/USER_STUDY.md`.

## What was implemented now

Nothing that collects data. The interface changes that this plan tests and that shipped on 20 October 2026 are the sample-size rule for the track record and the shorter caching of stale summaries (`docs/DEPLOYMENT_COMPLETION.md`). An anonymous on-page clarity feedback widget was considered and **not** built: it would collect data before ethics approval and add a privacy surface for little evidence.

## Before it can run

1. Ethics approval and the consent form (owner: the author).
2. Freeze the two scenarios and the scoring key in the repository before recruitment.
3. Tamil and Hindi versions only after the named-reviewer translation review in `docs/I18N_REVIEW.md`.
4. Results, when they exist, go to `results/user_study.json` from the analysis script only.
