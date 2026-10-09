"""How good is the live forecast? Test it against measurements, then fit the correction.

    python -m src.live.backtest --fetch     # download measured daily values from OpenAQ (several minutes)
    python -m src.live.backtest             # evaluate from the cached file and write the reference

The live forecast is driven by modelled concentrations. This module replays it
over the recent past and compares it with what government monitors measured,
which OpenAQ still holds for past days even though its copy is not current.

Design
------
* **Truth**: for each city and day, the mean across CPCB monitors of measured
  PM2.5, PM10 and ozone (OpenAQ daily aggregates with at least 75 % of the hours
  present), turned into an AQI with the CPCB sub-index formula. Only those
  three species are used because they are the ones whose units in OpenAQ are
  trustworthy; the measured AQI here is therefore an AQI from three species.
* **Forecast under test**: exactly ``src.live.forecast``'s path - modelled
  daily means, the training feature pipeline, the unchanged trained model.
* **Correction**: one multiplier per city and species (PM2.5, PM10, ozone), the
  ratio of the measured to the modelled median over the most recent thirty
  days of measurements.
* **No peeking**: the test walks forward a day at a time. The multipliers used
  for a day are fitted only on measurements at least three days older than it,
  which is how stale the measurements were when this was written. The same
  test is repeated with fourteen-day-old measurements, because the measured
  feed had stopped advancing and the correction will keep ageing.
* **A second question**: the same model is also run on *measured* PM2.5, PM10
  and ozone, to separate what the inputs cost from what the model can do.

One limitation is built in and stated in the output: past modelled values are
analyses, slightly better than the same-day forecast a live run has to use for
the hours of today still to come. Live accuracy is therefore likely a little
worse than the backtest.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src import config
from src.features import hai as hai_mod
from src.ingestion.settings import TARGET_CITIES
from src.live import cams, features
from src.live.forecast import predict_rows

LOGGER = config.get_logger(__name__)

MEASURED_PATH = config.RESULTS_DIR / "live_backtest_measured.csv"
REPORT_PATH = config.RESULTS_DIR / "live_backtest.json"

CORRECTED = ["PM2.5", "PM10", "O3"]  # species with trustworthy measured units
MIN_COVERAGE_PERCENT = 75.0
MIN_PAIRED_DAYS = 12
FACTOR_LIMITS = (0.2, 5.0)
HOLDOUT_SHARE = 0.4  # the most recent part of the window is what gets scored
WINDOW_DAYS = 110
CORRECTION_LOOKBACK_DAYS = 30
CORRECTION_DELAY_DAYS = 3  # how old the newest measurement was when this was written
STALE_DELAY_DAYS = 14
MIN_DAYS_FOR_CITY_SPREAD = 30


# --------------------------------------------------------------------------- #
# Measured truth
# --------------------------------------------------------------------------- #
def fetch_measured(start: str, end: str) -> pd.DataFrame:
    """Daily measured PM2.5, PM10 and ozone per CPCB monitor, from OpenAQ. Cached to disk."""
    from src.ingestion import db, openaq
    from src.ingestion import settings as settings_mod
    from src.ingestion.http import HttpClient, HttpError

    settings_mod.load_env()
    settings = settings_mod.get_settings()
    key = settings_mod.secret("OPENAQ_API_KEY")
    client = HttpClient(settings)

    # Which sensors to ask about comes from AirGuard's own database: the ones
    # ingestion saw reporting recently, in ug/m3, at government monitors.
    store = db.PostgresStore()
    try:
        sensors = store.query(
            "select distinct s.city, s.source_station_id, o.sensor_id, o.pollutant "
            "from airguard.air_quality_observations o join airguard.stations s using (station_pk) "
            "where o.source_id = 'OpenAQ' and s.upstream_provider = 'CPCB' and o.pollutant = any(%s) "
            "and o.raw_unit = 'µg/m³' and o.observed_at > %s and o.sensor_id is not null",
            (CORRECTED, (pd.Timestamp(end) - pd.Timedelta(days=30)).to_pydatetime()),
        )
    finally:
        store.close()
    LOGGER.info("measured truth: %d sensors at government monitors", len(sensors))

    rows: List[Dict[str, Any]] = []
    for index, (city, station, sensor, pollutant) in enumerate(sensors, start=1):
        try:
            payload = openaq._get(client, f"/sensors/{sensor}/days", key, {"date_from": start, "date_to": end, "limit": 1000}, label="openaq days")
        except HttpError as exc:
            LOGGER.warning("measured truth: sensor %s failed (%s)", sensor, exc.kind)
            continue
        for item in payload.get("results") or []:
            coverage = (item.get("coverage") or {}).get("percentComplete")
            local = (((item.get("period") or {}).get("datetimeFrom")) or {}).get("local")
            value = item.get("value")
            if local is None or value is None or coverage is None or coverage < MIN_COVERAGE_PERCENT or value < 0:
                continue
            rows.append({"City": city, "station": station, "pollutant": pollutant, "Date": local[:10], "value": float(value), "coverage": coverage})
        if index % 50 == 0:
            LOGGER.info("measured truth: %d of %d sensors", index, len(sensors))

    frame = pd.DataFrame(rows)
    frame.to_csv(MEASURED_PATH, index=False)
    LOGGER.info("measured truth: %d monitor-days written to %s", len(frame), MEASURED_PATH.name)
    return frame


def measured_city_days(station_days: pd.DataFrame) -> pd.DataFrame:
    """Average monitors into one measured value per city, day and species, then an AQI."""
    frame = station_days.copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    wide = frame.pivot_table(index=["City", "Date"], columns="pollutant", values="value", aggfunc="mean").reset_index()
    counts = frame.groupby(["City", "Date"])["station"].nunique().rename("monitors").reset_index()
    wide = wide.merge(counts, on=["City", "Date"])
    for pollutant in CORRECTED:
        if pollutant not in wide.columns:
            wide[pollutant] = np.nan
    scored = hai_mod.compute_sub_indices(wide[["City", "Date"] + CORRECTED])
    wide["AQI_measured"] = hai_mod.recompute_aqi(scored, min_pollutants=2)
    return wide.rename(columns={p: f"{p}_measured" for p in CORRECTED})


# --------------------------------------------------------------------------- #
# Correction and scoring
# --------------------------------------------------------------------------- #
def fit_factors(modelled: pd.DataFrame, measured: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Measured-to-modelled ratio of medians, per city and species."""
    paired = modelled.merge(measured, on=["City", "Date"])
    factors: Dict[str, Dict[str, float]] = {}
    for city, group in paired.groupby("City"):
        for pollutant in CORRECTED:
            both = group[[pollutant, f"{pollutant}_measured"]].dropna()
            if len(both) < MIN_PAIRED_DAYS or both[pollutant].median() <= 0:
                continue
            ratio = float(both[f"{pollutant}_measured"].median() / both[pollutant].median())
            factors.setdefault(city, {})[pollutant] = round(float(np.clip(ratio, *FACTOR_LIMITS)), 4)
    return factors


