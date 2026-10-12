"""Run all existing Python tests; persist redacted output and actual JUnit counts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import platform
from importlib.metadata import version
from src.ingestion.settings import load_env, redact
from src.research.calibration.validation import parse_junit, source_fingerprint
from src.research.calibration.checkpoint import write_json

ROOT=Path(__file__).resolve().parents[1]
load_env()
environment=dict(os.environ)
environment.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTEST_ADDOPTS='')
command=[sys.executable,'-m','pytest','tests','-q','--junitxml=logs/defense-all-python-junit.log']
before=source_fingerprint()
result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True)
log=redact(result.stdout.decode('utf-8',errors='replace')+'\n'+result.stderr.decode('utf-8',errors='replace'))
(ROOT/'logs/defense-all-python.log').write_text(log,encoding='utf-8')
write_json(ROOT/'logs/defense-all-python-exit.log',{'exit_code':result.returncode})
report=parse_junit(ROOT/'logs/defense-all-python-junit.log',exit_code=result.returncode,log_text=log)
report.update(actual_exit_observed=True,exit_code=result.returncode,scope='all existing tests; real configured integrations enabled; database fixtures roll back',
              source_fingerprint=before,source_changed_during_run=before!=source_fingerprint())
report['runtime']={'python':platform.python_version(),'packages':{p:version(p) for p in ('numpy','pandas','pyarrow','pytest','streamlit')}}
write_json(ROOT/'results/project_hardening/all_python_tests.json',report)
print(json.dumps({k:report[k] for k in ('exit_code','counts','suite_passed','cpcb_method_passed','source_changed_during_run')}))
sys.exit(result.returncode)
