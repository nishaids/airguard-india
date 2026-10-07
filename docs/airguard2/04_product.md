# Part 4 — Product and interface

Everything in this part is **Proposed**. Per the implementation order, none of it is built before the data and model work in Parts 2 and 3; an interface designed first would be designed around numbers that do not exist yet.

## M. Interface redesign specification

### M.1 Honest assessment of the current interface

The 1.0 interface was restyled for visual impact: a dark background with coloured radial gradients, translucent blurred panels, gradient-filled headline text, a large hero block, and symbol characters used as icons. That is the aesthetic the brief now rules out, and the brief is right to. It signals "demo", it spends contrast on decoration, and it gives the same visual weight to a headline metric and a caveat. It is replaced, not refined.

Two things from 1.0 are kept: tabular numerals for every figure, and the colour-blind-safe palette for data.

### M.2 Design personality

An instrument, not a poster. The reference points are a good weather product (now, then next, then detail), a financial terminal (density without clutter, numbers aligned to be compared), a public-health dashboard (plain words, caveats beside the figure), and a government monitoring portal (provenance always visible). These are patterns to learn from; no layout, branding, illustration or code is copied from any product.

| Principle | In practice |
| --- | --- |
| The number is the hero | Tomorrow's AQI and its range are the largest elements on any screen that shows them |
| Uncertainty is drawn, not footnoted | Every forecast appears with its range; a forecast without a range is not rendered |
| Provenance is always in view | Source and "as of" time sit beside every measurement |
| One accent, used for interaction only | Colour otherwise belongs to data |
| Calm | Flat surfaces, hairline rules, no glow, no gradient fills, no blur, no decorative animation |
| Progressive disclosure | A resident sees four things; a researcher can reach everything |

### M.3 Personas, and the navigation tested against them

| Persona | Needs in the first ten seconds | Rarely needs |
| --- | --- | --- |
| **Resident or parent** — child with asthma, Chennai | Is tomorrow a problem for my child, and when is the least bad time to go out? | Model diagnostics |
| **Planner** — school sports coordinator, site supervisor | Should tomorrow's outdoor activity move, and to when? | Per-pollutant detail |
| **Policy analyst** — city or state official | How does this city compare, and what would a reduction change? | Individual advice |
| **Researcher, student, judge** | How do you know, how accurate, on what data, and what does it fail at? | Simplified wording |

The brief suggests eleven navigation labels. Tested against these personas, several collapse: an "Exposure Advisor" is not a place a resident goes, it is a property of the forecast they are already reading; "Alerts" is an action; "Model Trust", "Research Lab" and "Data Sources" serve one persona and belong together. Proposed structure:

| Section | Replaces from the brief | Primary persona |
| --- | --- | --- |
| **Today** | Command Center, Live Air, Exposure Advisor | Resident, planner |
| **Forecast** | Tomorrow Forecast | Resident, planner |
| **Map** | India Risk Map, City Intelligence | Analyst, resident |
| **Policy Lab** | Policy Lab | Analyst |
| **Evidence** | Research Lab, Model Trust, Data Sources | Researcher |

Alerts are a control in the header. The cohort and city selectors are global and persist. This structure is a hypothesis: it is to be checked with a first-click test on five people per persona before it is fixed.

## N. Page wireframes

Described top to bottom. Desktop uses a 12-column grid; the mobile order is given where it differs.

### N.1 Today

Answers: what is happening now, what is likely tomorrow, who should be careful, why, and what to consider doing.

| Region | Content | Notes |
| --- | --- | --- |
| Header bar | Product name · city selector · cohort selector · language · alerts | Selectors are global |
| Status line | "Measured at Alandur, Chennai · 8 minutes ago · source: OpenAQ (CPCB)" | Turns to a warning state when stale: "No fresh data since 14:00" |
| Now (4 columns) | Current AQI, category label and level, dominant pollutant, 24-hour sparkline | Measured and modelled values are visually distinct |
| Tomorrow (5 columns) | Expected AQI at display size · range bar · band probability bar · confidence word · trend against today | The range bar is part of the number, not a tooltip |
| For you (3 columns) | Advisory for the selected cohort: band, one action sentence, one cohort sentence | Each sentence links to its published source |
| Lowest-exposure window | 24-hour strip for tomorrow with the recommended two hours marked, reduction against the peak, and the absolute level in that window | Reads "No suitable lower-exposure window identified" when that is the truth |
| Why | One sentence naming the two largest drivers; link to full explanation | — |
| Track record | "Last 30 days: typical miss 14 AQI points; range contained the outcome on 27 of 30 days" | Read from stored verification |
| Footer | Sources, licences, disclaimer | Always present |

