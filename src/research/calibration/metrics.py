"""Error metrics, named for what they are.

Exact error metrics (MAE, RMSE, bias, coefficient of determination) are computed
only on days whose measured index is an exact value. A day in the open-ended
Severe band is a lower bound (>= 401), so its error is not identifiable; those
days are scored by category, by exceedance and by how far below 401 the
forecast fell. Nothing here is called "accuracy" except the share of days whose
forecast category equals the observed category.
"""
from __future__ import annotations

import math

import numpy as np

EDGES = (50, 100, 200, 300, 400)
LABELS = ('Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe')
SEVERE_FLOOR = 401.0


def bands(values):
    """CPCB category index 0-5 for index values."""
    return np.digitize(np.asarray(values, dtype=float), EDGES, right=True)


def _clean(observed, forecast):
    observed = np.asarray(observed, dtype=float)
    forecast = np.asarray(forecast, dtype=float)
    if observed.shape != forecast.shape:
        raise ValueError('Observed and forecast must have the same shape.')
    if len(observed) and (not np.isfinite(observed).all() or not np.isfinite(forecast).all()):
        raise ValueError('Metrics need finite pairs; drop undefined forecasts before scoring.')
    return observed, forecast


def regression(observed, forecast):
    """MAE, RMSE, mean bias (forecast minus observed) and the coefficient of determination."""
    observed, forecast = _clean(observed, forecast)
    n = len(observed)
    if n == 0:
        return {'n': 0, 'mae': None, 'rmse': None, 'bias': None, 'r2': None}
    error = forecast - observed
    total = float(((observed - observed.mean()) ** 2).sum())
    return {
        'n': n,
        'mae': float(np.abs(error).mean()),
        'rmse': float(math.sqrt((error ** 2).mean())),
        'bias': float(error.mean()),
        'r2': float(1 - (error ** 2).sum() / total) if n > 1 and total > 0 else None,
    }


def categorical(observed_category, forecast):
    """Category agreement over the six CPCB bands."""
    observed_category = np.asarray(observed_category, dtype=int)
    issued = bands(forecast)
    n = len(observed_category)
    if n == 0:
        return {'n': 0, 'category_accuracy': None, 'macro_f1': None, 'within_one_category': None}
    scores = []
    for label in range(6):
        tp = int(((issued == label) & (observed_category == label)).sum())
        fp = int(((issued == label) & (observed_category != label)).sum())
        fn = int(((issued != label) & (observed_category == label)).sum())
        if tp + fp + fn == 0:
            continue  # a band absent from both forecast and observation says nothing
        scores.append(2 * tp / (2 * tp + fp + fn))
    return {
        'n': n,
        'category_accuracy': float((issued == observed_category).mean()),
        'macro_f1': float(np.mean(scores)) if scores else None,
        'macro_f1_bands_present': len(scores),
        'within_one_category': float((np.abs(issued - observed_category) <= 1).mean()),
    }


def exceedance(observed_category, forecast, minimum_category):
    """Detection of days at or above a category (3 = Poor or worse, 4 = Very Poor or worse)."""
    observed_category = np.asarray(observed_category, dtype=int)
    event = observed_category >= minimum_category
    warned = bands(forecast) >= minimum_category
    hits = int((event & warned).sum())
    misses = int((event & ~warned).sum())
    false_alarms = int((~event & warned).sum())
    return {
        'threshold_category': LABELS[minimum_category], 'n': int(len(event)), 'events': int(event.sum()),
        'hits': hits, 'misses': misses, 'false_alarms': false_alarms,
        'probability_of_detection': hits / (hits + misses) if hits + misses else None,
        'false_alarm_ratio': false_alarms / (hits + false_alarms) if hits + false_alarms else None,
        'critical_success_index': hits / (hits + misses + false_alarms) if hits + misses + false_alarms else None,
        'precision': hits / (hits + false_alarms) if hits + false_alarms else None,
        'recall': hits / (hits + misses) if hits + misses else None,
    }


def censored_severe(forecast):
    """How a method treats days observed in the open Severe band (true index >= 401)."""
    forecast = np.asarray(forecast, dtype=float)
    n = len(forecast)
    if n == 0:
        return {'n': 0, 'share_forecast_below_401': None, 'mean_shortfall_lower_bound': None,
                'median_forecast': None}
    shortfall = np.clip(SEVERE_FLOOR - forecast, 0, None)
    return {
        'n': n,
        'share_forecast_below_401': float((forecast < SEVERE_FLOOR).mean()),
        'share_forecast_below_very_poor': float((forecast <= 300).mean()),
        # 401 minus the forecast is the least the error can be; the true error is larger.
        'mean_shortfall_lower_bound': float(shortfall.mean()),
        'median_forecast': float(np.median(forecast)),
    }


def by_category(observed, forecast, observed_category, censored):
    """Per observed category: exact-error metrics on exact days, shortfall on censored ones."""
    observed, forecast = np.asarray(observed, dtype=float), np.asarray(forecast, dtype=float)
    observed_category = np.asarray(observed_category, dtype=int)
    censored = np.asarray(censored, dtype=bool)
    out = {}
    for index, label in enumerate(LABELS):
        exact = (observed_category == index) & ~censored
        entry = regression(observed[exact], forecast[exact])
        if entry['n']:
            entry['underprediction_rate'] = float((forecast[exact] < observed[exact]).mean())
            entry['overprediction_rate'] = float((forecast[exact] > observed[exact]).mean())
        if index == 5:
            entry['censored_days'] = censored_severe(forecast[censored & (observed_category == 5)])
        out[label] = entry
    return out


def summary(observed, forecast, observed_category, censored):
    """Everything reported for one method on one set of rows."""
    observed, forecast = _clean(observed, forecast)
    observed_category = np.asarray(observed_category, dtype=int)
    censored = np.asarray(censored, dtype=bool)
    if observed.shape != observed_category.shape or observed.shape != censored.shape:
        raise ValueError('Targets, forecasts, categories and censor flags must align.')
    if ((observed_category < 0) | (observed_category > 5)).any():
        raise ValueError('Observed category must be in 0..5.')
    if (censored & (observed_category != 5)).any():
        raise ValueError('Only Severe targets may have censored-Severe flags.')
    exact = ~censored
    out = regression(observed[exact], forecast[exact])
    out['n_exact'] = out.pop('n')
    out['n_censored_severe'] = int(censored.sum())
    out.update({k: v for k, v in categorical(observed_category, forecast).items() if k != 'n'})
    out['n_category'] = int(len(observed_category))
    out['poor_or_worse'] = exceedance(observed_category, forecast, 3)
    out['very_poor_or_worse'] = exceedance(observed_category, forecast, 4)
    out['censored_severe'] = censored_severe(forecast[censored])
    out['by_observed_category'] = by_category(observed,forecast,observed_category,censored)
    for label, entry in out['by_observed_category'].items():
        n = entry['n'] + (entry.get('censored_days') or {}).get('n',0)
        entry['descriptive_only_below_30'] = n < 30
    return out
