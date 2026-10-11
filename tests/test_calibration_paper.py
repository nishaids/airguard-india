"""Evidence binding and bibliography safety for the unsubmitted IEEE skeleton."""
import copy
import json
import re
import pytest
from src.research.calibration import paper


def artifacts():
    experiment = {'dataset_hash': 'a'*64, 'data_version': 'experiment-inputs',
                  'usable_stations': 59, 'usable_cities': 41, 'valid_targets': 22830,
                  'rejected_targets': 12000, 'severe_days': 229}
    acquisition = {**experiment, 'dataset_hash': 'b'*64, 'data_version': 'acquisition-inputs',
                   'usable_stations': 68, 'usable_cities': 46, 'valid_targets': 26778,
                   'rejected_targets': 13750, 'severe_days': 322}
    result = {'dataset_hash': experiment['dataset_hash'], 'data_version': experiment['data_version'],
              'run_id': 'c'*64, 'final_test_range': ['2026-07-10', '2026-10-07'],
              'final_test_scored': False, 'folds': [{'strict': {'ridge_strict': {'mae': 10}}},
                                                 {'status': 'INSUFFICIENT_DATA'}],
              'spatial': [{'ridge_strict': {'mae': 12}}, {'status': 'INSUFFICIENT_DATA'}],
              'uncertainty': {'fold_01': {}},
              'paired_comparisons': {'ridge_strict_vs_climatology':
                                    {'n': 100, 'mae_difference': -2., 'ci95': [-4., 1.]}}}
    prospect = {'forecasts': 12, 'issued_target_days': 1, 'verified_days': 0,
                'station_bound_forecasts': 0, 'historical_forecasts_missing_git_sha': 12,
                'correction_deployed': False}
    protocol = {'study_window': {'first_date': '2025-02-19', 'last_date': '2026-10-07'},
                '_locked_at': '2026-10-11T18:32:05+00:00', 'splits': {'final_test_days': 90}}
    selection = {'universe': {'eligible_stations': 481, 'eligible_cities': 256},
                 'selected': {'stations': 181, 'cities': 101}}
    return acquisition, result, prospect, experiment, protocol, selection


def test_dataset_counts_bind_to_the_exact_experiment(tmp_path, monkeypatch):
    current, result, _, experiment, _, _ = artifacts()
    monkeypatch.setattr(paper.config, 'PROJECT_ROOT', tmp_path)
    folder = tmp_path/'data/research/derived'/result['data_version']/'builder-hash'
    folder.mkdir(parents=True)
    (folder/'quality_report.json').write_text(json.dumps(experiment))
    recovered = paper.find_experiment_quality(result, current)
    assert recovered == experiment
    evidence = paper.dataset_evidence(current, recovered, result)
    assert not evidence['datasets_identical']
    assert evidence['acquisition_minus_experiment_counts']['usable_stations'] == 9
    assert evidence['experiment_input_counts']['valid_targets'] == 22830
    assert evidence['acquisition_counts']['valid_targets'] == 26778
    with pytest.raises(ValueError, match='do not substitute'):
        paper.find_experiment_quality({**result, 'dataset_hash': 'd'*64}, current)
    with pytest.raises(ValueError, match='do not match'):
        paper.dataset_evidence(current, current, result)


@pytest.mark.parametrize('delta,interval,relation,conclusion', [
    (-2., [-4., -1.], 'lower paired MAE', 'lower MAE supported'),
    (2., [1., 4.], 'higher paired MAE', 'higher MAE supported'),
    (-2., [-4., 1.], 'lower paired MAE', 'not established'),
    (0., [-1., 1.], 'the same paired MAE', 'not established'),
])
def test_claim_direction_and_uncertainty_come_from_artifact(delta, interval, relation, conclusion):
    result = {'paired_comparisons': {'ridge_strict_vs_climatology':
                                   {'n': 37, 'mae_difference': delta, 'ci95': interval}}}
    text = paper.comparison_findings(result)
    assert relation in text and conclusion in text
    assert f'{delta:+.2f}' in text and 'n=37 exact pairs' in text
    assert 'History Ridge versus persistence: paired evidence unavailable' in text


def test_bibliography_preserves_metadata_links_and_existing_escapes():
    text = r'''@techreport{cpcb2014aqi,
      author={{CPCB & Board}}, title={AQI \& uncertainty_100% #1 $2},
      institution={Institute & Council}, howpublished={Public report}, year=2014,
      volume={2}, number={3}, pages={10--20},
      doi={10.1234/air_quality}, url={https://example.org/air_quality?x=1&y=2},
      note={Online: https://example.org/technical_report}
    }
    @misc{xu2021enbpi, author="Chen Xu and Yao Xie", title={Conformal prediction},
      year={2020}, eprint={2010.09107}, archivePrefix={arXiv}}
    '''
    rendered = paper.bib_entries(text)
    assert r'CPCB \& Board' in rendered
    assert r'AQI \& uncertainty\_100\% \#1 \$2' in rendered
    assert r'\\&' not in rendered
    assert r'Institute \& Council' in rendered and 'Public report' in rendered
    assert 'vol. 2, no. 3, pp. 10--20' in rendered
    assert r'\url{https://doi.org/10.1234/air_quality}' in rendered
    assert r'\url{https://example.org/air_quality?x=1&y=2}' in rendered
    assert r'Online: \url{https://example.org/technical_report}' in rendered
    assert r'arXiv: \url{https://arxiv.org/abs/2010.09107}' in rendered
    assert ', ,' not in rendered


def test_render_uses_distinct_counts_completed_evaluations_and_verified_source():
    values = artifacts()
    source = paper.render_source(*values, references='')
    assert '68 usable stations, 46 cities, 26778 valid targets' in source
    assert 'with 59 usable stations, 41 cities, 22830 valid targets' in source
    assert 'acquisition and experiment datasets differ' in source
    assert '+9 usable stations, +5 cities' in source
    assert 'completed 1 temporal evaluations' in source
    assert '1 spatial holdouts and 1 calibration-window evaluations' in source
    assert '1 temporal and 1 spatial entries lacked sufficient data' in source
    assert r'\url{https://open-meteo.com/en/docs/previous-runs-api}' in source
    assert 'the manuscript itself is not a new' in source
    assert 'operational pollutant-support policy' in source
    assert 'pending archive integration' in source
    assert '0 forecasts have a bound station; 12 do not' in source
    assert not re.search(r'@[A-Z_]+@', source)


def test_missing_final_status_is_not_fabricated():
    values = list(artifacts())
    values[1] = copy.deepcopy(values[1])
    del values[1]['final_test_scored']
    source = paper.render_source(*values, references='')
    assert 'Final-test scoring status is unavailable' in source
    assert 'no final-test scoring was performed' not in source


def test_generate_refuses_an_inconsistent_latest_pointer_before_writing(tmp_path, monkeypatch):
    out = tmp_path/'results/research'
    out.mkdir(parents=True)
    monkeypatch.setattr(paper.config, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(paper, 'OUT', out)
    (out/'measured_dataset.json').write_text('{}')
    exact = {'run_id': 'frozen', 'artifact': 'results/research/exact.json'}
    (out/'exact.json').write_text(json.dumps(exact))
    (out/'preliminary_latest.json').write_text(json.dumps({**exact, 'run_id': 'different'}))
    with pytest.raises(ValueError, match='immutable result artifact'):
        paper.generate()
    assert not (tmp_path/'paper/station_calibration_skeleton.tex').exists()
