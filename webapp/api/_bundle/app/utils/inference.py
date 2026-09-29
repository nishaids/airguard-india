"""Inference, caching and input validation for the AirGuard India application.

The application never recomputes anything the pipeline has already computed. It
loads the versioned model artefacts and the results JSON written by ``src/``, and
this module is the single boundary between those artefacts and the Streamlit
pages. Keeping the boundary in one place means the pages contain presentation
logic only, and that the cold-start cost is paid once per session.

Production hygiene provided here
--------------------------------
* ``@st.cache_resource`` for models and ``@st.cache_data`` for tables, so a
  session loads each artefact once.
* Input validation on every public entry point, with a typed result rather than
  an exception, so a page can render a message instead of a traceback.
* Graceful fallback when a requested city or date lies outside the record.
* A drift check comparing a live input vector against the training distribution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as date_type
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src import config
from src.features import hai as hai_mod

PROJECT_ROOT = config.PROJECT_ROOT


# --------------------------------------------------------------------------- #
# Streamlit cache shims
# --------------------------------------------------------------------------- #
try:  # pragma: no cover - exercised only inside Streamlit
    import streamlit as st

    cache_data = st.cache_data(show_spinner=False)
    cache_resource = st.cache_resource(show_spinner=False)
except Exception:  # pragma: no cover - importable outside Streamlit for tests
    cache_data = lru_cache(maxsize=None)
    cache_resource = lru_cache(maxsize=None)


# --------------------------------------------------------------------------- #
# Artefact loading
# --------------------------------------------------------------------------- #
@cache_data
def load_results(name: str) -> Dict[str, Any]:
    """Load a results JSON by file name, returning an empty mapping if absent."""
    path = config.RESULTS_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@cache_data
def load_features() -> pd.DataFrame:
    """Load the engineered feature matrix used for lookups and history charts."""
    from src.features.build import FEATURES_PATH

    frame = pd.read_csv(FEATURES_PATH, parse_dates=["Date"])
    return frame.sort_values(["City", "Date"]).reset_index(drop=True)


@cache_data
def load_clean() -> pd.DataFrame:
    """Load the cleaned daily table."""
    from src.data.clean import CLEAN_PATH

    return pd.read_csv(CLEAN_PATH, parse_dates=["Date"]).sort_values(["City", "Date"])


@cache_data
def feature_columns() -> Dict[str, Any]:
    """Load the retained feature lists."""
    from src.features.build import FEATURE_COLUMNS_PATH

    return json.loads(FEATURE_COLUMNS_PATH.read_text(encoding="utf-8"))


@cache_resource
def load_model(kind: str) -> Any:
    """Load a deployed model artefact.

    Parameters
    ----------
    kind:
        ``"regression"`` or ``"classification"``. The tuned artefact is preferred
        when it exists and the tuning report shows it improved the primary
        metric; otherwise the untuned winner is loaded. The decision is read from
        ``results/tuning_report.json`` rather than assumed.
    """
    import joblib

    tuning = load_results("tuning_report.json")
    results = load_results(f"evaluation_{kind}.json")

    if tuning and kind in tuning:
        entry = tuning[kind]
        improved = (
            entry["delta"]["MAE"] < 0
            if kind == "regression"
            else entry["delta"]["macro_f1"] > 0
        )
        candidate = PROJECT_ROOT / entry["artifact"]
        if improved and candidate.exists():
            return joblib.load(candidate)

    best = results.get("best_model")
    for record in results.get("results", []):
        if record["model"] == best and record.get("artifact"):
            path = PROJECT_ROOT / record["artifact"]
            if path.exists():
                return joblib.load(path)
    raise FileNotFoundError(f"No deployable {kind} artefact found. Run the pipeline first.")


@cache_data
def deployed_model_names() -> Dict[str, str]:
    """Return the human-readable name of the model deployed for each task."""
    tuning = load_results("tuning_report.json")
    names: Dict[str, str] = {}
    for kind in ("regression", "classification"):
        results = load_results(f"evaluation_{kind}.json")
        name = results.get("best_model", "unknown")
        if tuning and kind in tuning:
            entry = tuning[kind]
            improved = (
                entry["delta"]["MAE"] < 0
                if kind == "regression"
                else entry["delta"]["macro_f1"] > 0
            )
            if improved:
                name = f"{entry['model']} (tuned)"
        names[kind] = name
    return names


@cache_data
def available_cities() -> List[str]:
    """Return the cities the deployed models cover."""
    return sorted(load_clean()["City"].unique().tolist())


@cache_data
def date_bounds(city: Optional[str] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Return the first and last date available, optionally for one city."""
    frame = load_features()
    if city:
        frame = frame.loc[frame["City"] == city]
    return frame["Date"].min(), frame["Date"].max()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
