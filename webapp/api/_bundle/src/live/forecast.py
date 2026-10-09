"""Tomorrow's AQI for each city, from today's modelled conditions.

    python -m src.live.forecast            # print the forecast for all twelve cities
    python -m src.live.forecast Delhi      # one city

The trained LightGBM model is unchanged. What changes is where its inputs come
from, and the output says so in plain words: the inputs are modelled, some are
filled with typical values, and the accuracy figures attached are from a
backtest against measurements, not a promise.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src import config
from src.deploy.serverless_inference import _feature_order, _regression_booster
from src.deploy.tree_predict import predict_regression
from src.features import hai as hai_mod
from src.ingestion.settings import TARGET_CITIES
from src.live import cams
from src.live.features import IMPUTED, MIN_HISTORY_DAYS, build_features, finite, load_reference, missing_features, prepare_history

MODEL_NAME = "LightGBM regression, trained on CPCB city-day records from 2015 to 2020"
HISTORY_DAYS_SHOWN = 14

#: The correction is fitted against measurements, and the modelled data's error
#: changes with the season. Past this age it is dropped rather than trusted:
#: an old correction that scales winter smog down would under-warn.
CORRECTION_MAX_AGE_DAYS = 21

CAVEATS = [
    "Inputs are modelled concentrations (CAMS global, about 40 km), not station measurements.",
    "The model was trained on measured CPCB data from 2015-2020; modelled inputs and later years are outside what it was trained on.",
    "NO, NOx, NH3, benzene and toluene are not available live and are filled with each city's typical value for the month.",
    "This is not an official forecast. For official air quality, use the Central Pollution Control Board.",
    "The Health Advisory Index is not clinically validated and is not medical advice.",
]


def local_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=cams.TIMEZONE).tz_localize(None)


def predict_rows(features: pd.DataFrame) -> pd.Series:
    """Next-day AQI for every row that has every feature; NaN elsewhere."""
    order = _feature_order()["regression"]
    booster = _regression_booster()
    complete = features[order].notna().all(axis=1)
    values = [
        predict_regression(row, booster, order) if ok else float("nan")
        for row, ok in zip(features[order].to_dict("records"), complete)
    ]
    return pd.Series(values, index=features.index, name="AQI_next_predicted")


def _city_result(city: str, frame: pd.DataFrame, today: pd.Timestamp, reference: Dict[str, Any]) -> Dict[str, Any]:
    rows = frame.loc[frame["City"] == city].sort_values("Date")
    base = rows.loc[rows["Date"] == today]
    if base.empty:
        return {"city": city, "ok": False, "message": "No modelled data for today for this city."}
    row = base.iloc[0]

    order = _feature_order()["regression"]
    missing = missing_features(row, order)
    if missing:
        return {"city": city, "ok": False, "message": f"Not enough recent history to build the forecast ({len(missing)} inputs missing; {MIN_HISTORY_DAYS} days are needed)."}

    predicted = float(row["AQI_next_predicted"])
    bucket = hai_mod.bucket_from_aqi([predicted])[0]

    spread = (reference.get("backtest") or {}).get("error_quantiles")
    if spread:
        spread = (spread.get("by_city") or {}).get(city) or spread
    likely = None
    if spread:  # error = forecast minus measured, so the measured value sits at forecast minus error
        likely = [finite(max(0.0, predicted - spread["q90"])), finite(max(0.0, predicted - spread["q10"]))]

    tomorrow_row = rows.loc[rows["Date"] == today + pd.Timedelta(days=1)]
    modelled_tomorrow = finite(tomorrow_row.iloc[0]["AQI"]) if not tomorrow_row.empty else None

    recent = rows.loc[(rows["Date"] <= today) & (rows["Date"] > today - pd.Timedelta(days=HISTORY_DAYS_SHOWN))]
    cohorts = [
        {
            "cohort": cohort,
            "label": config.COHORT_LABELS[cohort],
            "hai": finite(row[f"HAI_{cohort}"], 1),
            "band": row[f"HAI_{cohort}_band"],
            "advisory": {"text": hai_mod.advisory(cohort, row[f"HAI_{cohort}_band"], language="en", dominant=row["dominant_pollutant"])["text"]},
        }
        for cohort in config.COHORTS
    ]

    return {
        "city": city,
        "ok": True,
        "today": {
            "date": str(today.date()),
            "aqi": finite(row["AQI"]),
            "bucket": row["AQI_Bucket"],
            "dominant_pollutant": row["dominant_pollutant"],
            "forecast_hours_in_daily_mean": int(row["forecast_hours"]),
            "concentrations": {p: finite(row[p], 2) for p in cams.POLLUTANTS},
            "concentrations_before_correction": {p: finite(row[f"{p}_modelled"], 2) for p in cams.POLLUTANTS},
            "units": {p: config.POLLUTANT_UNITS[p] for p in cams.POLLUTANTS},
        },
        "tomorrow": {
            "date": str((today + pd.Timedelta(days=1)).date()),
            "aqi": finite(predicted),
            "bucket": bucket,
            "likely_range": likely,
            "atmospheric_model_aqi": modelled_tomorrow,
        },
        "history": [{"date": str(d.date()), "aqi": finite(a)} for d, a in zip(recent["Date"], recent["AQI"])],
        "cohorts": cohorts,
    }


def live_forecast(
    cities: Optional[Iterable[str]] = None,
    now: Optional[pd.Timestamp] = None,
    fetcher: Optional[cams.Fetcher] = None,
    correct_bias: bool = True,
) -> Dict[str, Any]:
    """Forecast tomorrow for the given cities (all twelve by default). Never raises for one bad city."""
    names: List[str] = [c for c in (cities or TARGET_CITIES) if c in TARGET_CITIES]
    if not names:
        return {"ok": False, "message": f"Unknown city. Available: {', '.join(TARGET_CITIES)}."}

    now = now or local_now()
    today = now.normalize()
    reference = load_reference()

    try:
        hourly = cams.fetch_hourly({n: TARGET_CITIES[n] for n in names}, past_days=MIN_HISTORY_DAYS + 6, forecast_days=3, fetcher=fetcher)
    except cams.LiveSourceError as exc:
        return {"ok": False, "message": f"{exc}. No live forecast can be made without it; the historical explorer still works."}

    fitted_until = reference.get("bias_fitted_until")
    age = int((today - pd.Timestamp(fitted_until)).days) if fitted_until else None
    corrected = bool(correct_bias and reference.get("bias") and age is not None and age <= CORRECTION_MAX_AGE_DAYS)
    note = reference.get("bias_note")
    if reference.get("bias") and not corrected and correct_bias:
        note = f"No correction applied: the one fitted to {fitted_until} is {age} days old, past the {CORRECTION_MAX_AGE_DAYS}-day limit. Expect the forecast to run high."

    daily = cams.daily_means(hourly, now)
    frame = build_features(prepare_history(daily, reference, corrected), reference)
    frame["AQI_next_predicted"] = predict_rows(frame)
    return {
        "ok": True,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local_time": now.strftime("%Y-%m-%d %H:%M") + " IST",
        "inputs": {
            "source": cams.SOURCE,
            "source_type": cams.SOURCE_TYPE,
            "label": "MODELLED, not measured",
            "latest_hour": str(hourly["time"].max()),
            "corrected_against_measurements": corrected,
            "correction_note": note,
            "correction_fitted_until": fitted_until,
            "correction_age_days": age,
            "filled_with_typical_values": IMPUTED,
        },
        "model": MODEL_NAME,
        "evaluation": reference.get("backtest"),
        "caveats": CAVEATS,
        "cities": [_city_result(name, frame, today, reference) for name in names],
    }


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = live_forecast(argv or None)
    if not result["ok"]:
        print(result["message"])
        return 1
    inputs = result["inputs"]
    print(f"\nAirGuard live forecast | {result['local_time']} | inputs: {inputs['source']} | {inputs['label']}")
    print(f"correction: {inputs['correction_note']}")
    print(f"{'city':20s} {'today':>7s} {'':13s} {'tomorrow':>9s} {'':13s} {'likely range':>14s} {'atmos. model':>13s}")
    for city in result["cities"]:
        if not city["ok"]:
            print(f"{city['city']:20s} {city['message']}")
            continue
        t, n = city["today"], city["tomorrow"]
        likely = f"{n['likely_range'][0]:.0f}-{n['likely_range'][1]:.0f}" if n["likely_range"] else "n/a"
        print(f"{city['city']:20s} {t['aqi']:7.0f} {t['bucket']:13s} {n['aqi']:9.0f} {n['bucket']:13s} {likely:>14s} {str(n['atmospheric_model_aqi']):>13s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
