"""Offline calibration primitives. No default operational interval or probability.

Software tests use artificial fixtures; they are never scientific results.
Monotonic AQI transformation does not create simultaneous pollutant coverage.
"""
from dataclasses import dataclass
from datetime import datetime
import math
from src.nationwide.aqi import calculate, valid


def concentration_bounds(lower, upper, *, ozone_lower=None, ozone_upper=None):
    if set(lower)!=set(upper) or any(not valid(lower[p]) or not valid(upper[p]) or lower[p]>upper[p] for p in lower):
        raise ValueError('Matched finite nonnegative concentration bounds required')
    lo=calculate(lower,ozone_lower);hi=calculate(upper,ozone_upper)
    if lo['aqi'] is None or hi['aqi'] is None or set(lo['sub_indices'])!=set(hi['sub_indices']):
        raise ValueError('Fixed eligible pollutant support required at both bounds')
    if hi['aqi']<lo['aqi']: raise ValueError('Inconsistent ozone averaging/hourly bounds')
    return {'lower':lo['aqi'],'upper':None if hi['qualifier']=='LOWER_BOUND' else hi['aqi'],
        'upper_lower_bound':hi['aqi'] if hi['qualifier']=='LOWER_BOUND' else None,
        'qualifier':hi['qualifier'],'methodology_version':lo['methodology_version'],
        'coverage_notice':'Requires simultaneous pollutant coverage and identical averaging/support. Marginal pollutant coverage is not joint AQI coverage.'}


def quantile_score(y, prediction, quantile):
    if not 0<quantile<1 or not math.isfinite(y) or not math.isfinite(prediction): raise ValueError('Invalid quantile score input')
    error=y-prediction
    return max(quantile*error,(quantile-1)*error)


def brier(actual, probability):
    if actual not in (0,1) or isinstance(probability,bool) or not isinstance(probability,(float,int)) or not 0<=probability<=1:
        raise ValueError('Binary outcome and probability in [0,1] required')
    return (probability-actual)**2


@dataclass
class AdaptiveConformal:
    """ACI state updated once each genuinely available outcome arrives.

    No exchangeability/time-dependent conditional-coverage guarantee. The
    clipping policy is recorded; reset/version the state when protocol changes.
    """
    target_alpha: float = .1
    gamma: float = .01
    alpha: float = .1
    last_available_at: datetime | None = None
    updates: int = 0

    def update(self, missed, available_at, now):
        if not isinstance(missed,bool) or available_at.tzinfo is None or now.tzinfo is None or available_at>now:
            raise ValueError('Only available outcomes may update ACI')
        if self.last_available_at and available_at<=self.last_available_at:
            raise ValueError('Outcome updates must be uniquely ordered by availability')
        if not 0<self.target_alpha<1 or not 0<self.gamma<1: raise ValueError('Invalid ACI settings')
        self.alpha=max(.001,min(.999,self.alpha+self.gamma*(self.target_alpha-int(missed))))
        self.last_available_at=available_at;self.updates+=1
        return self.alpha
