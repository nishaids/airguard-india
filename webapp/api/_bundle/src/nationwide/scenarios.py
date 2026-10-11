"""Read-only counterfactual on an immutable operational forecast's raw inputs.

No provider requests, training, clinical scores or historical rows. Reuse the
central normalization and daily AQI engine, including preceding gas support.
"""
from __future__ import annotations
import hashlib
import math
from datetime import datetime, timezone
from src.ingestion.settings import load_env, secret
from src.nationwide.aqi import METHOD, aggregate, normalize, parse_time, valid
from src.nationwide.providers import AIR_FIELDS
from src.nationwide.store import Store, BudgetExceeded, digest

POLLUTANTS = set(AIR_FIELDS.values())

def recalculate(record, reductions):
    if record["methodology_version"] != METHOD:
        raise ValueError("This forecast uses a different methodology version.")
    raw = record["artifact"]["provider_input"]
    hourly, units = raw["hourly"], raw["hourly_units"]
    times = hourly["time"]
    if not isinstance(times, list) or not 1 <= len(times) <= 240:
        raise ValueError("Saved hourly inputs are unavailable.")
    rows = []
    for i, timestamp in enumerate(times):
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp):
            raise ValueError("Invalid saved timestamp.")
        row = {"time": datetime.fromtimestamp(timestamp, timezone.utc).isoformat()}
        for field, pollutant in AIR_FIELDS.items():
            values = hourly.get(field)
            if not isinstance(values, list) or len(values) != len(times):
                raise ValueError("Saved hourly pollutant data is incomplete.")
            value = normalize(pollutant, values[i], units.get(field, ""))
            if values[i] is not None and value is None:
                raise ValueError("Saved pollutant unit or concentration is unusable.")
            if value is not None:
                row[pollutant] = value
        rows.append(row)
    start, end = parse_time(record["target_start"]), parse_time(record["target_end"])
    baseline = aggregate(rows, start, end)
    # Never silently compare the UI forecast to another vintage or engine.
    if baseline["aqi"] != record["predicted_aqi"] or baseline["qualifier"] != record["qualifier"]:
        raise ValueError("Saved inputs do not reproduce the forecast baseline.")
    if baseline["aqi"] is None:
        raise ValueError("The forecast lacks an eligible AQI baseline.")
    modified = [{k: v * (1 - reductions.get(k, 0)) if k in POLLUTANTS and valid(v) else v for k, v in row.items()} for row in rows]
    scenario = aggregate(modified, start, end)
    return {"ok": True, "kind": "COUNTERFACTUAL_AQI_SCENARIO", "forecast_run_id": record["id"], "location_key": record["location_key"], "target_date": record["artifact"]["forecast"]["date"], "issued_at": parse_time(record["issued_at"]).isoformat(), "methodology_version": METHOD, "input_reference": record["raw_forecast_reference"], "scenario_reference": digest([record["raw_forecast_reference"], METHOD, reductions]), "baseline": baseline, "scenario": scenario, "reductions": reductions, "notice": "If the selected forecast pollutant concentrations were reduced by these amounts, the corresponding CPCB-style AQI would be approximately this value. This is a counterfactual calculation, not a prediction of a policy's causal effect."}

def handle(payload, client="anonymous", store=None, now=None):
    load_env()
    try:
        if not isinstance(payload, dict) or set(payload) - {"forecast_run_id", "location_key", "reductions"}:
            raise ValueError("Supply forecast_run_id, location_key and pollutant reductions only.")
        identifier, location_key = payload.get("forecast_run_id"), payload.get("location_key")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 1 or not isinstance(location_key, str) or not 1 <= len(location_key) <= 80:
            raise ValueError("A saved operational forecast and its location key are required.")
        raw = payload.get("reductions", {})
        if not isinstance(raw, dict) or set(raw) - POLLUTANTS or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in raw.values()):
            raise ValueError("Use supported pollutant reductions between 0 and 1.")
        reductions = {k: float(v) for k, v in raw.items() if v > 0}
        store = store or Store()
        token = hashlib.sha256(((secret("CRON_SECRET") or "airguard") + client).encode()).hexdigest()
        store.budget("request:" + token, 60, 60)
        store.budget("requests-all", 120, 60)
        with store.cursor() as cur:
            cur.execute("select id,location_key,issued_at,target_start,target_end,predicted_aqi,qualifier,raw_forecast_reference,methodology_version,artifact from airguard.forecast_runs where id=%s and location_key=%s", (identifier, location_key))
            record = cur.fetchone()
        if not record:
            return 404, {"ok": False, "message": "No operational forecast matches this location and record."}
        if parse_time(record["target_end"]) <= (now or datetime.now(timezone.utc)):
            return 409, {"ok": False, "message": "This forecast target has ended. Refresh the live summary before calculating a scenario."}
        return 200, recalculate(record, reductions)
    except ValueError as e:
        return 400, {"ok": False, "message": str(e)}
    except BudgetExceeded:
        return 429, {"ok": False, "message": "Request budget reached. Please retry later."}
    except Exception:
        return 503, {"ok": False, "message": "Saved forecast inputs are temporarily unavailable. No historical substitute was used."}
