# Live next-day forecast — what was built and how good it is

The 1.0 application forecasts from a record that ends on 1 July 2020. This adds a forecast of **tomorrow's** AQI for the twelve cities, computed from **today's** conditions, and a test of that forecast against government monitors.

The short version: it works, it is honest about its inputs, and it is not accurate enough to rely on. The reason is the inputs, and the test shows that clearly.

## Status on 10 October 2026

| Item | State |
| --- | --- |
| Live forecast for 12 cities (`python -m src.live.forecast`) | **Working** |
| API endpoint and page (`/api/live_forecast`, `/live`) | **Built, tested locally** in an isolated copy of the deployment bundle |
| Tested against measurements | **Done**: 474 held-out city-days, 24 August to 7 October 2026 |
| Seven corrections the audit said the site owed | **Applied** to the pages |
| Deployed to the public site | **Not done.** The Vercel command-line login on this machine had expired; deployment needs the account owner to log in |
| Live ingestion into Supabase | **Verified**: 133 stations, 1,498 readings, 774 fire detections, 624 forecast hours stored; a second run wrote nothing |
| Ingestion running by itself every day | **Not built** |

## How the forecast is made

1. **Inputs.** Hourly PM2.5, PM10, NO₂, SO₂, CO and ozone for each city from the CAMS global atmospheric model, through Open-Meteo. No key is needed. These are **modelled** values on a grid of about 40 km. They are not station measurements, and everything the forecast returns says so.
2. **Daily values.** Hours are averaged into Indian calendar days, the way the training data's daily averages were. Today's value includes the hours still to come, taken from the atmospheric model's own forecast; the output says how many.
3. **Correction.** PM2.5, PM10 and ozone are multiplied by a per-city factor: the ratio of what CPCB monitors measured to what the model said, over the most recent 30 days of measurements. If the correction is more than 21 days old it is dropped and the output says so, because the model's error changes with the season and a stale factor that scales winter smog down would under-warn.
4. **Missing species.** NO, NOx, NH₃, benzene and toluene are not available. They are filled with each city's typical value for the month, from the training period. The AQI is computed before the fill, so it never rests on a filler.
5. **Features and model.** The same feature functions the 1.0 pipeline uses, and the unchanged LightGBM regression model. Nothing was retrained.
6. **Uncertainty.** The "likely range" is the middle 80% of the forecast's errors in the test below, taken per city.

Everything is fetched at request time. The endpoint holds no credential and needs no database.

## How good it is

`python -m src.live.backtest`. The forecast was replayed over the recent past and compared with what monitors measured the next day.

- **Truth**: an AQI from measured PM2.5, PM10 and ozone, averaged over the CPCB monitors in each city: 28,849 monitor-days from 332 sensors, giving 1,199 city-days between 22 June and 7 October 2026. OpenAQ still holds these past days even though its copy is not current. Only those three species are used because their units in OpenAQ are trustworthy.
- **No peeking**: the test walks forward a day at a time; the correction used for a day is fitted only on measurements at least three days older than it. Every figure below is from the last 40% of the window.

| Forecast for tomorrow | Mean miss (AQI) | Lean | Right category | Within one category | City-days |
| --- | --- | --- | --- | --- | --- |
| **AirGuard, as deployed** | **30.7** | +17.7 | 53.2% | 94.9% | 474 |
| AirGuard, correction two weeks old | 32.9 | +19.8 | 51.5% | 93.2% | 474 |
| AirGuard, no correction | 37.5 | +30.8 | 46.4% | 94.1% | 474 |
| Tomorrow = today, modelled | 35.8 | +14.4 | 50.8% | 92.6% | 474 |
| The atmospheric model's own next day | 32.2 | +14.7 | 55.1% | 96.2% | 474 |
| Tomorrow = today, **measured** | **12.8** | −0.7 | 74.9% | 98.9% | 447 |

What this says:

- The forecast misses by about 31 AQI points on average and leans high. It names the right category about half the time and is almost always within one category.
- It is slightly better than the two modelled baselines. The atmospheric-model baseline is flattered, because its past values are analyses and not day-ahead forecasts. So the machine-learning model adds a little; it does not add much.
- **Simply repeating today's measured value is more than twice as accurate as anything that uses modelled inputs.** The inputs are the limit. On the same day, the corrected modelled AQI is itself 30.8 points away from the measured one.
- Delhi and Gurugram are the worst: 61.4 and 67.5 points. The smaller southern cities are best: Thiruvananthapuram 14.7, Chennai 16.8.

### The same model on measured inputs

To separate what the inputs cost from what the model can do, the model was also fed measured PM2.5, PM10 and ozone (the three gases stayed modelled).

| | Mean miss (AQI) | Right category | City-days |
| --- | --- | --- | --- |
| AirGuard on measured inputs | 12.9 | 76.0% | 229 |
| Tomorrow = today, measured, same days | 12.6 | 76.4% | 229 |

With measured inputs the error falls from 31 to 13. But **on 2026 data the model does not beat the simple rule that tomorrow equals today.** The 1.0 report's margin over that rule (15.05 against 18.90, on 2019–20) is not reproduced here. This is a result, not a failure to hide. It comes with three qualifications: the window is June to October, when day-to-day change is small and the simple rule is at its strongest; five of the model's species were filled in and three were modelled; and the truth is an AQI from three species.

### Limits of the test

- Past modelled values are analyses. A live run uses a same-day forecast for the rest of today, so live accuracy is probably somewhat worse.
- One season. Nothing here covers winter, when pollution is highest and the modelled data's error is likely to change sign.
- Amritsar and Visakhapatnam each have a single monitor in the truth; Delhi has forty.
- The correction factors show how far the atmospheric model is from the monitors: its ozone is between two and five times the measured value in every city, and its PM10 is up to three times too low.

## What is on the page

`/live` shows tomorrow's AQI and category for each city, the likely range, today's modelled value, the atmospheric model's own figure for comparison, two weeks of history, the concentrations used and as modelled, the Health Advisory Index for today's modelled air, the test table above, and the caveats. If Open-Meteo cannot be reached the page says so and shows nothing in its place.

The same redeployment carries the corrections the audit listed: the classifier's score is no longer called confidence; the false statement about a lockdown flag is gone; the historical page is labelled a replay; the note on how not to read the SHAP ranking is added; cross-validation error is shown beside the single test year; the simulator's comparison with the lockdown is no longer called a check. Tamil and Hindi advisory text is not shown on the site.

## Commands

```
python -m src.live.forecast             tomorrow for all twelve cities
python -m src.live.forecast Delhi       one city
python -m src.live.backtest --fetch     download measurements again and re-test (about 7 minutes)
python -m src.live.backtest             re-test from the cached measurements and refresh the correction
python -m pytest tests/test_live.py -q  the tests
python -m src.deploy.vendor_for_vercel  rebuild the deployment bundle after any of the above
```

## What would make it good

1. **Current measurements.** Everything above points here. `api.data.gov.in` has refused connections since 7 October and OpenAQ's copy of the CPCB monitors has not advanced since 7 October. With measured inputs the error is 13, not 31.
2. **Retraining on recent data.** The model is from 2015–2020 and does not beat persistence on 2026. The measurements downloaded for this test are the start of a recent training set.
3. **A scheduled job that does not depend on a laptop**, to ingest each day, refresh the correction, and record each forecast so it can be scored against what happened.
4. **A winter of evidence** before any claim about severe days.
