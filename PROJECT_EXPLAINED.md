# AirGuard India — the whole project, explained simply

> Everything here is explained in plain language first, with the real numbers
> underneath. Every number in this file was produced by code in this repository
> and can be regenerated with `python run_all.py`.

---

## 1. What is this project, in one breath?

India already tells you how dirty the air is today. **This project tells you how
dirty it will be tomorrow, and it tells seven different kinds of people seven
different things — because the same air is not equally dangerous to everyone.**

### The simple version

Imagine a school that has one bell for everyone.

When the bell rings, *everybody* goes outside — the football team, the kid with
asthma who carries an inhaler, the pregnant teacher, the 70-year-old gardener.
One bell, one message, for everyone.

That is exactly what India's official Air Quality Index (AQI) does. It looks at
the air over a whole city, turns it into **one number**, and gives that same
number to every single person in that city.

But here is the thing: **the same air is not equally harmful to everyone.**

- A healthy 25-year-old footballer breathes dirty air and feels a bit tired.
- A child breathing the *same* air is harmed more, because a child's lungs are
  still being built and a child breathes more air for each kilogram of body
  weight.
- Someone with asthma may end up in hospital from that same air.

So one bell is not enough. **AirGuard India rings seven different bells.**

And the second problem: the official AQI tells you about air you have *already
breathed*. It is like a weather report that only tells you it rained yesterday.
If you want to decide whether your child plays football tomorrow, yesterday's
report is useless.

**So this project predicts tomorrow.**

---

## 2. The two problems, stated properly

| Problem | What the official AQI does | What AirGuard India does |
| --- | --- | --- |
| **One number for everyone** | Reports the maximum pollutant sub-index, identically to every person in a city | Computes a **Health Advisory Index (HAI)** separately for **7 population groups**, each weighted by how much each pollutant actually harms that group |
| **It looks backwards** | Summarises air already breathed | **Forecasts the next day** from today's measurements and the recent trend |

**And the measured result of doing this:** on **66.92%** of all 17,057 city-days
in the record, **at least one group of people should have been told something
different** from what the official AQI implied.

That is not an opinion. It is a count.

---

## 3. The 8 major novelties

These are the things that make this a research project and not just a dashboard.
Each one comes with the evidence that it actually works — not a claim, a
measurement.

### ★ 1. The Health Advisory Index (HAI) — seven people, seven answers

**Simple version:** instead of one score for the whole city, we build a separate
score for seven kinds of people.

The seven groups:

1. Healthy adults
2. Children (under 14)
3. Elderly (60+)
4. People with asthma or COPD
5. Cardiac (heart) patients
6. Pregnant women
7. Outdoor workers

Each group gets a **vulnerability weight** for each pollutant, based on published
medical research. For example, children get a **1.55×** weight on nitrogen
dioxide and **1.45×** on ozone, because their airways are still developing and
they breathe more air per kilogram of body weight than adults do.

**The evidence it matters:**

| Group | Average HAI | Average AQI ÷ 5 | How much higher | Gets a *different* advisory than the AQI |
| --- | --- | --- | --- | --- |
| Healthy adult | 31.19 | 29.83 | +1.35 | **25.95%** of days |
| Children (under 14) | 39.75 | 29.83 | +9.92 | **47.05%** of days |
| Elderly (60+) | 43.18 | 29.83 | +13.35 | **54.47%** of days |
| Asthma / COPD | 41.12 | 29.83 | +11.29 | **50.50%** of days |
| **Cardiac patients** | 44.88 | 29.83 | +15.05 | **58.11%** of days |
| Pregnant women | 41.99 | 29.83 | +12.16 | **51.43%** of days |
| Outdoor workers | 42.41 | 29.83 | +12.58 | **54.46%** of days |

Read the cardiac row again: **on more than half of all days, a heart patient
should have been given a different instruction than the one the official index
gave them.**

### ★ 2. The never-less-protective guarantee — a promise proved by code

**Simple version:** we made a promise, and the computer checks the promise every
single time the project runs.

The promise: **the HAI will never tell you the air is safer than the official
AQI says.** It can say "more careful", never "less careful". If it ever broke
that promise, the whole pipeline would stop with an error.

This matters because a health tool that is *sometimes* less cautious than the
official advice is dangerous. So it is not allowed to be, ever — and that is
enforced by an assertion in the code, not by hoping.

