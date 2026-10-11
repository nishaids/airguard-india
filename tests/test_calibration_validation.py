import xml.etree.ElementTree as ET

import pytest

from src.research.calibration import validation


def junit(tmp_path, cases, **counts):
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite', {key: str(value) for key, value in counts.items()})
    for module, name, status in cases:
        case = ET.SubElement(suite, 'testcase', classname=module, name=name)
        if status != 'passed':
            ET.SubElement(case, status)
    path = tmp_path / 'tests.xml'
    ET.ElementTree(root).write(path)
    return path


def cpcb_cases():
    return [(module, name, 'passed') for module, name in validation.CPCB_REQUIRED_TESTS.values()]


def test_actual_successful_cpcb_cases_and_summary_counts(tmp_path):
    cases = cpcb_cases() + [('tests.other', 'test_optional', 'skipped')]
    path = junit(tmp_path, cases, tests=len(cases), failures=0, errors=0, skipped=1)
    result = validation.parse_junit(path, exit_code=0, log_text='6 passed, 1 skipped, 11 deselected in 0.5s')
    assert result['counts'] == {'tests': 7, 'collected': 7, 'passed': 6, 'failures': 0,
                                'errors': 0, 'skipped': 1, 'deselected': 11}
    assert result['suite_passed'] and result['cpcb_method_passed']
    assert not result['cpcb_missing_or_unsuccessful_groups']


@pytest.mark.parametrize('exit_code', [1, 2, 3, 4, 5, None])
def test_nonzero_or_unobserved_exit_cannot_pass_even_with_success_xml(tmp_path, exit_code):
    result = validation.parse_junit(junit(tmp_path, cpcb_cases()), exit_code=exit_code)
    assert not result['suite_passed'] and not result['cpcb_method_passed']


def test_failures_errors_skips_are_counted_and_block_cpcb_method(tmp_path):
    cases = cpcb_cases()
    cases[0] = (*cases[0][:2], 'failure')
    cases[1] = (*cases[1][:2], 'error')
    cases[2] = (*cases[2][:2], 'skipped')
    result = validation.parse_junit(junit(tmp_path, cases, tests=6, failures=1, errors=1, skipped=1), exit_code=1)
    assert result['counts']['passed'] == 3
    assert result['counts']['failures'] == result['counts']['errors'] == result['counts']['skipped'] == 1
    assert len(result['unsuccessful_tests']) == 2
    assert not result['cpcb_method_passed']


def test_no_tests_and_all_skipped_refuse_acceptance(tmp_path):
    empty = validation.parse_junit(junit(tmp_path, [], tests=0), exit_code=0)
    assert not empty['suite_passed'] and not empty['cpcb_method_passed']
    skipped = [('tests.other', 'test_disabled', 'skipped')]
    result = validation.parse_junit(junit(tmp_path, skipped, tests=1, skipped=1), exit_code=0)
    assert not result['suite_passed']


def test_unrelated_success_does_not_verify_cpcb_method(tmp_path):
    path = junit(tmp_path, [('tests.other', 'test_works', 'passed')], tests=1)
    result = validation.parse_junit(path, exit_code=0)
    assert result['suite_passed'] and not result['cpcb_method_passed']
    assert set(result['cpcb_missing_or_unsuccessful_groups']) == set(validation.CPCB_REQUIRED_TESTS)


def test_summary_mismatch_cannot_pass(tmp_path):
    path = junit(tmp_path, cpcb_cases(), tests=99, failures=0, errors=0, skipped=0)
    result = validation.parse_junit(path, exit_code=0)
    assert not result['counts_consistent'] and not result['suite_passed']


def test_nested_suite_counts_do_not_double_count(tmp_path):
    path = tmp_path / 'tests.xml'
    path.write_text('<testsuites><testsuite tests="2"><testsuite tests="1"><testcase classname="tests.a" name="one"/>'
                    '</testsuite><testsuite tests="1"><testcase classname="tests.b" name="two"/>'
                    '</testsuite></testsuite></testsuites>')
    result = validation.parse_junit(path, exit_code=0)
    assert result['counts']['tests'] == result['counts']['passed'] == 2 and result['suite_passed']


def fingerprint_tree(tmp_path):
    for name in validation.TESTED_MODULES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('source = 1\n')
    tests = tmp_path / 'tests/test_example.py'
    tests.parent.mkdir()
    tests.write_text('def test_example():\n    assert True\n')
    return tests


def test_normalization_and_source_test_fingerprints_detect_changes(tmp_path):
    test_file = fingerprint_tree(tmp_path)
    first = validation.source_fingerprint(tmp_path)
    aqi = tmp_path / 'src/nationwide/aqi.py'
    aqi.write_bytes(b'source = 1\r\n')
    assert validation.source_fingerprint(tmp_path) == first
    aqi.write_text('source = 2\n')
    second = validation.source_fingerprint(tmp_path)
    assert second['tested_module_sha256']['src/nationwide/aqi.py'] != first['tested_module_sha256']['src/nationwide/aqi.py']
    assert second['source_tree_sha256'] != first['source_tree_sha256']
    test_file.write_text('def test_example():\n    assert False\n')
    assert validation.source_fingerprint(tmp_path)['test_tree_sha256'] != second['test_tree_sha256']


def test_missing_modules_or_stale_source_evidence_cannot_validate(tmp_path):
    fingerprint_tree(tmp_path)
    report = {'validation_version': validation.VERSION, 'actual_exit_observed': True, 'exit_code': 0,
              'suite_passed': True, 'source_changed_during_run': False,
              'source_fingerprint': validation.source_fingerprint(tmp_path)}
    assert validation.evidence_matches_current(report, tmp_path)
    (tmp_path / 'src/nationwide/aqi.py').write_text('changed = True\n')
    assert not validation.evidence_matches_current(report, tmp_path)
    (tmp_path / 'src/nationwide/aqi.py').unlink()
    report['source_fingerprint'] = validation.source_fingerprint(tmp_path)
    assert not validation.evidence_matches_current(report, tmp_path)


def test_offline_environment_prevents_dotenv_from_reloading_credentials():
    original = {'DATABASE_URL': 'secret-dsn', 'PATH': 'ordinary-path', 'PYTEST_ADDOPTS': '--bad-option'}
    child = validation._offline_environment(original)
    assert all(child[name] == '' for name in validation.SECRET_NAMES)
    assert child['PYTEST_ADDOPTS'] == '' and child['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert child['AIRGUARD_OFFLINE_TEST_VALIDATION'] == '1'
    assert original['DATABASE_URL'] == 'secret-dsn'


def test_launch_failure_never_writes_test_acceptance(tmp_path, monkeypatch):
    fingerprint_tree(tmp_path)

    def unavailable(*args, **kwargs):
        raise FileNotFoundError('no interpreter')

    monkeypatch.setattr(validation.subprocess, 'run', unavailable)
    with pytest.raises(FileNotFoundError):
        validation.run(root=tmp_path)
    assert not (tmp_path / 'results/research/test_validation.json').exists()
