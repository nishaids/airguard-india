"""Produce validation evidence from an actual, offline pytest subprocess exit.

JUnit and console logs use unique ignored ``.log`` paths. No successful test
report is inferred from files being present, and source changes invalidate the
evidence. Importing this module never launches tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.ingestion.settings import SECRET_NAMES, redact
from src.research.calibration.checkpoint import canonical_hash, write_json

VERSION = 'research-offline-test-validation-v1'
NORMALIZATION = 'UTF-8 text; CRLF and CR normalized to LF; no other changes'
TESTED_MODULES = (
    'src/nationwide/aqi.py', 'src/nationwide/providers.py', 'src/nationwide/store.py',
    'src/research/storage.py', 'src/research/calibration/availability.py',
    'src/research/calibration/data.py', 'src/research/calibration/measured.py',
    'src/research/calibration/preliminary.py', 'src/research/calibration/statistics.py',
    'src/research/calibration/splits.py', 'src/research/calibration/primary.py',
    'src/research/calibration/checkpoint.py', 'src/research/calibration/repair_archive.py',
    'src/research/calibration/openaq_archive.py', 'src/research/calibration/model_archives.py',
    'src/research/calibration/protocol.py', 'src/research/calibration/dataset.py',
    'src/research/calibration/validation.py',
    'src/research/calibration/cams_acquisition.py', 'src/research/calibration/cams_baseline.py',
    'src/research/calibration/cams_physics.py', 'src/research/calibration/primary_dataset.py',
    'src/research/calibration/operational_features.py',
)
CPCB_REQUIRED_TESTS = {
    'closed_breakpoints': ('tests.test_nationwide', 'test_all_closed_breakpoints'),
    'interpolation_and_minimum': ('tests.test_nationwide', 'test_official_interpolation_and_minimum'),
    'units': ('tests.test_nationwide', 'test_units_no_assumed_gas_conversion'),
    'hourly_coverage_and_gas_windows': ('tests.test_nationwide', 'test_averaging_minimum_unique_bins_and_gas_windows'),
    'target_timezone': ('tests.test_nationwide', 'test_ist_tomorrow_boundaries'),
    'censored_severe': ('tests.test_calibration_checkpoint', 'test_severe_not_a_numeric_regression_target'),
}
_SOCKET_ORIGINALS = None


def normalized_text_sha256(path):
    text = Path(path).read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def source_fingerprint(root=None):
    """The source/test identity readiness must compare with stored evidence."""
    root = Path(root) if root is not None else config.PROJECT_ROOT
    modules = {name: normalized_text_sha256(root / name) if (root / name).is_file() else None
               for name in TESTED_MODULES}
    source_tree = {path.relative_to(root).as_posix(): normalized_text_sha256(path)
                   for path in sorted((root / 'src').rglob('*.py')) if path.is_file()}
    tests = {path.relative_to(root).as_posix(): normalized_text_sha256(path)
             for path in sorted((root / 'tests').rglob('test_*.py')) if path.is_file()}
    return {'normalization': NORMALIZATION, 'tested_module_sha256': modules,
            'missing_tested_modules': [name for name, digest in modules.items() if digest is None],
            'source_tree_scope': 'src/**/*.py', 'source_tree_sha256': canonical_hash(source_tree),
            'source_file_count': len(source_tree), 'test_file_sha256': tests,
            'test_tree_sha256': canonical_hash(tests)}


def _integer_attribute(suite, name, fallback):
    value = suite.get(name)
    if value is None:
        return fallback
    number = int(value)
    if number < 0:
        raise ValueError('Negative JUnit summary count')
    return number


def _matches_case(case, module, name):
    classname = case.get('classname', '')
    filename = case.get('file', '').replace('\\', '/')
    base_name = case.get('name', '').split('[', 1)[0]
    return base_name == name and (classname == module or classname.startswith(module + '.') or
                                  filename.endswith(module.replace('.', '/') + '.py'))


def parse_junit(path, *, exit_code, log_text=''):
    """Parse counts and observed outcomes; refuse empty or inconsistent evidence."""
    root = ET.parse(path).getroot()
    if root.tag not in ('testsuite', 'testsuites'):
        raise ValueError('Unsupported JUnit root')
    suites = [suite for suite in root.iter('testsuite') if not list(suite.iter('testsuite'))[1:]]
    if not suites:
        raise ValueError('JUnit contains no test suite')
    cases = list(root.iter('testcase'))
    observed = {'passed': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
    statuses = []
    for case in cases:
        status = ('errors' if case.find('error') is not None else
                  'failures' if case.find('failure') is not None else
                  'skipped' if case.find('skipped') is not None else 'passed')
        observed[status] += 1
        statuses.append(status)
    declared = {}
    for name, fallback in (('tests', len(cases)), ('failures', observed['failures']),
                           ('errors', observed['errors']), ('skipped', observed['skipped'])):
        values = []
        for suite in suites:
            its_cases = list(suite.iter('testcase'))
            its_count = len(its_cases) if name == 'tests' else sum(
                case.find({'failures': 'failure', 'errors': 'error', 'skipped': 'skipped'}[name]) is not None
                for case in its_cases)
            values.append(_integer_attribute(suite, name, its_count))
        declared[name] = sum(values)
    consistent = declared['tests'] == len(cases) and all(
        declared[name] == observed[name] for name in ('failures', 'errors', 'skipped'))
    matches = re.findall(r'\b(\d+) deselected\b', log_text)
    counts = {**declared, 'collected': len(cases), 'passed': observed['passed'],
              'deselected': int(matches[-1]) if matches else None}
    suite_passed = (exit_code == 0 and consistent and declared['tests'] > 0 and observed['passed'] > 0
                    and declared['failures'] == 0 and declared['errors'] == 0)
    groups = {}
    for group, (module, name) in CPCB_REQUIRED_TESTS.items():
        selected = [(case, status) for case, status in zip(cases, statuses) if _matches_case(case, module, name)]
        groups[group] = {'collected': len(selected), 'passed': sum(status == 'passed' for _, status in selected),
                         'failures': sum(status == 'failures' for _, status in selected),
                         'errors': sum(status == 'errors' for _, status in selected),
                         'skipped': sum(status == 'skipped' for _, status in selected)}
    missing = [group for group, value in groups.items() if not value['collected'] or
               value['passed'] != value['collected']]
    return {'counts': counts, 'counts_consistent': consistent, 'suite_passed': suite_passed,
            'cpcb_method_passed': suite_passed and not missing,
            'cpcb_test_groups': groups, 'cpcb_missing_or_unsuccessful_groups': missing,
            'unsuccessful_tests': [{'node_id': redact(case.get('classname', '') + '::' + case.get('name', '')),
                                    'status': status}
                                   for case, status in zip(cases, statuses) if status in ('failures', 'errors')]}


def evidence_matches_current(report, root=None):
    """A passing stale artifact cannot establish current-source validation."""
    return (report.get('validation_version') == VERSION and report.get('actual_exit_observed') is True and
            report.get('exit_code') == 0 and report.get('suite_passed') is True and
            report.get('source_changed_during_run') is False and
            report.get('source_fingerprint') == source_fingerprint(root) and
            not report.get('source_fingerprint', {}).get('missing_tested_modules', ['unknown']))


def _offline_environment(environment=None):
    child = dict(os.environ if environment is None else environment)
    # Empty values are intentional: load_env only fills ABSENT keys, so real
    # local .env credentials cannot re-enable integration tests in the child.
    child.update({name: '' for name in SECRET_NAMES})
    child.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTEST_ADDOPTS='',
                 AIRGUARD_OFFLINE_TEST_VALIDATION='1')
    return child


def pytest_sessionstart(session):
    """Explicit offline subprocess plugin; ordinary imports leave sockets alone."""
    global _SOCKET_ORIGINALS
    if os.environ.get('AIRGUARD_OFFLINE_TEST_VALIDATION') != '1':
        return
    _SOCKET_ORIGINALS = (socket.socket.connect, socket.socket.connect_ex)

    def blocked(*args, **kwargs):
        raise RuntimeError('Offline research validation forbids socket connections')

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


def pytest_sessionfinish(session, exitstatus):
    global _SOCKET_ORIGINALS
    if _SOCKET_ORIGINALS is not None:
        socket.socket.connect, socket.socket.connect_ex = _SOCKET_ORIGINALS
        _SOCKET_ORIGINALS = None


def run(*, root=None, snapshot=False):
    """Run the full offline suite and publish evidence only after actual exit."""
    root = Path(root) if root is not None else config.PROJECT_ROOT
    started = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12]
    logs = root / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    junit = logs / f'research_validation_{run_id}.junit.xml.log'
    console = logs / f'research_validation_{run_id}.pytest.log'
    command = [sys.executable, '-m', 'pytest', 'tests', '-q', '-k', 'not real_database',
               '-p', 'src.research.calibration.validation', f'--junitxml={junit.relative_to(root).as_posix()}']
    before = source_fingerprint(root)
    # If launch is interrupted or fails, no new acceptance report is written.
    completed = subprocess.run(command, cwd=root, env=_offline_environment(),
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
    ended = datetime.now(timezone.utc).isoformat()
    output = redact(completed.stdout + '\n' + completed.stderr)
    console.write_text(output, encoding='utf-8')
    try:
        parsed = parse_junit(junit, exit_code=completed.returncode, log_text=output)
        # Redact any diagnostic strings in the ignored JUnit artifact using an
        # XML serializer, so redaction markers cannot invalidate XML syntax.
        tree = ET.parse(junit)
        for item in tree.iter():
            item.attrib.update({key: redact(value) for key, value in item.attrib.items()})
            item.text = redact(item.text) if item.text else item.text
            item.tail = redact(item.tail) if item.tail else item.tail
        tree.write(junit, encoding='utf-8', xml_declaration=True)
    except (OSError, ET.ParseError, ValueError, TypeError) as error:
        parsed = {'counts': None, 'suite_passed': False, 'cpcb_method_passed': False,
                  'junit_error_type': type(error).__name__}
    after = source_fingerprint(root)
    changed = before != after
    result = {**parsed, 'validation_version': VERSION, 'run_id': run_id,
              'started_at': started, 'completed_at': ended, 'generated_at': ended,
              'command': ['python',*command[1:]], 'interpreter_version':sys.version.split()[0],
              'working_directory': '.', 'actual_exit_observed': True,
              'exit_code': completed.returncode, 'source_fingerprint': before,
              'source_changed_during_run': changed,
              'suite_passed': parsed['suite_passed'] and not changed and not before['missing_tested_modules'],
              'cpcb_method_passed': parsed['cpcb_method_passed'] and not changed and not before['missing_tested_modules'],
              'offline_policy': {'blank_credentials': list(SECRET_NAMES), 'python_socket_connections': 'blocked',
                                 'third_party_pytest_autoload': 'disabled',
                                 'excluded_name_expression': 'real_database'},
              'logs': {'console': console.relative_to(root).as_posix(),
                       'console_sha256': hashlib.sha256(console.read_bytes()).hexdigest(),
                       'junit': junit.relative_to(root).as_posix(),
                       'junit_sha256': hashlib.sha256(junit.read_bytes()).hexdigest() if junit.exists() else None}}
    result['status'] = 'PASS' if result['suite_passed'] else 'FAILED_OR_INCOMPLETE'
    if snapshot:
        immutable = root / 'results/research/test_validation_snapshots' / f'{run_id}.json'
        if immutable.exists():
            raise ValueError('Immutable test validation snapshot already exists')
        write_json(immutable, result)
    write_json(root / 'results/research/test_validation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    result = run(snapshot=args.snapshot)
    print(json.dumps({'status': result['status'], 'exit_code': result['exit_code'],
                      'counts': result['counts'], 'cpcb_method_passed': result['cpcb_method_passed']}))
    return 0 if result['suite_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