Three more properties are proved the same way: the index stays inside its
bounds, it only goes up when a pollutant goes up (monotonicity), and the ordering
between groups is preserved.

### ★ 3. Forecasting tomorrow, and proving the model actually helps

**Simple version:** predicting tomorrow's air is easy to *fake*. We made sure we
didn't fake it.

Here is the trap. Air quality barely changes overnight. So if you just say
**"tomorrow will be exactly like today"** — a rule so dumb it needs no machine
learning at all — you already get **R² = 0.841**, which looks like a great score.

A dishonest project would report "R² = 0.91!" and let you be impressed.

This project reports the honest number instead:

| | Mean Absolute Error (AQI points) |
| --- | --- |
| "Tomorrow = today" (the dumb rule) | 18.90 |
| **Our LightGBM model** | **15.10** |
| **The actual improvement** | **20.11% better** |

That **20.11%** is the real contribution of the machine learning. Everything
above that is free and would have been free without any model.

### ★ 4. Data leakage demonstrated by experiment, not merely avoided

**Simple version:** we ran an experiment to *show* how easy it is to cheat, so
that nobody can accuse us of cheating.

"Leakage" is when a model secretly gets to peek at the answer. In air quality,
there is a very tempting form of it: the AQI *band* (Good / Poor / Severe) is
calculated directly from the AQI *number* using a fixed table. So if you ask a
model "what band is today?" and also hand it today's AQI number, it will score
**100% perfect** — while having learned absolutely nothing. It just read the
answer key.

So we fitted three models on identical data splits and published all three:

| What the model was asked | Macro-F1 score | What it means |
| --- | --- | --- |
| Today's band, given today's AQI | **1.0000** | Cheating. Reading the answer. |
| Today's band, with AQI removed | 0.7077 | The honest same-day version |
| **Tomorrow's band (what we actually do)** | **0.7411** | A real forecast |

That perfect 1.0 is displayed proudly *as a warning*. It is what our numbers
would look like if we were cheating — and they don't look like that.

### ★ 5. Imputation chosen by measurement — including rejecting the winner

**Simple version:** some measurements are missing. We tested five ways to fill
the gaps, and then deliberately *did not* use the one that scored best.

We hid 15% of the real values on purpose, filled them back in five different
ways, and measured which method reconstructed the truth most accurately.

The winner was **linear interpolation** — but linear interpolation fills today's
gap by looking at *tomorrow's* value. In a forecasting system that is time
travel, and time travel is cheating.

So we rejected the winner and used **forward-fill (limit 3 days)**, which only
ever looks backwards. And then we **reported how much accuracy that cost us**,
as a number, instead of hiding the trade-off.

### ★ 6. Event-aware cleaning — Diwali is signal, not noise

**Simple version:** the dirtiest days of the year are real, not mistakes. We made
sure the computer doesn't delete them.

Most data-cleaning code automatically deletes "outliers" — values that look
extreme. But in Indian air quality, the extreme days are the *most important*
days:

- **Diwali** — firecracker smoke sends pollution through the roof
- **Crop-residue burning season** (October–November in the north)
- **The 2020 COVID lockdown** — when the air suddenly got dramatically cleaner

An automatic outlier filter would erase all three. Ours explicitly **exempts**
these known event windows, so genuine pollution episodes are never thrown away
as "errors".

The proof it's worth keeping: Diwali produces a measurable national spike, and
the lockdown produced a measured **−33.99%** drop in national mean AQI.

### ★ 7. The safe-exposure window — and catching a subtle data trap

**Simple version:** we tell you the cleanest hours of the day to go outside — and
we had to find the right data to do it, because the obvious data was a trap.

The dataset has hourly AQI values. The obvious thing is to look for the cleanest
hour. But there is a hidden problem: **the supplied hourly "AQI" is a 24-hour
rolling average.** It is smeared across an entire day by its own definition, so
it *cannot* show a daily rhythm. Using it would have shown a pathetic **8%**
swing between the best and worst hour and we'd have concluded, wrongly, that the
time of day barely matters.

So we rebuilt the calculation from **instantaneous hourly concentrations**
instead. The real swing: **39.6%.**

The difference between 8% and 39.6% is the difference between "don't bother" and
"a genuinely useful piece of health advice". Both numbers are reported, along
with the explanation of why they differ.

