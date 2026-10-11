"""Date-block paired comparisons and calibration using pre-test data only."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from scipy.stats import norm
from src.research.calibration.metrics import bands


def finite_quantile(scores, coverage):
    scores = np.asarray(scores, dtype=float)
    scores = scores[np.isfinite(scores)]
    if not len(scores):
        return None
    rank = int(math.ceil((len(scores) + 1) * coverage))
    if rank > len(scores):
        return None  # finite interval cannot establish the requested level
    return float(np.sort(scores)[rank - 1])


def paired(frame, first, second, repetitions=5000, block=7, seed=42):
    """Negative differential favours first; keep spatial pairs inside each date."""
    exact = frame[~frame.censored].copy()
    exact['loss'] = abs(exact[first]-exact.y_aqi)-abs(exact[second]-exact.y_aqi)
    calendar = pd.date_range(exact.target_date.min(), exact.target_date.max(), freq='D') if len(exact) else []
    daily = exact.groupby(pd.to_datetime(exact.target_date)).loss.agg(['sum','count']).reindex(calendar, fill_value=0)
    if len(daily) < block * 2:
        return {'n': len(exact), 'status': 'INSUFFICIENT_DATES'}
    values, counts = daily['sum'].to_numpy(), daily['count'].to_numpy()
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(repetitions):
        starts = rng.integers(0, len(values)-block+1, size=math.ceil(len(values)/block))
        indices = np.concatenate([np.arange(start,start+block) for start in starts])[:len(values)]
        if counts[indices].sum():
            estimates.append(float(values[indices].sum()/counts[indices].sum()))
    d = (daily['sum']/daily['count'].replace(0,np.nan)).dropna().to_numpy()
    centered = d-d.mean()
    variance = np.dot(centered,centered)/len(d)
    for lag in range(1, min(block,len(d))):
        variance += 2*(1-lag/block)*np.dot(centered[lag:],centered[:-lag])/len(d)
    variance /= len(d)
    dm = float(d.mean()/np.sqrt(variance)) if variance > 0 else None
    baseline = float(abs(exact[second]-exact.y_aqi).mean())
    delta = float(exact.loss.mean())
    return {'n':len(exact),'dates':len(d),'mae_difference':delta,
            'relative_mae_change':delta/baseline if baseline else None,
            'ci95':np.quantile(estimates,[.025,.975]).tolist(),
            'dm_statistic':dm,'dm_pvalue':float(2*norm.sf(abs(dm))) if dm is not None else None,
            'dm_note':'Daily mean loss; Newey-West lag 6; gaps omitted from DM only',
            'bootstrap':'moving seven-calendar-day blocks; sum/count weighting preserves station pairs',
            'resamples':repetitions}


def holm(results):
    available = [(key,r['dm_pvalue']) for key,r in results.items() if r.get('dm_pvalue') is not None]
    available.sort(key=lambda item:item[1])
    previous = 0.
    for index,(key,p) in enumerate(available):
        previous = max(previous,min(1.,(len(available)-index)*p))
        results[key]['holm_pvalue'] = previous
    return results


def advisory_pairs(category, forecast):
    category, forecast = np.asarray(category), np.asarray(forecast,dtype=float)
    if category.shape != forecast.shape or category.ndim != 1:
        raise ValueError('Advisory categories and forecasts must be aligned vectors')
    if not np.isfinite(forecast).all() or not np.isfinite(category).all():
        raise ValueError('Advisory pairs must be finite')
    if ((category<0)|(category>5)|(category!=category.astype(int))).any():
        raise ValueError('Advisory categories must be integers in 0..5')
    return category,forecast


def warning(category, forecast):
    category, forecast = advisory_pairs(category,forecast)
    issued = bands(forecast)
    high = category >= 3
    return {'n':len(category), 'under_warning':float(np.mean(issued<category)) if len(category) else None,
            'over_warning':float(np.mean(issued>category)) if len(category) else None,
            'serious_under_warning':float(np.mean(issued<category-1)) if len(category) else None,
            'high_pollution_under_warning':float(np.mean(issued[high]<category[high])) if high.any() else None,
            'mean_warning_distance':float(np.mean(issued-category)) if len(category) else None}


def warning_with_intervals(frame, forecast, repetitions=5000):
    result = warning(frame.y_category, forecast)
    observed, issued = frame.y_category.to_numpy(), bands(forecast)
    losses = pd.DataFrame({'date': pd.to_datetime(frame.target_date),
                           'under_warning': (issued < observed).astype(float),
                           'over_warning': (issued > observed).astype(float)})
    days = pd.date_range(losses.date.min(), losses.date.max())
    summed = losses.groupby('date')[['under_warning', 'over_warning']].sum().reindex(days, fill_value=0)
    counts = losses.groupby('date').size().reindex(days, fill_value=0).to_numpy()
    if len(days) >= 7:
        rng = np.random.default_rng(42)
        starts = rng.integers(0, len(days)-7+1, size=(repetitions, math.ceil(len(days)/7)))
        indices = (starts[:, :, None] + np.arange(7)).reshape(repetitions, -1)[:, :len(days)]
        denominator = counts[indices].sum(axis=1)
        for field in ('under_warning', 'over_warning'):
            numerator = summed[field].to_numpy()[indices].sum(axis=1)
            estimates = numerator[denominator > 0] / denominator[denominator > 0]
            result[field + '_ci95_date_block'] = np.quantile(estimates, [.025, .975]).tolist()
    return result


def select_risk_quantile(category, predictions, target):
    n = len(category)
    if not n:
        return None
    for quantile, pred in sorted(predictions.items()):
        category, pred = advisory_pairs(category,pred)
        risk = (int((bands(pred)<np.asarray(category)).sum())+1)/(n+1)
        if risk <= target:
            return quantile
    return None  # never claim a risk-controlled choice when no candidate qualifies
