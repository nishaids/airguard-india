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


def warning(category, forecast):
    category, issued = np.asarray(category), bands(forecast)
    high = category >= 3
    return {'n':len(category), 'under_warning':float(np.mean(issued<category)) if len(category) else None,
            'over_warning':float(np.mean(issued>category)) if len(category) else None,
            'serious_under_warning':float(np.mean(issued<category-1)) if len(category) else None,
            'high_pollution_under_warning':float(np.mean(issued[high]<category[high])) if high.any() else None,
            'mean_warning_distance':float(np.mean(issued-category)) if len(category) else None}


def select_risk_quantile(category, predictions, target):
    n = len(category)
    if not n:
        return None
    for quantile, pred in sorted(predictions.items()):
        risk = (int((bands(pred)<np.asarray(category)).sum())+1)/(n+1)
        if risk <= target:
            return quantile
    return None  # never claim a risk-controlled choice when no candidate qualifies