def _metrics(predicted: pd.Series, truth: pd.Series) -> Dict[str, Any]:
    both = pd.concat([predicted.rename("p"), truth.rename("t")], axis=1).dropna()
    if both.empty:
        return {"n": 0}
    error = both["p"] - both["t"]
    order = [name for name, _, _ in config.AQI_BUCKET_BOUNDS]
    rank = {name: i for i, name in enumerate(order)}
    p_bucket = pd.Series(hai_mod.bucket_from_aqi(both["p"].to_numpy())).map(rank)
    t_bucket = pd.Series(hai_mod.bucket_from_aqi(both["t"].to_numpy())).map(rank)
    return {
        "n": int(len(both)),
        "mae": round(float(error.abs().mean()), 1),
        "bias": round(float(error.mean()), 1),
        "rmse": round(float(np.sqrt((error**2).mean())), 1),
        "same_category_percent": round(float((p_bucket == t_bucket).mean() * 100), 1),
        "within_one_category_percent": round(float(((p_bucket - t_bucket).abs() <= 1).mean() * 100), 1),
    }


def replay(daily: pd.DataFrame, reference: Dict[str, Any], measured: pd.DataFrame) -> pd.DataFrame:
    """Run the live path over every past day and line each forecast up with what was measured next day."""
    frame = features.build_features(features.prepare_history(daily, reference, correct_bias=True), reference)
    frame["forecast"] = predict_rows(frame)
    frame = frame.merge(measured[["City", "Date", "AQI_measured", "monitors"]], on=["City", "Date"], how="left")
    by_city = frame.groupby("City", sort=False)
    frame["truth_next"] = by_city["AQI_measured"].shift(-1)
    frame["modelled_next"] = by_city["AQI"].shift(-1)
    # a row is only a forecast for *tomorrow* if tomorrow is the next row
    gap = by_city["Date"].shift(-1) - frame["Date"]
    frame.loc[gap != pd.Timedelta(days=1), ["truth_next", "modelled_next"]] = np.nan
    return frame