@dataclass
class ValidationResult:
    """Outcome of validating a user request, with any fallback that was applied."""

    ok: bool
    city: Optional[str] = None
    date: Optional[pd.Timestamp] = None
    messages: List[str] = field(default_factory=list)
    fallback_applied: bool = False


def validate_request(city: str, requested: Any) -> ValidationResult:
    """Validate a city and date, falling back to the nearest available record.

    The application must not raise on any input. An unknown city is rejected with
    an explanation; a date outside the covered range is snapped to the nearest
    available date for that city and the substitution is reported, so the page
    can display what it actually used.
    """
    cities = available_cities()
    if city not in cities:
        return ValidationResult(
            ok=False,
            messages=[
                f"'{city}' is not covered. The deployed models cover "
                f"{len(cities)} cities: {', '.join(cities)}."
            ],
        )

    frame = load_features()
    subset = frame.loc[frame["City"] == city, "Date"]
    if subset.empty:
        return ValidationResult(ok=False, messages=[f"No records available for {city}."])

    try:
        target = pd.Timestamp(requested)
    except (ValueError, TypeError):
        return ValidationResult(ok=False, messages=[f"'{requested}' is not a valid date."])

    low, high = subset.min(), subset.max()
    messages: List[str] = []
    fallback = False
    if target < low or target > high:
        nearest = low if target < low else high
        messages.append(
            f"{target.date()} is outside the record for {city} "
            f"({low.date()} to {high.date()}). Showing {nearest.date()} instead."
        )
        target, fallback = nearest, True
    elif target not in set(subset):
        position = (subset - target).abs().idxmin()
        nearest = frame.loc[position, "Date"]
        messages.append(f"No record for {target.date()}; showing {nearest.date()}.")
        target, fallback = nearest, True

    return ValidationResult(
        ok=True, city=city, date=target, messages=messages, fallback_applied=fallback
    )


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def _row_for(city: str, target: pd.Timestamp) -> Optional[pd.Series]:
    """Return the engineered feature row for one city-day."""
    frame = load_features()
    match = frame.loc[(frame["City"] == city) & (frame["Date"] == target)]
    return None if match.empty else match.iloc[0]


