"""Real provider acceptance, persisted results, no fixed AQI assertions."""
import json
from pathlib import Path
from src.ingestion.settings import load_env, redact
from src.nationwide.service import Service

load_env()
service = Service()
out = []
for query in ("Avadi",):
    try:
        search = service.search(query)
        location = search["results"][0]
        summary = service.summary(location["lat"],location["lon"],location["name"],location.get("region"))
        Path("results/nationwide_example.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
        out.append({"location":location,"current":{k:summary["current"].get(k) for k in ("aqi","status","measured_or_modelled","timestamp","freshness")},"tomorrow":{k:summary["tomorrow"].get(k) for k in ("aqi","status","date","peak_hour","issued_at","forecast_run_id")},"providers":summary["provider_status"],"stations":len(summary["measured_context"]["stations"]),"hours":len(summary["hourly_forecast"]),"ok":summary["ok"]})
    except Exception as exc:
        out.append({"query":query,"error":redact(exc),"class":type(exc).__name__})
print(json.dumps(out,ensure_ascii=True,indent=2))
