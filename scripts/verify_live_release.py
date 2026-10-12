"""Capture fresh, credential-redacted checks for a production-safe release."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from src.ingestion.settings import load_env, redact
from src.research.calibration.checkpoint import write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_env()
    checks = {}
    for name in ('lint', 'typecheck', 'test', 'build'):
        command = ['cmd', '/c', 'npm', 'run', name]
        if name == 'test':
            command += ['--', '--reporter=json', '--outputFile=test-results/live-release-unit.json']
        result = subprocess.run(command, cwd=ROOT/'webapp', capture_output=True)
        path = ROOT/f'logs/live-release-{name}.log'
        path.write_text(redact((result.stdout + result.stderr).decode('utf-8', errors='replace')), encoding='utf-8')
        checks[name] = {'command': ' '.join(command[2:]), 'exit_code': result.returncode,
                        'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        print(json.dumps({'check': name, 'exit_code': result.returncode}), flush=True)
        if result.returncode:
            break
    unit_path = ROOT/'webapp/test-results/live-release-unit.json'
    unit = json.loads(unit_path.read_text(encoding='utf-8')) if unit_path.exists() else {}
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'git_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'unit': {k: unit.get(k) for k in ('success', 'numTotalTests', 'numPassedTests', 'numFailedTests')},
              'passed': len(checks) == 4 and all(c['exit_code'] == 0 for c in checks.values()) and unit.get('success') is True}
    write_json(ROOT/'results/release/website_preflight.json', report)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