def apply_what_if(
    row: pd.Series, adjustments: Dict[str, float]
) -> Tuple[pd.Series, Dict[str, float]]:
    """Apply proportional what-if adjustments and recompute dependent features.

    Adjusting a concentration in isolation would leave the engineered ratio
    features, sub-indices and HAI values describing the unadjusted day, so every
    quantity derived from the adjusted pollutants is recomputed here. Lag and
    rolling features describe days that already happened and are deliberately
    left untouched: a what-if on today does not rewrite history.

    Parameters
    ----------
    row:
        An engineered feature row.
    adjustments:
        Mapping of pollutant to the proportion removed, so ``0.2`` means a 20 per
        cent reduction. Negative values increase the concentration.
    """
    adjusted = row.copy()
    applied: Dict[str, float] = {}
    for pollutant, fraction in adjustments.items():
        if pollutant in adjusted.index and fraction:
            adjusted[pollutant] = float(adjusted[pollutant]) * (1.0 - float(fraction))
            applied[pollutant] = float(fraction)

    if not applied:
        return adjusted, applied

    frame = adjusted.to_frame().T
    for column in config.POLLUTANT_COLS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = hai_mod.compute_sub_indices(frame)
    for pollutant in config.AQI_POLLUTANTS:
        name = f"sub_{pollutant}"
        if name in frame.columns:
            adjusted[name] = float(frame[name].iloc[0])

    recomputed = hai_mod.recompute_aqi(frame)
    if "AQI_recomputed" in adjusted.index and pd.notna(recomputed.iloc[0]):
        adjusted["AQI_recomputed"] = float(recomputed.iloc[0])
    if pd.notna(recomputed.iloc[0]) and "AQI" in adjusted.index:
        adjusted["AQI"] = float(recomputed.iloc[0])

    epsilon = 1e-6
    if {"PM2.5", "PM10"}.issubset(adjusted.index):
        adjusted["pm_ratio"] = min(20.0, float(adjusted["PM2.5"]) / (float(adjusted["PM10"]) + epsilon))
        adjusted["pm_coarse"] = max(0.0, float(adjusted["PM10"]) - float(adjusted["PM2.5"]))
    if {"NO2", "NOx"}.issubset(adjusted.index):
        adjusted["no2_nox_ratio"] = min(20.0, float(adjusted["NO2"]) / (float(adjusted["NOx"]) + epsilon))
    if {"SO2", "PM2.5"}.issubset(adjusted.index):
        adjusted["so2_pm25_ratio"] = min(20.0, float(adjusted["SO2"]) / (float(adjusted["PM2.5"]) + epsilon))
    if {"O3", "NO2"}.issubset(adjusted.index):
        adjusted["o3_no2_ratio"] = min(20.0, float(adjusted["O3"]) / (float(adjusted["NO2"]) + epsilon))
    if set(["PM2.5", "PM10", "NO2", "SO2", "O3"]).issubset(adjusted.index):
        adjusted["total_pollutant_load"] = float(
            sum(float(adjusted[p]) for p in ["PM2.5", "PM10", "NO2", "SO2", "O3"])
        )

    for cohort in config.COHORTS:
        name = f"HAI_{cohort}"
        if name in adjusted.index:
            adjusted[name] = float(hai_mod.compute_hai(frame, cohort).iloc[0])

    return adjusted, applied


def cohort_snapshot(row: pd.Series, cohort: str) -> Dict[str, Any]:
    """Return the HAI value, band and dominant pollutant for one cohort on one day."""
    frame = row.to_frame().T
    for column in config.POLLUTANT_COLS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = hai_mod.compute_sub_indices(frame)

    value = float(hai_mod.compute_hai(frame, cohort).iloc[0])
    band = hai_mod.band_of(np.array([value]))[0]
    dominant = hai_mod.dominant_pollutant(frame).iloc[0]
    return {
        "cohort": cohort,
        "cohort_label": config.COHORT_LABELS[cohort],
        "hai": round(value, 2),
        "band": band,
        "dominant_pollutant": dominant,
        "vulnerability_factors": hai_mod.VULNERABILITY[cohort],
        "rationale": hai_mod.COHORT_RATIONALE[cohort],
    }