def walk_forward(daily: pd.DataFrame, measured: pd.DataFrame, base: Dict[str, Any], days: List[pd.Timestamp], delay: Optional[int]) -> pd.DataFrame:
    """Replay each day with the correction that would have existed then. ``delay=None`` means no correction."""
    scored: List[pd.DataFrame] = []
    for day in days:
        factors: Dict[str, Dict[str, float]] = {}
        if delay is not None:
            newest = day - pd.Timedelta(days=delay)
            oldest = newest - pd.Timedelta(days=CORRECTION_LOOKBACK_DAYS)
            factors = fit_factors(
                daily.loc[(daily["Date"] > oldest) & (daily["Date"] <= newest)],
                measured.loc[(measured["Date"] > oldest) & (measured["Date"] <= newest)],
            )
        window = daily.loc[(daily["Date"] > day - pd.Timedelta(days=features.MIN_HISTORY_DAYS + 7)) & (daily["Date"] <= day + pd.Timedelta(days=1))]
        frame = replay(window, dict(base, bias=factors), measured)
        scored.append(frame.loc[frame["Date"] == day])
    frame = pd.concat(scored, ignore_index=True)
    return frame.loc[frame["truth_next"].notna() & frame["forecast"].notna()]


def measured_inputs(daily: pd.DataFrame, measured: pd.DataFrame, base: Dict[str, Any], first_day: pd.Timestamp) -> pd.DataFrame:
    """The same model, fed measured PM2.5, PM10 and ozone. The three gases stay modelled."""
    columns = ["City", "Date"] + [f"{p}_measured" for p in CORRECTED]
    hybrid = daily.merge(measured[columns], on=["City", "Date"], how="left")
    for pollutant in CORRECTED:
        hybrid[pollutant] = hybrid[f"{pollutant}_measured"]
    hybrid = hybrid.drop(columns=[f"{p}_measured" for p in CORRECTED])
    frame = replay(hybrid, dict(base, bias={}), measured)
    return frame.loc[(frame["Date"] >= first_day) & frame["truth_next"].notna() & frame["forecast"].notna()]


def evaluate(daily: pd.DataFrame, measured: pd.DataFrame, base: Dict[str, Any]) -> Dict[str, Any]:
    dates = sorted(pd.Timestamp(d) for d in measured["Date"].unique())
    cut = dates[int(len(dates) * (1 - HOLDOUT_SHARE))]
    days = list(pd.date_range(cut, dates[-1] - pd.Timedelta(days=1)))

    fresh = walk_forward(daily, measured, base, days, CORRECTION_DELAY_DAYS)
    stale = walk_forward(daily, measured, base, days, STALE_DELAY_DAYS)
    raw = walk_forward(daily, measured, base, days, None)
    real = measured_inputs(daily, measured, base, cut)
    error = fresh["forecast"] - fresh["truth_next"]

    return {
        "window": {"first_day": str(dates[0].date()), "last_day": str(dates[-1].date()), "holdout_from": str(cut.date())},
        "truth": "an AQI from measured PM2.5, PM10 and ozone, averaged over CPCB monitors in each city (OpenAQ daily aggregates)",
        "holdout": {
            "airguard_corrected_inputs": _metrics(fresh["forecast"], fresh["truth_next"]),
            "airguard_correction_14_days_old": _metrics(stale["forecast"], stale["truth_next"]),
            "airguard_uncorrected_inputs": _metrics(raw["forecast"], raw["truth_next"]),
            "baseline_same_as_today_modelled": _metrics(fresh["AQI"], fresh["truth_next"]),
            "baseline_atmospheric_model_next_day": _metrics(fresh["modelled_next"], fresh["truth_next"]),
            "baseline_same_as_today_measured": _metrics(fresh["AQI_measured"], fresh["truth_next"]),
        },
        "holdout_by_city": {city: _metrics(group["forecast"], group["truth_next"]) for city, group in fresh.groupby("City")},
        "measured_inputs": {
            "what": "the same model fed measured PM2.5, PM10 and ozone; fewer days, because every look-back day must have a measurement",
            "airguard": _metrics(real["forecast"], real["truth_next"]),
            "same_as_today_measured": _metrics(real["AQI_measured"], real["truth_next"]),
        },
        "input_quality": {
            "modelled_vs_measured_same_day_corrected": _metrics(fresh["AQI"], fresh["AQI_measured"]),
            "modelled_vs_measured_same_day_uncorrected": _metrics(raw["AQI"], raw["AQI_measured"]),
        },
        "error_quantiles": {
            "definition": "forecast minus measured, held-out days",
            "q10": round(float(error.quantile(0.10)), 1),
            "q50": round(float(error.quantile(0.50)), 1),
            "q90": round(float(error.quantile(0.90)), 1),
            # A city's own spread where it has enough days: Delhi's errors are not Chennai's.
            "by_city": {
                city: {"q10": round(float(e.quantile(0.10)), 1), "q90": round(float(e.quantile(0.90)), 1), "n": int(len(e))}
                for city, e in error.groupby(fresh["City"])
                if len(e) >= MIN_DAYS_FOR_CITY_SPREAD
            },
        },
    }