### ★ 8. The counterfactual policy simulator — checked against reality

**Simple version:** you move a slider that says "cut PM2.5 by 20%", and the
project recalculates the *entire* five-year history from scratch, to show how
many days would have been safer.

It doesn't just rescale a number. It recomputes every pollutant sub-index, every
AQI, every band, and all seven cohort HAI values, for all 18,395 city-days.

Headline scenario — **PM2.5 and PM10 both cut by 20%**:

- Mean AQI: **144.1 → 120.3** (−16.5%)
- **29.8%** fewer unsafe city-days
- **12,432 cohort advisory-days averted**

**And here is the part that makes it science rather than a toy:** we checked the
simulator against something that *actually happened*.

The 2020 national lockdown was a real, sudden, economy-wide emission cut. It
produced a **measured −33.99%** change in national mean AQI. The simulator's
nearest comparable scenario (all pollutants cut 40%) predicts **−37.0%**.

Those two numbers agree closely — **and the simulator was never fitted to the
lockdown in any way.** It had no idea the lockdown existed. That is an
independent validation.

### Two more, for completeness

The project actually ships **ten** novelties. The two not counted above:

- ★ **City pollution archetypes** — unsupervised clustering on the *shape* of
  each city's pollutant mix (not how dirty it is), producing two archetypes that
  map to genuinely different policy levers. Validated by reproducing the exact
  same grouping with a second, completely different algorithm (**ARI = 1.000**).
- ★ **Explainability and Responsible AI** — TreeSHAP explanations, plus a data
  card and model card that state every limitation plainly.

> **A finding worth mentioning:** when we asked SHAP which feature the models
> rely on most, the answer for **both** the regression and the classification
> model was `HAI_healthy_adult` — **the index this project invented**. It beats
> raw PM2.5 and even the official AQI itself. We were not aiming for that; it
> fell out of the analysis, which makes it better evidence.

---

## 4. The dataset — what, from where, and why

### What it is

| Field | Value |
| --- | --- |
| **Name** | Air Quality Data in India (2015–2020) |
| **Original source** | **Central Pollution Control Board (CPCB)** — Ministry of Environment, Forest and Climate Change, **Government of India** |
| **Where we downloaded it** | Kaggle, uploaded by Vopani (`rohanrao`) |
| **Licence** | **CC0: Public Domain** — verified live at download time |
| **Raw size** | 29,531 rows, 26 cities, 2015-01-01 → 2020-07-01 |
| **After cleaning** | **18,395 rows across 12 cities** |
| **One row means** | One city, one day: the average pollution across that city's monitoring stations |

### Why this dataset

1. **It is official government data.** CPCB is the body that legally operates
   India's air quality monitoring network. This is not a hobbyist's scrape.
2. **The licence is genuinely open.** CC0 means public domain — usable without
   restriction. We didn't take that on trust: the licence string was read
   directly from the live page at download time and stored, along with a
   **SHA-256 checksum of every file**, in `data/raw/PROVENANCE.json`. Anyone can
   verify they have byte-identical data.
3. **It is long enough to learn from.** Five and a half years covers five
   winters, five Diwalis, five monsoons — enough for a model to learn seasonal
   behaviour rather than memorise one year.
4. **It contains a natural experiment.** The 2020 lockdown gives us a real,
   independent event to validate the policy simulator against. That is rare and
   valuable.
5. **It has both daily and hourly files**, which is what makes the safe-exposure
   window feature possible at all.

### Why only 12 of the 26 cities

We set **two rules before looking at any results** (this matters — deciding
afterwards would be cherry-picking):

1. At least **80%** of the days in a city's own span must have a real AQI value.
2. The city must have at least **730** labelled days (two years).

14 cities failed. **Every single exclusion is listed with its reason** in the
data card — nothing was dropped quietly. Examples:

- **Mumbai** — excluded, only 38.6% complete
- **Patna** — excluded, 78.5% complete (just under the line, still excluded)
- **Aizawl** — excluded, only 111 labelled days

The 12 that survived: Amaravati, Amritsar, Bengaluru, Chennai, Delhi, Gurugram,
Hyderabad, Jaipur, Kolkata, Lucknow, Thiruvananthapuram, Visakhapatnam.

