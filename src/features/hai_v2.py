"""HAI v2: an AQHI-style cohort index whose coefficients come from evidence.

HAI v1 multiplied CPCB sub-indices by hand-chosen vulnerability factors, so its
headline divergence from the official AQI followed from the choice of factors
rather than from anything measured (limitations L24 and L25). v2 replaces that
with excess risk summed over pollutants,

    ER = sum_p ( exp(beta_p * C_p) - 1 )

with beta_p a published short-term concentration-response coefficient, and a
scale pinned to the CPCB band boundaries for a healthy adult so the aggregation
change alone cannot manufacture a difference from the official index.

The arithmetic is here; the coefficients are not. `config/hai_factors.yaml`
ships with every beta unadopted, because choosing a coefficient means judging
its exposure window, population and units against this use, and that is a
qualified human's call (HUMAN_ACTIONS.md, "Health factors"). Until then
`compute` returns PENDING and refuses to produce a number, and the Monte Carlo
harness runs only on coefficients a caller supplies explicitly — which is how
the tests exercise it, with values labelled synthetic.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src import config
from src.nationwide.aqi import BREAKPOINTS

FACTORS_PATH = config.PROJECT_ROOT / 'config/hai_factors.yaml'
# CPCB publishes one upper concentration per band, in this order, for each pollutant.
BOUNDARY_POSITION = {50: 0, 100: 1, 200: 2, 300: 3, 400: 4}
PENDING_REASON = ('No concentration-response coefficient has been adopted. A qualified human must '
                  'verify each source, its exposure window, its population and its units before '
                  'HAI v2 produces a value.')


def load_factors(path=None):
    """Read the coefficient register. Unverified entries stay unusable."""
    text = Path(path or FACTORS_PATH).read_text(encoding='utf-8')
    register = yaml.safe_load(text)
    register['adopted'] = {
        pollutant: entry['value']
        for pollutant, entry in (register.get('coefficients') or {}).items()
        if entry.get('verified') and entry.get('value') is not None and not entry.get('neutral')
    }
    register['neutral'] = sorted(
        pollutant for pollutant, entry in (register.get('coefficients') or {}).items()
        if entry.get('neutral'))
    register['awaiting_review'] = sorted(
        pollutant for pollutant, entry in (register.get('coefficients') or {}).items()
        if not entry.get('verified'))
    return register


def excess_risk(concentrations, betas, factors=None):
    """Summed excess risk. A pollutant without a coefficient contributes nothing.

    Contributing nothing is the honest treatment of a missing coefficient: it
    cannot be filled in from a different pollutant, and a zero contribution is
    visible in `pollutants_used` rather than hidden inside a total.
    """
    total, used, skipped = 0.0, [], []
    for pollutant, concentration in (concentrations or {}).items():
        beta = (betas or {}).get(pollutant)
        if beta is None or concentration is None:
            skipped.append(pollutant)
            continue
        try:
            value = float(concentration)
        except (TypeError, ValueError):
            skipped.append(pollutant)
            continue
        if value < 0 or not math.isfinite(value):
            skipped.append(pollutant)
            continue
        modifier = float((factors or {}).get(pollutant, 1.0))
        total += modifier * (math.exp(float(beta) * value) - 1.0)
        used.append(pollutant)
    return {'excess_risk': total, 'pollutants_used': sorted(used), 'pollutants_skipped': sorted(skipped)}


def band_anchors(betas, boundaries=(50, 100, 200, 300, 400)):
    """Excess risk of a healthy adult at each CPCB band boundary.

    A boundary is represented by the concentration vector in which every
    pollutant sits exactly at that boundary's own breakpoint, which is the only
    reading of "this day is a 100" that does not privilege one pollutant.
    """
    anchors = []
    for boundary in boundaries:
        position = BOUNDARY_POSITION.get(boundary)
        if position is None:
            continue
        concentrations = {pollutant: bands[position] for pollutant, bands in BREAKPOINTS.items()
                          if len(bands) > position}
        anchors.append({'aqi': boundary, 'concentrations': concentrations,
                        'excess_risk': excess_risk(concentrations, betas)['excess_risk']})
    return anchors


def scaled(value, anchors, ceiling=500.0):
    """Map excess risk onto the CPCB 0-500 scale, piecewise linear between anchors.

    Reporting on the official scale rather than an invented 0-100 one is what
    makes "this cohort reads 240 where the AQI reads 180" a sentence anyone can
    check, and it is what the index comparison in WP4 needs.

    Monotone by construction: the anchors are non-decreasing in excess risk, so
    a higher excess risk can never read as a lower index.
    """
    if not anchors:
        return None
    points = [(0.0, 0.0)] + [(a['excess_risk'], float(a['aqi'])) for a in anchors]
    points.sort()
    if value <= points[0][0]:
        return 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            if x1 == x0:
                return min(ceiling, y1)
            return min(ceiling, y0 + (value - x0) * (y1 - y0) / (x1 - x0))
    # Above the top anchor the scale is capped and the reading is a lower bound,
    # exactly as the CPCB treats the open-ended Severe band.
    return ceiling


def band_of(index):
    """CPCB-aligned band label for a scaled index value."""
    if index is None:
        return None
    for limit, label in ((50, 'Good'), (100, 'Satisfactory'), (200, 'Moderate'),
                         (300, 'Poor'), (400, 'Very Poor')):
        if index <= limit:
            return label
    return 'Severe'


def compute(concentrations, cohort='healthy_adult', register=None, betas=None):
    """HAI v2 for one day and one cohort, or an explicit PENDING."""
    register = register or load_factors()
    coefficients = betas if betas is not None else register.get('adopted') or {}
    cohorts = register.get('cohorts') or {}
    if cohort not in cohorts:
        raise KeyError(f'unknown cohort {cohort!r}; expected one of {sorted(cohorts)}')
    if not coefficients:
        return {'status': 'PENDING_EVIDENCE_REVIEW', 'hai': None, 'band': None, 'cohort': cohort,
                'reason': PENDING_REASON, 'awaiting_review': register.get('awaiting_review'),
                'register_status': register.get('status')}
    factors = (cohorts[cohort].get('factors') or {})
    neutral = sorted(p for p, f in factors.items() if float(f) == 1.0)
    risk = excess_risk(concentrations, coefficients, factors)
    anchors = band_anchors(coefficients)
    index = scaled(risk['excess_risk'], anchors)
    return {
        'status': 'EXPERIMENTAL_NOT_VALIDATED', 'cohort': cohort, 'hai': None if index is None else round(index, 1),
        'band': band_of(index), 'excess_risk': risk['excess_risk'],
        'pollutants_used': risk['pollutants_used'], 'pollutants_skipped': risk['pollutants_skipped'],
        'neutral_factors': neutral, 'cohort_evidence_verified': bool(cohorts[cohort].get('verified')),
        'coefficient_source': 'caller-supplied' if betas is not None else 'config/hai_factors.yaml',
        'limits': register.get('limits'),
    }


def monte_carlo(concentrations_by_day, draws, cohort='healthy_adult', register=None, aqi_by_day=None):
    """Sensitivity of "this cohort's band differs from the AQI" to the coefficients.

    `draws` is a list of coefficient dictionaries sampled from the published
    confidence intervals by the caller, which keeps the sampling distribution a
    reviewed decision rather than an assumption buried in here. This replaces
    HAI v1's single 66.9% headline (L25) with a distribution, and separates the
    aggregation effect — what the reference cohort alone produces — from the
    vulnerability effect.
    """
    register = register or load_factors()
    if not draws:
        return {'status': 'PENDING_EVIDENCE_REVIEW', 'reason': PENDING_REASON, 'draws': 0}
    days = list(concentrations_by_day or [])
    reference_share, cohort_share = [], []
    for betas in draws:
        differing_reference = differing_cohort = comparable = 0
        for index, concentrations in enumerate(days):
            official = (aqi_by_day or [None] * len(days))[index]
            if official is None:
                continue
            comparable += 1
            official_band = band_of(official)
            reference = compute(concentrations, 'healthy_adult', register, betas)
            subject = compute(concentrations, cohort, register, betas)
            differing_reference += reference['band'] != official_band
            differing_cohort += subject['band'] != official_band
        if not comparable:
            continue
        reference_share.append(differing_reference / comparable)
        cohort_share.append(differing_cohort / comparable)
    if not cohort_share:
        return {'status': 'INSUFFICIENT_COMPARABLE_DAYS', 'draws': len(draws), 'days': len(days)}
    return {
        'status': 'EXPERIMENTAL_NOT_VALIDATED', 'cohort': cohort, 'draws': len(draws), 'days': len(days),
        'aggregation_effect': summarise(reference_share),
        'cohort_effect': summarise(cohort_share),
        'vulnerability_only': summarise([c - r for c, r in zip(cohort_share, reference_share)]),
        'notice': 'The aggregation effect is what changing the index form alone produces. Only the '
                  'remainder can be attributed to cohort vulnerability.',
    }


def summarise(values):
    """Median and 95% interval of a sample, reported as a distribution."""
    ordered = sorted(values)
    if not ordered:
        return None

    def quantile(q):
        position = q * (len(ordered) - 1)
        low = int(math.floor(position))
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {'median': quantile(0.5), 'p2_5': quantile(0.025), 'p97_5': quantile(0.975),
            'min': ordered[0], 'max': ordered[-1], 'n': len(ordered)}


def register_summary(register=None):
    """What the register currently permits, for the status page and the paper."""
    register = register or load_factors()
    cohorts = register.get('cohorts') or {}
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'schema_version': register.get('schema_version'),
        'status': register.get('status'),
        'reviewer': register.get('reviewer'),
        'adopted_coefficients': sorted(register.get('adopted') or {}),
        'neutral_by_declaration': register.get('neutral'),
        'awaiting_review': register.get('awaiting_review'),
        'cohorts': {name: {'reference': bool(entry.get('reference')),
                           'verified': bool(entry.get('verified')),
                           'all_factors_neutral': all(float(f) == 1.0 for f in (entry.get('factors') or {}).values())}
                    for name, entry in cohorts.items()},
        'usable': bool(register.get('adopted')),
        'limits': register.get('limits'),
    }