def run(fetch: bool = False) -> Dict[str, Any]:
    today = pd.Timestamp.now(tz=cams.TIMEZONE).tz_localize(None).normalize()
    start = today - pd.Timedelta(days=WINDOW_DAYS)

    if fetch or not MEASURED_PATH.exists():
        fetch_measured(str(start.date()), str(today.date()))
    station_days = pd.read_csv(MEASURED_PATH)
    measured = measured_city_days(station_days)
    newest = pd.Timestamp(measured["Date"].max())

    # modelled values start earlier, so the first evaluated day already has its look-back
    warm_up = pd.Timestamp(measured["Date"].min()) - pd.Timedelta(days=features.MIN_HISTORY_DAYS + 2)
    hourly = cams.fetch_hourly(TARGET_CITIES, start_date=str(warm_up.date()), end_date=str(today.date()))
    daily = cams.daily_means(hourly)
    daily = daily.loc[daily["Date"] < today]  # complete past days only

    base = features.build_reference()
    result = evaluate(daily, measured, base)

    oldest = newest - pd.Timedelta(days=CORRECTION_LOOKBACK_DAYS)
    deployed = fit_factors(
        daily.loc[(daily["Date"] > oldest) & (daily["Date"] <= newest)],
        measured.loc[(measured["Date"] > oldest) & (measured["Date"] <= newest)],
    )
    headline = result["holdout"]["airguard_corrected_inputs"]
    real = result["measured_inputs"]
    reference = dict(
        base,
        bias=deployed,
        bias_fitted_until=str(newest.date()),
        bias_note=(
            f"PM2.5, PM10 and ozone are scaled per city to match the median of CPCB monitors over the "
            f"{CORRECTION_LOOKBACK_DAYS} days to {newest.date()} (measurements via OpenAQ)"
        ),
        backtest={
            "summary": (
                f"On {headline['n']} held-out city-days ({result['window']['holdout_from']} to {result['window']['last_day']}) "
                f"the forecast missed the measured AQI by {headline['mae']} points on average and named the right category "
                f"{headline['same_category_percent']}% of the time."
            ),
            "holdout": result["holdout"],
            "measured_inputs": real,
            "window": result["window"],
            "truth": result["truth"],
            "error_quantiles": result["error_quantiles"],
            "optimism_note": (
                "Past modelled values are analyses; a live run uses a same-day forecast for the hours still to come, "
                "so live accuracy is likely somewhat worse than this."
            ),
        },
    )
    features.write_reference(reference)

    result.update(
        generated_by="src/live/backtest.py",
        generated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        measured_monitor_days=int(len(station_days)),
        measured_city_days=int(measured["AQI_measured"].notna().sum()),
        factors_deployed=deployed,
        factors_fitted_until=str(newest.date()),
    )
    REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest the live forecast against measurements")
    parser.add_argument("--fetch", action="store_true", help="download measured daily values again")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    result = run(fetch=args.fetch)
    window = result["window"]
    print(f"\nwindow {window['first_day']} to {window['last_day']} | held out from {window['holdout_from']} | {result['measured_city_days']} measured city-days")
    print(f"{'forecast for tomorrow':42s} {'n':>5s} {'MAE':>7s} {'bias':>7s} {'RMSE':>7s} {'same cat.':>10s} {'within 1':>9s}")
    for name, m in result["holdout"].items():
        if m.get("n"):
            print(f"{name:42s} {m['n']:5d} {m['mae']:7.1f} {m['bias']:7.1f} {m['rmse']:7.1f} {m['same_category_percent']:9.1f}% {m['within_one_category_percent']:8.1f}%")
    print("\nby city (corrected inputs):")
    for city, m in result["holdout_by_city"].items():
        if m.get("n"):
            print(f"  {city:20s} n={m['n']:3d}  MAE {m['mae']:6.1f}  bias {m['bias']:6.1f}  same category {m['same_category_percent']:5.1f}%")
    real = result["measured_inputs"]
    print("\nthe same model on measured PM2.5, PM10 and ozone:")
    for name in ("airguard", "same_as_today_measured"):
        m = real[name]
        print(f"  {name:40s} {m['n']:5d} {m['mae']:7.1f} {m['bias']:7.1f} {m['rmse']:7.1f} {m['same_category_percent']:9.1f}% {m['within_one_category_percent']:8.1f}%")
    print("\ninput quality, same day:", json.dumps(result["input_quality"]))
    print("error quantiles:", json.dumps(result["error_quantiles"]))
    print(f"factors deployed (fitted on measurements to {result['factors_fitted_until']}):", json.dumps(result["factors_deployed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
