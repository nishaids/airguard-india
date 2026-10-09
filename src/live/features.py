"""Turn a table of daily modelled concentrations into the model's feature row.

The trained model expects exactly the columns the 1.0 feature pipeline builds
from the cleaned historical record. This module makes the live table look like
that record and then calls the *same* functions, so a live feature means what
it meant in training.

Three things differ from training, and each is recorded on the output:

* the concentrations are modelled, and may be scaled by a per-city correction
  fitted against measurements (``reference["bias"]``);
* five species the atmospheric model does not provide (NO, NOx, NH3, benzene,
  toluene) are filled with the city's typical value for the month, taken from
  the training period;
* the AQI is recomputed from the daily concentrations with the CPCB formula,
  because no published AQI exists for a modelled day.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src import config
from src.features import hai as hai_mod
from src.live import cams

REFERENCE_PATH = config.MODELS_DIR / "deploy" / "live_reference.json"

#: Species the training data has and the atmospheric model does not.
IMPUTED = ["NO", "NOx", "NH3", "Benzene", "Toluene"]

#: First day of the training record: ``days_since_start`` counts from here.
TRAINING_ORIGIN = pd.Timestamp("2015-01-01")

#: The longest look-back any feature uses, in days, plus the day itself.
MIN_HISTORY_DAYS = max(config.ROLLING_WINDOWS) + 1


@lru_cache(maxsize=1)
def load_reference() -> Dict[str, Any]:
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))


def prepare_history(daily: pd.DataFrame, reference: Dict[str, Any], correct_bias: bool = True) -> pd.DataFrame:
    """Give the modelled daily table the columns and meaning of the cleaned training table."""
    out = daily.sort_values(["City", "Date"]).reset_index(drop=True).copy()

    bias = reference.get("bias", {}) if correct_bias else {}
    for pollutant in cams.POLLUTANTS:
        out[f"{pollutant}_modelled"] = out[pollutant]
        factors = out["City"].map(lambda city, p=pollutant: (bias.get(city) or {}).get(p, 1.0))
        out[pollutant] = out[pollutant] * factors

    # The AQI is computed before the typical values are filled in, so that it
    # rests only on the six species that describe today and never on a filler.
    out = hai_mod.compute_sub_indices(out)
    out["AQI"] = hai_mod.recompute_aqi(out)
    out["AQI_Bucket"] = hai_mod.bucket_from_aqi(out["AQI"].to_numpy())
    out["dominant_pollutant"] = hai_mod.dominant_pollutant(out)

    typical = reference["typical_by_city_month"]
    months = out["Date"].dt.month.astype(str)
    for pollutant in IMPUTED:
        out[pollutant] = [
            (typical.get(city) or {}).get(month, {}).get(pollutant, reference["typical_overall"][pollutant])
            for city, month in zip(out["City"], months)
        ]
    out["inserted_calendar_day"] = 0
    out["aqi_above_scale"] = (out["AQI"] > 500).astype(int)
    out["n_imputed_pollutants"] = len(IMPUTED)
    return out


def build_features(history: pd.DataFrame, reference: Dict[str, Any]) -> pd.DataFrame:
    """Run the training feature pipeline over a prepared history. One row per city and day."""
    from src.features import build  # imported here: it pulls in the whole 1.0 pipeline

    frame = build.add_temporal_features(history)
    frame["days_since_start"] = (frame["Date"] - TRAINING_ORIGIN).dt.days
    frame, _ = build.add_lag_features(frame)
    frame, _ = build.add_rolling_features(frame)
    frame, _ = build.add_ratio_features(frame)
    frame = hai_mod.add_all_cohort_hai(frame)

    encoding = reference["city_target_enc"]
    frame["City_target_enc"] = frame["City"].map(encoding).fillna(reference["city_target_enc_overall"])
    return frame


def missing_features(row: pd.Series, feature_order: List[str]) -> List[str]:
    """Features the model wants that this row cannot supply (too little history, or a gap)."""
    return [name for name in feature_order if name not in row.index or pd.isna(row[name])]


def build_reference() -> Dict[str, Any]:
    """Everything the live path needs from the training period, as plain numbers.

    Computed from rows before the train/test boundary only, so nothing here has
    seen the test period.
    """
    from src.data.clean import CLEAN_PATH

    boundary = pd.Timestamp(json.loads((config.PROCESSED_DIR / "feature_columns.json").read_text(encoding="utf-8"))["split_boundary"])
    clean = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    train = clean.loc[clean["Date"] < boundary]

    by_city_month: Dict[str, Dict[str, Dict[str, float]]] = {}
    for (city, month), group in train.groupby(["City", train["Date"].dt.month]):
        by_city_month.setdefault(city, {})[str(int(month))] = {p: round(float(group[p].median()), 4) for p in IMPUTED}

    return {
        "generated_by": "src/live/features.py::build_reference",
        "training_period_end": str((boundary - pd.Timedelta(days=1)).date()),
        "typical_by_city_month": by_city_month,
        "typical_overall": {p: round(float(train[p].median()), 4) for p in IMPUTED},
        "city_target_enc": {city: round(float(v), 4) for city, v in train.groupby("City")["AQI"].mean().items()},
        "city_target_enc_overall": round(float(train["AQI"].mean()), 4),
        "bias": {},
        "bias_note": "no correction fitted",
    }


def write_reference(reference: Dict[str, Any]) -> None:
    REFERENCE_PATH.write_text(json.dumps(reference, indent=2), encoding="utf-8")
    load_reference.cache_clear()


def finite(value: Any, digits: int = 1) -> Any:
    """A JSON-safe number: ``None`` for NaN or infinity."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if np.isfinite(number) else None
