"""The security readiness gate, as a conjunction of individually checkable facts.

A gate that a human ticks is not evidence. Each check below reads either a
committed audit artefact or the source that enforces the control, so the gate
can only pass while the control is actually there. A check whose evidence is
absent returns None and the gate does not pass: unknown is not the same as safe.
"""
import json
from pathlib import Path

from src import config
from src.qa.paths import scan

CLIENT_TREE = 'webapp/app'
SERVER_ONLY_SECRETS = ('SUPABASE_SERVICE_ROLE_KEY', 'DATABASE_URL', 'SERVICE_ROLE')


def _read(relative, root):
    path = root / relative
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None


def _contains(relative, needle, root):
    path = root / relative
    if not path.exists():
        return None
    return needle in path.read_text(encoding='utf-8')


def _client_bundle_secret_references(root):
    """Server-only secret names appearing in client-rendered source."""
    base = root / CLIENT_TREE
    if not base.exists():
        return None
    hits = []
    for path in base.rglob('*'):
        if path.suffix not in {'.js', '.jsx', '.ts', '.tsx'} or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for name in SERVER_ONLY_SECRETS:
            if name in text:
                hits.append(f'{path.relative_to(root).as_posix()}:{name}')
    return hits


def gate(root=None):
    root = Path(root or config.PROJECT_ROOT)
    database = _read('results/release/database_audit.json', root) or {}
    secrets = _read('results/release/secret_audit.json', root)
    workflow = root / '.github/workflows/quality.yml'
    workflow_text = workflow.read_text(encoding='utf-8') if workflow.exists() else ''
    leaks = scan(root=root)
    client_hits = _client_bundle_secret_references(root)

    checks = {
        # Every AirGuard table carries row-level security, read back from the database.
        'row_level_security_everywhere': database.get('all_airguard_tables_rls'),
        # No generated or published artefact names a local absolute path.
        'no_generated_path_leaks': len(leaks) == 0,
        # No credential value appears in Git history, the worktree or built browser assets.
        'no_secret_material_committed': None if secrets is None else (
            secrets.get('history_secret_hits') == 0
            and secrets.get('current_worktree_secret_hits') == 0
            and secrets.get('browser_asset_secret_hits') == 0),
        # Server-only secret names do not appear in client-rendered source.
        'service_role_key_server_only': None if client_hits is None else len(client_hits) == 0,
        # Per-bucket request budgets are enforced in the data layer, not just documented.
        'request_budget_enforced': _contains('src/nationwide/store.py', 'airguard.request_budgets', root),
        # Coordinates are range-checked before any provider call.
        'coordinate_range_validated': _contains('src/nationwide/providers.py', '6 <= latitude <= 38', root),
        # CI fails on a reintroduced local path and on a high-severity dependency advisory.
        'path_guard_in_ci': 'check_generated_paths' in workflow_text,
        'dependency_audit_in_ci': 'npm audit' in workflow_text,
    }
    unknown = sorted(name for name, value in checks.items() if value is None)
    failed = sorted(name for name, value in checks.items() if value is False)
    return {
        'checks': checks,
        'passed': bool(checks) and not failed and not unknown,
        'failed': failed,
        'unknown': unknown,
        'path_leaks': leaks,
        'client_secret_references': client_hits or [],
        'evidence': {
            'database_audit': database.get('generated_at'),
            'secret_audit': (secrets or {}).get('generated_at'),
        },
        'notice': 'A check without evidence is unknown, and unknown does not pass. Penetration testing, '
                  'authentication hardening and upstream provider terms are outside this gate.',
    }
