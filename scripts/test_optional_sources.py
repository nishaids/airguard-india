"""Independent optional-source checks. Exact CPCB errors are redacted."""
import json
from dataclasses import replace
from pathlib import Path
from src.ingestion.settings import load_env,get_settings,redact
from src.ingestion.http import HttpClient
from src.ingestion import cpcb,firms

load_env()
settings=replace(get_settings(),http_timeout_seconds=8,http_max_retries=0)
results=[]
for module in (cpcb,firms):
    try:
        bundle=module.collect(settings=settings,client=HttpClient(settings),limit=10)
        results.append({"source":module.__name__,"status":"PARTIAL" if bundle.partial else "SUCCESS","records":len(bundle.records),"notes":bundle.notes})
    except Exception as exc:
        results.append({"source":module.__name__,"status":"FAILED","error_class":type(exc).__name__,"exact_error":redact(exc)})
Path("results/optional_provider_checks.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print(json.dumps(results,indent=2))