def forecast(
    city: str,
    requested: Any,
    cohort: str = "healthy_adult",
    adjustments: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Produce the full next-day forecast package for one city, date and cohort.

    Returns
    -------
    dict
        Either ``{"ok": False, "messages": [...]}`` or a complete package with the
        predicted AQI, predicted bucket with its confidence, the cohort HAI and
        band, the dominant pollutant, the safest outdoor window, and the actual
        outcome where the record contains it.
    """
    validation = validate_request(city, requested)
    if not validation.ok:
        return {"ok": False, "messages": validation.messages}

    row = _row_for(validation.city, validation.date)
    if row is None:
        return {"ok": False, "messages": [f"No engineered record for {city} on {validation.date}."]}

    adjusted, applied = apply_what_if(row, adjustments or {})
    columns = feature_columns()

    regression_model = load_model("regression")
    classification_model = load_model("classification")

    regression_features = pd.DataFrame([adjusted[columns["regression"]].to_dict()])
    classification_features = pd.DataFrame([adjusted[columns["classification"]].to_dict()])
    regression_features = regression_features.astype(float)
    classification_features = classification_features.astype(float)

    predicted_aqi = float(regression_model.predict(regression_features)[0])
    predicted_bucket = str(classification_model.predict(classification_features)[0])

    confidence: Optional[float] = None
    distribution: Dict[str, float] = {}
    if hasattr(classification_model, "predict_proba"):
        probabilities = classification_model.predict_proba(classification_features)[0]
        classes = list(getattr(classification_model, "classes_", []))
        distribution = {
            str(label): round(float(p), 4) for label, p in zip(classes, probabilities)
        }
        confidence = round(float(np.max(probabilities)), 4)

    snapshot = cohort_snapshot(adjusted, cohort)
    season = config.SEASON_OF_MONTH[validation.date.month]

    from src.features.safe_window import lookup_window

    windows = load_results("safe_windows.json")
    safe_window = lookup_window(validation.city, season, windows) if windows else None

    advisory = hai_mod.advisory(
        cohort,
        snapshot["band"],
        language="en",
        dominant=snapshot["dominant_pollutant"],
        safe_window=safe_window,
    )

    actual_aqi = row.get("AQI_next")
    actual_bucket = row.get("AQI_Bucket_next")

    return {
        "ok": True,
        "city": validation.city,
        "date": validation.date,
        "forecast_date": validation.date + pd.Timedelta(days=1),
        "season": season,
        "messages": validation.messages,
        "fallback_applied": validation.fallback_applied,
        "what_if_applied": applied,
        "observed_today": {
            pollutant: round(float(adjusted[pollutant]), 2)
            for pollutant in config.HAI_POLLUTANTS
            if pollutant in adjusted.index
        },
        "observed_aqi_today": round(float(adjusted["AQI"]), 1) if "AQI" in adjusted.index else None,
        "predicted_aqi": round(predicted_aqi, 1),
        "predicted_bucket": predicted_bucket,
        "confidence": confidence,
        "bucket_distribution": distribution,
        "cohort": snapshot,
        "safe_window": safe_window,
        "advisory": advisory,
        "actual_next_aqi": None if pd.isna(actual_aqi) else round(float(actual_aqi), 1),
        "actual_next_bucket": None if pd.isna(actual_bucket) else str(actual_bucket),
        "models": deployed_model_names(),
    }


def history(city: str, end: pd.Timestamp, days: int = 30) -> pd.DataFrame:
    """Return the trailing ``days`` of observed AQI for a city."""
    frame = load_features()
    subset = frame.loc[
        (frame["City"] == city)
        & (frame["Date"] <= end)
        & (frame["Date"] > end - pd.Timedelta(days=days))
    ]
    return subset[["Date", "AQI", "AQI_Bucket"] + config.HAI_POLLUTANTS].copy()


# --------------------------------------------------------------------------- #
# Drift
# --------------------------------------------------------------------------- #
@cache_data
def training_reference() -> Dict[str, Dict[str, float]]:
    """Summarise the training-period distribution of each pollutant."""
    columns = feature_columns()
    boundary = pd.Timestamp(columns["split_boundary"])
    frame = load_features()
    train = frame.loc[frame["Date"] < boundary]
    return {
        pollutant: {
            "mean": float(train[pollutant].mean()),
            "std": float(train[pollutant].std()),
            "p01": float(train[pollutant].quantile(0.01)),
            "p99": float(train[pollutant].quantile(0.99)),
        }
        for pollutant in config.HAI_POLLUTANTS
        if pollutant in train.columns
    }


def drift_check(observations: Dict[str, float], threshold: float = 3.0) -> Dict[str, Any]:
    """Compare a live input vector against the training distribution.

    This is the deployment-monitoring stub. A model is only trustworthy on inputs
    resembling those it was fitted on, and an input far outside the training
    range is a reason to caveat the forecast rather than to suppress it. The check
    reports a standardised distance per pollutant and flags any exceeding
    ``threshold`` standard deviations.
    """
    reference = training_reference()
    flagged: List[Dict[str, Any]] = []
    for pollutant, value in observations.items():
        stats = reference.get(pollutant)
        if not stats or stats["std"] <= 0:
            continue
        z = (float(value) - stats["mean"]) / stats["std"]
        outside = not (stats["p01"] <= float(value) <= stats["p99"])
        if abs(z) > threshold or outside:
            flagged.append(
                {
                    "pollutant": pollutant,
                    "value": round(float(value), 2),
                    "training_mean": round(stats["mean"], 2),
                    "z_score": round(float(z), 2),
                    "outside_training_p01_p99": outside,
                }
            )
    return {
        "threshold_sd": threshold,
        "n_flagged": len(flagged),
        "flagged": flagged,
        "verdict": (
            "Input resembles the training distribution."
            if not flagged
            else "Input lies outside the range the model was fitted on; treat the "
            "forecast with additional caution."
        ),
    }