Mobile order: status line, Tomorrow, For you, Window, Now, Why, Track record. Tomorrow comes before Now because it is the decision.

### N.2 Forecast

| Region | Content |
| --- | --- |
| Selectors | City or station · cohort · date (tomorrow by default; past dates open the stored forecast beside the outcome) |
| Headline | Expected AQI, range, band probabilities, confidence, model version, issue time |
| Trajectory | Fourteen days of observed AQI, then tomorrow's range drawn as a band, with category guide lines labelled on the axis |
| Hourly | Tomorrow hour by hour with uncertainty band; window marked |
| Pollutants | Per-pollutant forecast with sub-index; dominant pollutant flagged |
| Weather tomorrow | Wind, boundary-layer height, rain, with a one-word reading of each ("stagnant", "ventilated") |
| All cohorts | Table: cohort, advisory band, the quantile it was issued from, the target under-warning rate |
| Why this forecast | Grouped drivers as a horizontal bar list, plain sentence above; expandable to full attribution |
| What-if | Sliders, clearly marked counterfactual, bounded |
| Days two and three | Shown only where validated; otherwise absent, not greyed |

### N.3 Map

| Region | Content |
| --- | --- |
| Map | India, station markers. Toggle: now · tomorrow expected · tomorrow upper bound · dominant pollutant · cohort advisory |
| Marker | Shape and number carry severity, colour reinforces it. Stale stations are hollow |
| Side panel | Ranked list of cities for the active layer; sortable; search |
| Drill-down | City → stations → station page with history and forecast |
| Layer honesty | Tomorrow layers appear only for stations with a valid forecast; others show "no forecast" |

### N.4 City

Seasonal pattern by month, station list with freshness, track record for that city, events (festival windows, described without causal language), archetype if the station-level clustering supports one.

### N.5 Policy Lab

| Region | Content |
| --- | --- |
| Framing | "A concentration scenario. It does not predict the effect of any measure." Fixed, not dismissible |
| Scenario builder | Up to three scenarios beside a baseline; per-pollutant reduction; scope by city, season, year |
| Results | For each scenario: AQI change, days moving band, cohort advisory-days, each **with a range** |
| Comparison | Small-multiple bars, common axis; table beneath |
| Method | What is and is not simulated; the weather-normalisation note |

### N.6 Evidence

Tabs: **Track record** (rolling error, rolling coverage, error by band, city and season — live from verification) · **Model** (version, training window, features, benchmark table, ablation) · **Calibration** (reliability diagram, interval coverage, under- and over-warning by cohort) · **Generalisation** (leave-one-city-out, excluded cities) · **Data** (sources, licences, missingness, quality flags, last retrieval) · **Method** (data card, model card, advisory method) · **Limitations** (the list in Part 5, in full).

### N.7 States every page must design for

| State | Treatment |
| --- | --- |
| Loading | Skeleton in the final layout |
| No fresh data | Named station, time of last reading, modelled value offered and labelled |
| Forecast withheld | Reason given in a sentence; never an empty panel |
| Low confidence | Forecast shown, range emphasised, advisory from the cautious quantile |
| Upstream outage | "Data temporarily unavailable", last successful retrieval time |
| Historical replay | A persistent band across the page: "Historical data, 2015–2020 — not a live forecast" |

## O. Design system

### O.1 Foundations

| Token | Specification |
| --- | --- |
| Typeface | One humanist or neo-grotesque sans for interface and prose; tabular lining numerals everywhere; a monospace only in the Evidence section |
| Type scale | 12 · 14 · 16 (body) · 20 · 28 · 40 · 72 (the AQI numeral) |
| Line length | 60–75 characters for prose |
| Spacing | 4-point base: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 |
| Grid | 12 columns to 1280 px; 8 columns tablet; 4 columns mobile; 24 px gutters desktop, 16 px mobile |
| Surfaces | Light theme first: paper-neutral background, white panels, one-pixel hairlines. A true dark theme is a second token set, not an inversion |
| Elevation | None beyond a hairline; a shadow only on floating elements |
| Radius | 4 px controls, 8 px panels |
| Accent | A single hue reserved for links, focus and selected controls |
| Motion | State changes only, 150 ms or less; nothing moves under reduced-motion |

### O.2 Severity system

Severity is the most important encoding in the product and must survive greyscale printing, colour-vision deficiency and a screen reader.