### What the data does NOT contain (stated honestly)

- **No weather.** No wind, rain, temperature or humidity — and wind is what
  actually blows pollution away. This is the single biggest limitation and it
  caps how accurate any model on this data can possibly be.
- **No health outcomes.** No hospital admissions, so the HAI cannot be validated
  against the illnesses it aims to predict.
- **Urban only**, and the record **ends 1 July 2020** — so it does not describe
  today's air.

---

## 5. The tech stack

### The brain (data science, Python 3.10)

| Tool | Job |
| --- | --- |
| **pandas / numpy** | Handling the tables and the maths |
| **scikit-learn** | Linear/Ridge regression, Random Forest, SVM, KNN, K-Means, metrics |
| **LightGBM** | The winning regression model, and the classifier this site serves |
| **XGBoost** | The best-scoring classifier |
| **imbalanced-learn (SMOTE)** | Creating synthetic examples of rare classes, so "Severe" days aren't ignored |
| **SHAP** | Explaining *why* the model predicted what it predicted |
| **matplotlib / seaborn** | The 41 figures, all at 300 DPI, all colour-blind-safe |
| **python-docx** | Auto-generating the three review documents |

### The website you are looking at

| Tool | Job |
| --- | --- |
| **Next.js 16 + React 19** | The website itself, 5 pages |
| **Recharts** | The interactive charts |
| **Python serverless functions** | The two live prediction endpoints |
| **Vercel** | Hosting |

### Why two different models for classification

The site serves **LightGBM + SMOTE** even though **XGBoost + SMOTE** scored
better. Here is the honest reason:

Vercel gives each serverless function a hard **250 MB** limit. We measured the
real Linux package sizes rather than guessing:

| Package | Installed size |
| --- | --- |
| xgboost | **145 MB** |
| scipy | 105 MB |
| pandas | 64 MB |
| scikit-learn | 45 MB |
| numpy | 40 MB |

XGBoost alone eats more than half the budget. Together they came to **320 MB** —
over the limit before we'd added a single line of our own code.

**What we did about it:** we exported the trained model's decision trees to plain
JSON and wrote our own ~80-line tree evaluator that needs no machine-learning
library at all. Then we verified it reproduces the original model **exactly** —
**0.0 difference** across all 4,397 test rows for regression, **0 label
mismatches** for classification.

The final bundles: **199 MB** and **168 MB**. Both fit, with room to spare.

The cost of switching classifier is stated openly on the site: macro-F1
**0.7145** (deployed) vs **0.7411** (reported best) — a gap of **−0.0266**.

---

## 6. How the backend works

### The simple version

Think of it as a **kitchen** and a **waiter**.

The **kitchen** (the Python pipeline) does all the heavy cooking *in advance* —
hours of it. It cleans the data, trains the models, draws the charts, writes the
reports. This happens on a laptop, once.

The **waiter** (the website) mostly just carries out food that is already cooked.
Almost everything you see on the site was cooked in advance and is just being
served from a file.

Only **two** things are cooked fresh to order, because they depend on what *you*
click:

1. **Your forecast** — because you choose the city, the date and which group of
   people you are
2. **Your policy scenario** — because you choose the sliders

### The pipeline: 20 stages, one command

```bash
python run_all.py
```

That runs, in dependency order:

```
acquire → quality → clean → features → safe_windows → eda
  → regression → classification → clustering → tuning → evaluation
  → explain → policy → cards → diagrams → notebooks → reports
  → readme → smoke → audit
```

- **acquire** — download the data, record SHA-256 checksums and the licence
- **clean** — fix missing values, remove sensor errors, protect event days
- **features** — build 100+ predictive columns (yesterday's AQI, 7-day averages,
  pollutant ratios, all seven HAI values)
- **regression / classification / clustering** — train and compare every model
- **tuning** — 322 model fits searching for better settings (~39 minutes)
- **explain** — compute SHAP values
- **smoke** — 14 tests, including 336 city/cohort/date combinations to prove the
  app never crashes
- **audit** — check 13 "definition of done" criteria

### How a forecast request actually travels

