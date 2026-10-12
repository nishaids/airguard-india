"""Pure, testable operational-field conversions; no provider or target access.

Interpolate same-run native fields to IST hourly starts FIRST, then compute
moist-air density at the lowest model level. Never extrapolate outside an
acquired lead cube or substitute 2m temperature/reanalysis for level-137 data.
"""
import numpy as np


def interpolate(leads, values, requested):
    leads=np.asarray(leads,dtype=float); values=np.asarray(values,dtype=float)
    requested=np.asarray(requested,dtype=float)
    if leads.ndim!=1 or len(leads)<2 or values.ndim!=2 or values.shape[0]!=len(leads):
        raise ValueError('Expected lead-by-station operational fields')
    if not all(np.isfinite(a).all() for a in (leads,values,requested)) or not (np.diff(leads)>0).all():
        raise ValueError('Native leads/values must be finite and strictly chronological')
    if (requested<leads[0]).any() or (requested>leads[-1]).any():
        raise ValueError('No extrapolation outside acquired operational forecast leads')
    return np.stack([np.interp(requested,leads,values[:,i]) for i in range(values.shape[1])],axis=1)


def lowest_level_pressure(surface_pressure, hybrid_coefficients):
    coefficients=np.asarray(hybrid_coefficients,dtype=float)
    sp=np.asarray(surface_pressure,dtype=float)
    if coefficients.shape!=(276,) or not np.isfinite(coefficients).all() or not np.isfinite(sp).all() or (sp<=0).any():
        raise ValueError('137-level hybrid coefficients and positive same-run surface pressure required')
    a,b=coefficients[:138],coefficients[138:]
    top=a[136]+b[136]*sp; bottom=a[137]+b[137]*sp
    if not np.allclose(bottom,sp,rtol=1e-6) or (top<=0).any() or (top>=bottom).any():
        raise ValueError('Hybrid coefficients do not describe the lowest atmospheric layer')
    return .5*(top+bottom)


def mass_concentration(mixing_ratio, temperature, specific_humidity, pressure, *, co=False):
    arrays=[np.asarray(x,dtype=float) for x in (mixing_ratio,temperature,specific_humidity,pressure)]
    r,t,q,p=arrays
    if len({a.shape for a in arrays})!=1 or not all(np.isfinite(a).all() for a in arrays):
        raise ValueError('Gas conversion fields must share a finite coordinate/time shape')
    if (r<0).any() or (t<=0).any() or (p<=0).any() or (q<0).any() or (q>=1).any():
        raise ValueError('Invalid mass mixing ratio or thermodynamic state')
    density=p/(287.05*t*(1+.6078*q))
    return r*density*(1e6 if co else 1e9)
