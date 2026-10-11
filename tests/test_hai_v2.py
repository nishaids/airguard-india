"""HAI v2 framework tests.

Every coefficient here is SYNTHETIC: a round number chosen to make the
arithmetic checkable. None of it is a published effect estimate and none of it
may be copied into config/hai_factors.yaml, which stays unadopted until a
qualified human reviews real sources.
"""
import math

import pytest

from src.features import hai_v2

SYNTHETIC = {'PM2.5': 0.001, 'PM10': 0.0005, 'NO2': 0.0008, 'O3': 0.0009}


def test_shipped_register_adopts_nothing_and_says_what_it_is_waiting_for():
    register = hai_v2.load_factors()
    assert register['status'] == 'AWAITING_EVIDENCE_REVIEW'
    assert register['adopted'] == {}
    assert register['reviewer'] is None
    assert {'PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3'} <= set(register['awaiting_review'])
    # NH3 and Pb are neutral by declaration, which is a stated position, not a gap.
    assert register['neutral'] == ['NH3', 'Pb']


def test_compute_refuses_to_produce_a_number_without_adopted_coefficients():
    result = hai_v2.compute({'PM2.5': 80}, 'elderly_60plus')
    assert result['status'] == 'PENDING_EVIDENCE_REVIEW'
    assert result['hai'] is None and result['band'] is None
    assert 'qualified human' in result['reason']


def test_every_cohort_ships_neutral_so_no_factor_is_invented():
    register = hai_v2.load_factors()
    for cohort, entry in register['cohorts'].items():
        assert all(float(f) == 1.0 for f in entry['factors'].values()), cohort
    assert register['cohorts']['healthy_adult']['reference'] is True


def test_excess_risk_sums_over_pollutants_and_reports_what_it_could_not_use():
    result = hai_v2.excess_risk({'PM2.5': 100, 'PM10': 200, 'SO2': 10, 'O3': None},
                                SYNTHETIC)
    expected = (math.exp(0.001 * 100) - 1) + (math.exp(0.0005 * 200) - 1)
    assert result['excess_risk'] == pytest.approx(expected)
    # SO2 has no coefficient and O3 has no concentration: both are named, not absorbed.
    assert result['pollutants_skipped'] == ['O3', 'SO2']
    assert result['pollutants_used'] == ['PM10', 'PM2.5']


def test_a_cohort_factor_scales_only_that_pollutant_contribution():
    plain = hai_v2.excess_risk({'PM2.5': 100}, SYNTHETIC)['excess_risk']
    doubled = hai_v2.excess_risk({'PM2.5': 100}, SYNTHETIC, {'PM2.5': 2.0})['excess_risk']
    assert doubled == pytest.approx(2 * plain)


def test_negative_or_non_finite_concentrations_are_refused_not_clamped():
    result = hai_v2.excess_risk({'PM2.5': -5, 'PM10': float('nan'), 'NO2': 'forty'}, SYNTHETIC)
    assert result['excess_risk'] == 0.0
    assert result['pollutants_skipped'] == ['NO2', 'PM10', 'PM2.5']


def test_scale_is_monotone_and_anchored_to_the_cpcb_boundaries():
    anchors = hai_v2.band_anchors(SYNTHETIC)
    assert [a['aqi'] for a in anchors] == [50, 100, 200, 300, 400]
    risks = [a['excess_risk'] for a in anchors]
    assert risks == sorted(risks)
    # Each anchor reads back as its own boundary, so a healthy adult on a CPCB
    # boundary day gets the same number from both indices.
    for anchor in anchors:
        assert hai_v2.scaled(anchor['excess_risk'], anchors) == pytest.approx(anchor['aqi'], abs=0.001)
    rising = [hai_v2.scaled(r, anchors) for r in [0, risks[0] / 2, risks[1], risks[3], risks[-1] * 3]]
    assert rising == sorted(rising)
    # Above the top anchor the scale caps at the end of the official range.
    assert rising[-1] == 500.0


def test_bands_follow_the_official_boundaries_including_the_open_top_band():
    assert [hai_v2.band_of(v) for v in (0, 50, 51, 100, 201, 301, 401)] == [
        'Good', 'Good', 'Satisfactory', 'Satisfactory', 'Poor', 'Very Poor', 'Severe']


def test_compute_with_supplied_coefficients_stays_labelled_experimental():
    result = hai_v2.compute({'PM2.5': 90, 'O3': 60}, 'children', betas=SYNTHETIC)
    assert result['status'] == 'EXPERIMENTAL_NOT_VALIDATED'
    assert result['hai'] is not None
    assert result['cohort_evidence_verified'] is False
    assert set(result['neutral_factors']) == {'PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3'}
    assert result['coefficient_source'] == 'caller-supplied'


def test_unknown_cohort_is_an_error_not_a_silent_default():
    with pytest.raises(KeyError):
        hai_v2.compute({'PM2.5': 10}, 'astronauts', betas=SYNTHETIC)


def test_monte_carlo_separates_the_aggregation_effect_from_vulnerability():
    days = [{'PM2.5': c, 'PM10': c * 1.6, 'NO2': c * 0.4, 'O3': c * 0.7} for c in range(20, 200, 10)]
    official = [c for c in range(20, 200, 10)]
    draws = [{p: b * scale for p, b in SYNTHETIC.items()} for scale in (0.8, 1.0, 1.25)]
    result = hai_v2.monte_carlo(days, draws, cohort='elderly_60plus', aqi_by_day=official)
    assert result['draws'] == 3 and result['days'] == len(days)
    assert result['aggregation_effect']['n'] == 3
    assert 0 <= result['cohort_effect']['median'] <= 1
    # Every cohort factor is 1.0, so nothing beyond aggregation can be attributed.
    assert result['vulnerability_only']['median'] == pytest.approx(0.0)


def test_monte_carlo_without_draws_is_pending_rather_than_zero():
    assert hai_v2.monte_carlo([{'PM2.5': 10}], [], aqi_by_day=[42])['status'] == 'PENDING_EVIDENCE_REVIEW'


def test_summarise_reports_a_distribution_not_a_point():
    summary = hai_v2.summarise([0.1, 0.2, 0.3, 0.4, 0.5])
    assert summary['median'] == pytest.approx(0.3)
    assert summary['min'] == 0.1 and summary['max'] == 0.5 and summary['n'] == 5


def test_register_summary_reports_unusable_until_a_coefficient_is_adopted():
    summary = hai_v2.register_summary()
    assert summary['usable'] is False
    assert summary['adopted_coefficients'] == []
    assert all(c['all_factors_neutral'] for c in summary['cohorts'].values())
    assert any('advisory heuristic' in limit for limit in summary['limits'])