```
You pick "Delhi, 5 Nov 2019, Children"
        │
        ▼
Browser sends POST /api/forecast
        │
        ▼
Vercel wakes a Python function (webapp/api/forecast.py)
        │
        ├─ looks up that city-day's 100 engineered features
        ├─ applies your what-if slider reductions, if any,
        │  and recomputes every affected value from scratch
        ├─ runs the exported regression trees  → predicted AQI
        ├─ runs the exported classification trees → band + confidence
        ├─ computes HAI for all 7 cohorts
        ├─ looks up the cleanest outdoor window
        ├─ checks whether your input looks unlike the training data (drift)
        └─ writes the plain-English advisory
        │
        ▼
JSON comes back; React draws the charts
```

**The important design choice:** the serverless function does *not* load a
`.joblib` model file, because that would require importing LightGBM, which
requires scipy, which blows the size limit. It reads the trees from JSON and
walks them with plain arithmetic instead.

### The one guard-rail worth knowing

The what-if sliders do **not** rewrite history. If you reduce today's PM2.5 by
20%, the code recomputes today's sub-indices, today's AQI and today's seven HAI
values — but it leaves yesterday's numbers and the 7-day rolling averages alone.

Why: a what-if about *today* should not retroactively change what happened last
Tuesday. Pretending otherwise would make the counterfactual dishonest.

---

## 7. What the website actually does, page by page

### Overview
Live headline numbers, the dataset provenance and licence, the two city
archetypes, and which models are running.

### Forecast — the main tool
Pick a **city**, a **date**, and **which group of people you are**. You get:

- Tomorrow's **predicted AQI number**
- Tomorrow's **predicted band** with the model's **confidence**, plus the full
  probability spread across all six bands
- Your group's **Health Advisory Index** and risk band
- The **dominant pollutant** that day
- The **cleanest hours** to go outside
- A plain-English **advisory** written for your group
- A **30-day history chart** with the forecast marked, and — for historical
  dates — what actually happened, so you can see the model's error yourself
- **All seven cohorts side by side**, so you can see how much the advice differs
- A **drift check** that warns you if the day is unlike anything the model was
  trained on
- **What-if sliders** to cut pollutants and watch everything recalculate

### City Risk Atlas
Five tabs: the two discovered **archetypes**, a **ranked risk table** of all 12
cities, a **month-by-city heatmap**, the **Diwali** analysis, and the **2020
lockdown** analysis.

### Policy Simulator
Move sliders (or pick a preset), and the entire five-year record is re-scored.
Shows AQI change, unsafe days removed, band migration, per-city effect, and
cohort advisory-days averted — plus the lockdown sanity check.

### Model Insights
Seven tabs of full evidence: every model compared, confusion matrices, ROC
curves, residual diagnostics, SHAP explanations, the tuning report, the leakage
demonstration, a plain-language metric glossary, and the data and model cards.

---

## 8. The final scoreboard

| Task | Model | Score | Beat the dumb baseline by |
| --- | --- | --- | --- |
| **Predict tomorrow's AQI number** | LightGBM | MAE **15.10** | **+20.11%** |
| **Predict tomorrow's band** | XGBoost + SMOTE | Macro-F1 **0.7411** | **+8.94%** |
| **Group cities by pollution type** | K-Means (k=2) | Silhouette **0.3553** | ARI **1.000** vs a second algorithm |

**The safety number that matters most:** of 4,397 predictions, only **5
(0.114%)** understated the danger by two bands or more. That is the failure that
could actually hurt somebody — being told the air is cleaner than it is — so it
is reported as a headline number instead of being buried in an average.

**Also:** 41 figures at 300 DPI · 14 smoke tests over 336 combinations, zero
crashes · 12 of 13 definition-of-done checks passing · every number in every
report read from JSON at generation time, never typed in by hand.

---

## 9. The honest limitations

A good project states what it cannot do:

1. **No weather data** — and wind is the single biggest driver of whether
   pollution disperses. This caps achievable accuracy.
2. **No health outcomes** — the HAI is grounded in published exposure-response
   literature, but it has not been validated against actual hospital admissions,
   because this dataset has none.
3. **The record ends 1 July 2020** — nothing here describes today's air, and the
   final months are atypical because of the lockdown.
4. **12 cities, urban only** — no rural monitoring, though much of India's
   biomass-burning exposure is rural.
5. **One value per city per day** — cannot tell a roadside from a park.
6. **This is not medical advice.** It is general public-health guidance. The
   official CPCB index remains the authoritative index for India.