| Channel | Rule |
| --- | --- |
| Label | The CPCB category name is always present in text |
| Level | A number from 1 to 6 and a matching six-segment glyph accompany the label |
| Colour | An ordered ramp that remains monotone in lightness, checked for the common colour-vision deficiencies; the official CPCB category colour is shown as a small reference chip so the product agrees with official communication |
| Shape | Map markers change shape as well as colour above "Poor" |
| Text contrast | 4.5 : 1 minimum on every severity background |

### O.3 Components

Stat block · range bar · band-probability bar · freshness badge · source tag · cohort switch · advisory card · driver list · 24-hour window strip · track-record line · station marker · data table with sortable, sticky headers · scenario comparison · status banner · unavailable state. Each is specified with its empty, loading, stale and error variants before it is built.

### O.4 Chart rules

One message per chart, stated in its title as a sentence. Direct labels in place of legends where possible. Uncertainty always drawn. Bars start at zero. Category guide lines labelled on the axis. No dual axes, no three-dimensional effects, no decorative fills. Every chart has a table equivalent reachable by keyboard.

### O.5 Iconography

One line-icon set at a single stroke weight. No symbol characters used as icons. An icon never carries meaning alone.

### O.6 Accessibility

Keyboard reachability of every control with a visible focus ring; landmarks and labelled regions; severity announced as "AQI 187, Moderate, level 3 of 6"; live regions for data refresh; text resizable to 200% without loss; touch targets 44 px; a high-contrast token set. Target: WCAG 2.2 AA, checked with automated tools and one manual screen-reader pass per release.

### O.7 Languages

All strings externalised from the first commit of 2.0; layout tolerant of longer strings and of Tamil and Devanagari line heights. English, Tamil and Hindi first. The 1.0 Streamlit application carries advisory text in all three, but the Tamil and Hindi strings were machine-drafted and have not been reviewed by a fluent health communicator, and the web application dropped them. **Health advice is not machine-translated**: each translation is reviewed by a fluent speaker with health-communication experience before release, and an unreviewed language is not offered.

## U. Startup and SaaS roadmap

Monetisation follows proof, not the other way round.

| Stage | Goal | Offer | Evidence that it is working |
| --- | --- | --- | --- |
| 0 — Credibility | Show the forecast is accurate, in public | Free site with a live track-record page | Thirty days of verified forecasts, published |
| 1 — Citizen product | Useful daily for residents | Today, Forecast, Map, alerts, three languages | Return visits; alert opt-ins |
| 2 — Pilots | One real organisational user in each of two segments | Schools: outdoor-activity planner for the week. Employers of outdoor workers: shift-exposure view | A signed pilot; a decision actually changed because of the product |
| 3 — Services | Sustainable revenue | Forecast and alert API; organisation dashboards; research workspace | Paying customers |

Segments worth testing, in order of fit to what the system does well: schools; employers with outdoor workforces; hospitals and public-health communicators; municipal and smart-city teams; universities and NGOs.

Constraints that must be resolved before any revenue: the weather source's free tier is non-commercial; each station-data source's terms must be read for redistribution; advisory content needs professional review and clear limits of liability; and none of the vulnerable-group claims may be marketed as medical.

## V. Competition demonstration flow

Each scene is marked with what exists today. A demonstration given before the build must use only the scenes marked as existing, and say so.

| # | Scene | Shows | Status today |
| --- | --- | --- | --- |
| 1 | Select Chennai: live AQI, station, minutes since reading | Measurement with provenance | **Proposed** — 1.0 has no live data |
| 2 | Tomorrow's AQI with its range and band probabilities | Uncertainty as a first-class output | **Proposed** |
| 3 | Switch healthy adult → child → asthma | Advice differs, and each is issued at a stated risk level | **Partial** — cohort switch exists; risk level does not |
| 4 | Tomorrow's lowest-exposure window, with the absolute level | Honest relative guidance | **Partial** — seasonal climatology only |
| 5 | "Why this forecast?" | Plain sentence, then the driver list | **Partial** — fixed example only |
| 6 | Map of tomorrow's risk; toggle to the upper bound | Geography of uncertainty | **Proposed** |
| 7 | Policy Lab: PM2.5 lower by 20%; advisory-days by cohort, with ranges | Scenario, not prediction | **Implemented** without ranges |
| 8 | Evidence: thirty-day track record, coverage, drift, limitations | The system reporting on itself | **Proposed** |

The line to deliver over scene 8: *measurement, prediction, uncertainty, a decision made at a stated risk, and a public record of how often it was right.*

**A demonstration that is honest today** uses scenes 3, 5 and 7 on the historical replay, then shows the pilot tables P1–P5 as the motivation for 2.0: what the current system gets wrong, measured, and the experiment designed to fix it. For a research audience that is a stronger story than a polished interface.
