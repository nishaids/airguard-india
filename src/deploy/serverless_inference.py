"""Forecast orchestration for the Vercel deployment.

Reuses every piece of ``app.utils.inference`` that is pure numpy/pandas
(validation, the what-if recomputation, the cohort snapshot, history, the
drift check) unchanged, so the Streamlit application and this deployment run
the same code for everything except the two model calls. Those two calls are
replaced with the dependency-free tree evaluator in ``tree_predict.py``
because ``inference.load_model()`` unpickles a ``lightgbm``/``scikit-learn``
object, and importing either package pulls in scipy -- see
``export_boosters.py`` for the measured sizes that make that impossible in a
250 MB serverless function.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src import config
from src.deploy.tree_predict import predict_classification, predict_regression
from src.features import hai as hai_mod
from src.features.safe_window import lookup_window

DEPLOY_MODELS_DIR = config.MODELS_DIR / "deploy"


@lru_cache(maxsize=1)
def _regression_booster() -> Dict[str, Any]:
    return json.loads((DEPLOY_MODELS_DIR / "regression_booster.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _classification_booster() -> Dict[str, Any]:
    return json.loads((DEPLOY_MODELS_DIR / "classification_booster.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _classification_classes() -> list:
    return json.loads((DEPLOY_MODELS_DIR / "classification_classes.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _feature_order() -> Dict[str, list]:
    return json.loads((DEPLOY_MODELS_DIR / "feature_order.json").read_text(encoding="utf-8"))


def deployed_model_names() -> Dict[str, str]:
    """Names shown to the deployed application's users.

    Regression is unchanged: the tuned LightGBM model reported everywhere else.
    Classification differs from the Streamlit deployment's XGBoost + SMOTE, and
    that difference is stated here rather than hidden, matching
    ``results/deployment_classifier.json``.
    """
    from app.utils import inference as streamlit_inference

    names = streamlit_inference.deployed_model_names()
    names["classification"] = "LightGBM + SMOTE (Vercel deployment; XGBoost + SMOTE is the reported best model)"
    return names


def forecast(
    city: str,
    requested: Any,
    cohort: str = "healthy_adult",
    adjustments: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Same contract as ``app.utils.inference.forecast``, served without lightgbm/sklearn."""
    from app.utils import inference as streamlit_inference

    validation = streamlit_inference.validate_request(city, requested)
    if not validation.ok:
        return {"ok": False, "messages": validation.messages}

    row = streamlit_inference._row_for(validation.city, validation.date)
    if row is None:
        return {"ok": False, "messages": [f"No engineered record for {city} on {validation.date}."]}

    adjusted, applied = streamlit_inference.apply_what_if(row, adjustments or {})
    order = _feature_order()

    regression_row = {name: float(adjusted[name]) for name in order["regression"]}
    classification_row = {name: float(adjusted[name]) for name in order["classification"]}

    predicted_aqi = predict_regression(regression_row, _regression_booster(), order["regression"])
    classification_result = predict_classification(
        classification_row, _classification_booster(), _classification_classes(), order["classification"]
    )
    predicted_bucket = classification_result["label"]
    confidence = classification_result["confidence"]
    distribution = {k: round(v, 4) for k, v in classification_result["distribution"].items()}

    snapshot = streamlit_inference.cohort_snapshot(adjusted, cohort)
    season = config.SEASON_OF_MONTH[validation.date.month]

    windows = streamlit_inference.load_results("safe_windows.json")
    safe_window = lookup_window(validation.city, season, windows) if windows else None

    advisory = hai_mod.advisory(
        cohort, snapshot["band"], language="en", dominant=snapshot["dominant_pollutant"], safe_window=safe_window
    )

    actual_aqi = row.get("AQI_next")
    actual_bucket = row.get("AQI_Bucket_next")

    all_cohorts = []
    for candidate in config.COHORTS:
        candidate_snapshot = streamlit_inference.cohort_snapshot(adjusted, candidate)
        all_cohorts.append(
            {
                "cohort": candidate,
                "cohort_label": config.COHORT_LABELS[candidate],
                "hai": candidate_snapshot["hai"],
                "band": candidate_snapshot["band"],
            }
        )

    drift = streamlit_inference.drift_check(
        {p: float(adjusted[p]) for p in config.HAI_POLLUTANTS if p in adjusted.index}
    )

    history_frame = streamlit_inference.history(validation.city, validation.date, days=30).copy()
    history_frame["Date"] = history_frame["Date"].dt.strftime("%Y-%m-%d")
    history_records = json.loads(history_frame[["Date", "AQI"]].to_json(orient="records"))

    return {
        "ok": True,
        "city": validation.city,
        "date": str(validation.date.date()),
        "forecast_date": str((validation.date + pd.Timedelta(days=1)).date()),
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
        "predicted_aqi": round(float(predicted_aqi), 1),
        "predicted_bucket": predicted_bucket,
        "confidence": round(float(confidence), 4) if confidence is not None else None,
        "bucket_distribution": distribution,
        "cohort": snapshot,
        "all_cohorts": all_cohorts,
        "safe_window": safe_window,
        "advisory": advisory,
        "actual_next_aqi": None if pd.isna(actual_aqi) else round(float(actual_aqi), 1),
        "actual_next_bucket": None if pd.isna(actual_bucket) else str(actual_bucket),
        "drift": drift,
        "models": deployed_model_names(),
        "history": history_records,
    }
