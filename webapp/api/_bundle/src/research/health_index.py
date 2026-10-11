"""Neutral-by-default research index. Never a clinical risk prediction."""
import math

VERSION = 'hai-v2-evidence-framework-v1'


def evidence_index(concentrations, reference_values, evidence=None):
    """Dimensionless pollutant ratios; apply only explicitly reviewed modifiers.

    Reference values must be supplied with units normalized by the caller.
    No population risk coefficient is estimated or inferred here.
    """
    if not concentrations or set(concentrations) != set(reference_values):
        raise ValueError('Matched concentration/reference support required')
    ratios = {}
    for pollutant, value in concentrations.items():
        reference = reference_values[pollutant]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Finite nonnegative normalized concentrations required')
        if not isinstance(reference, (int, float)) or not math.isfinite(reference) or reference <= 0:
            raise ValueError('Finite positive references required')
        ratios[pollutant] = value / reference
    modifier = 1.0
    if evidence is not None:
        if evidence.get('review_status') != 'HUMAN_VERIFIED' or not evidence.get('source_identifier'):
            raise ValueError('Unreviewed evidence cannot alter the neutral modifier')
        modifier = evidence.get('modifier')
        if isinstance(modifier, bool) or not isinstance(modifier, (int, float)) or not math.isfinite(modifier) or modifier <= 0:
            raise ValueError('Positive finite reviewed modifier required')
    return {'version': VERSION, 'value': max(ratios.values()) * modifier,
            'pollutant_ratios': ratios, 'modifier': modifier,
            'evidence_status': 'NEUTRAL_UNSUPPORTED' if evidence is None else 'HUMAN_VERIFIED',
            'meaning': 'Exploratory normalized exposure index; not AQI, clinical risk, or causal benefit.'}


def sensitivity(concentrations, reference_values, reviewed_evidence):
    baseline = evidence_index(concentrations, reference_values)
    variants = [evidence_index(concentrations, reference_values, item) for item in reviewed_evidence]
    return {'baseline': baseline, 'reviewed_variants': variants,
            'status': 'PENDING_REVIEWED_COEFFICIENTS' if not variants else 'EXPLORATORY'}
