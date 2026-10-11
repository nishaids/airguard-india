"""Verify the public research rewrite on the existing protected Vercel preview."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.ingestion.settings import load_env, secret, SECRET_NAMES


def main():
    load_env()
    root = Path(__file__).resolve().parents[1]
    url = sys.argv[1]
    if not url.startswith('https://webapp-') or not url.endswith('.vercel.app'):
        raise ValueError('Supply an existing webapp preview URL.')
    packages = (Path(os.environ['LOCALAPPDATA']) / 'npm-cache/_npx').glob('*/node_modules/vercel/package.json')
    cli = next(p.parent / 'dist/vc.js' for p in packages if json.loads(p.read_text())['version'] == '63.1.2')
    checks = []

    def request(path, expected=200, marker=None):
        args = [shutil.which('node'), str(cli), 'curl', path, '--deployment', url, '--', '--silent', '--show-error', '--max-time', '60', '--write-out', 'HTTP_STATUS:%{http_code}']
        response = subprocess.run(args, cwd=root / 'webapp', capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
        body, _, status = response.stdout.rpartition('HTTP_STATUS:')
        assert response.returncode == 0 and status == str(expected), f'Unexpected status on {path}: {status}'
        assert all(not secret(name) or secret(name) not in body for name in SECRET_NAMES)
        if marker:
            assert marker in body
            value = None
        else:
            value = json.loads(body)
        checks.append({'path': path, 'status': expected, 'kind': 'SSR HTML' if marker else 'HTTP JSON'})
        print(json.dumps(checks[-1]), flush=True)
        return value

    status = request('/api/research/status')
    assert status['ok'] and status['archive_experiment'] == 'PENDING — ADS credential/terms required'
    assert status['protocol']['protocol_version'] == 'airguard-dayahead-20ist-v1'
    assert status['readiness']['status'] == 'COLLECTING_NOT_RESEARCH_READY'
    request('/api/research/status?unexpected=1', 400)
    request('/api/providers/status?view=refresh', 400)
    alias = request('/api/providers/status?view=research')
    assert alias['protocol'] == status['protocol']
    request('/research/track-record', marker='Prospective forecast ledger')
    request('/research/legacy', marker='AirGuard')
    request('/live', marker='AirGuard')
    live = request('/api/air-quality/summary?lat=13.0827&lon=80.2707&name=Chennai')
    from src.nationwide.contracts import validate_summary
    validate_summary(live)
    assert live['tomorrow']['forecast_mode'] == 'CAMS_BASED_NATIONWIDE'
    assert live['tomorrow']['correction_status'] == 'NOT_VALIDATED'
    assert live['tomorrow']['corrected_aqi'] is None
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'deployment_url': url, 'passed': len(checks), 'checks': checks, 'prospective': status['prospective'], 'archive_experiment': status['archive_experiment'], 'visual_browser_qa': 'NOT_EXECUTED', 'production_changed': False}
    (root / 'results/research/preview_acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': len(checks), 'prospective_forecasts': status['prospective']['forecasts']}))


if __name__ == '__main__':
    main()
