import json

from src.qa.paths import scan
from src.qa.security import gate


def test_gate_passes_only_on_present_evidence_and_reports_what_is_missing(tmp_path):
    empty = gate(root=tmp_path)
    assert empty['passed'] is False
    # Nothing is readable under an empty root, so no check may be assumed safe.
    assert set(empty['unknown']) >= {'row_level_security_everywhere', 'no_secret_material_committed',
                                     'service_role_key_server_only'}


def test_repository_gate_names_every_control_and_passes_or_explains():
    result = gate()
    expected = {'row_level_security_everywhere', 'no_generated_path_leaks', 'no_secret_material_committed',
                'service_role_key_server_only', 'request_budget_enforced', 'coordinate_range_validated',
                'path_guard_in_ci', 'dependency_audit_in_ci'}
    assert set(result['checks']) == expected
    assert result['passed'] is (not result['failed'] and not result['unknown'])
    if not result['passed']:
        assert result['failed'] or result['unknown']


def test_a_failed_control_blocks_the_gate(tmp_path):
    (tmp_path / 'results/release').mkdir(parents=True)
    (tmp_path / 'results/release/database_audit.json').write_text(
        json.dumps({'all_airguard_tables_rls': False}), encoding='utf-8')
    result = gate(root=tmp_path)
    assert result['checks']['row_level_security_everywhere'] is False
    assert 'row_level_security_everywhere' in result['failed']
    assert result['passed'] is False


def test_path_scan_exempts_only_the_documents_that_quote_the_leak():
    from src.qa.paths import EXEMPT
    assert 'docs/MASTER_SPEC.md' in EXEMPT
    assert not [p for p in scan() if p.startswith('webapp/public')]
