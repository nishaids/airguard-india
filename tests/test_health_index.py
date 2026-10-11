import pytest
from src.research.health_index import evidence_index, sensitivity


def test_no_evidence_means_neutral_and_no_clinical_claim():
    result = evidence_index({'PM2.5': 30}, {'PM2.5': 15})
    assert result['modifier'] == 1 and result['value'] == 2
    assert result['evidence_status'] == 'NEUTRAL_UNSUPPORTED'
    assert sensitivity({'PM2.5': 30}, {'PM2.5': 15}, [])['status'] == 'PENDING_REVIEWED_COEFFICIENTS'


def test_unreviewed_or_bad_units_cannot_silently_change_health_index():
    with pytest.raises(ValueError):
        evidence_index({'PM2.5': 30}, {'PM10': 15})
    with pytest.raises(ValueError):
        evidence_index({'PM2.5': 30}, {'PM2.5': 15}, {'modifier': 2})
    result = evidence_index({'PM2.5': 30}, {'PM2.5': 15},
                            {'review_status': 'HUMAN_VERIFIED', 'source_identifier': 'fixture-only', 'modifier': 1.1})
    assert result['value'] == pytest.approx(2.2)
