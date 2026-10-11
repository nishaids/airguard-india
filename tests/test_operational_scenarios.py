from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from src.nationwide.aqi import METHOD, aggregate
from src.nationwide.scenarios import handle, recalculate
from src.nationwide.store import BudgetExceeded

START = datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)  # 12 Oct IST
NOW = START - timedelta(hours=5)

def record(missing=()):
    times = [START + timedelta(hours=i) for i in range(-24, 24)]
    fields = {"pm2_5": 80., "pm10": 130., "nitrogen_dioxide": 30., "sulphur_dioxide": 10., "carbon_monoxide": 900., "ozone": 80.}
    mapping = {"pm2_5": "PM2.5", "pm10": "PM10", "nitrogen_dioxide": "NO2", "sulphur_dioxide": "SO2", "carbon_monoxide": "CO", "ozone": "O3"}
    raw = {"hourly": {"time": [t.timestamp() for t in times], **{k: [None if mapping[k] in missing else v for _ in times] for k, v in fields.items()}}, "hourly_units": {k: "µg/m³" for k in fields}}
    rows = [{"time": t.isoformat(), **{mapping[k]: (v / 1000 if k == "carbon_monoxide" else v) for k, v in fields.items() if mapping[k] not in missing}} for t in times]
    result = aggregate(rows, START, START + timedelta(days=1))
    return {"id": 73, "location_key": "13.1147,80.1098", "issued_at": NOW, "target_start": START, "target_end": START + timedelta(days=1), "predicted_aqi": result["aqi"], "qualifier": result["qualifier"], "methodology_version": METHOD, "raw_forecast_reference": "immutable-input", "artifact": {"provider_input": raw, "forecast": {**result, "date": "2026-10-12"}}}

class MemoryStore:
    def __init__(self, saved=None, limited=False): self.saved = saved or record(); self.limited = limited
    def budget(self, *args):
        if self.limited: raise BudgetExceeded("test")
    @contextmanager
    def cursor(self): yield self
    def execute(self, query, params): self.params = params
    def fetchone(self): return self.saved if self.params == (self.saved["id"], self.saved["location_key"]) else None

def request(**updates): return {"forecast_run_id": 73, "location_key": "13.1147,80.1098", "reductions": {}, **updates}

def test_zero_reduction_reproduces_saved_live_baseline():
    code, result = handle(request(), store=MemoryStore(), now=NOW)
    assert code == 200 and result["baseline"] == result["scenario"]
    assert result["baseline"]["aqi"] == record()["predicted_aqi"]
    assert result["methodology_version"] == METHOD and result["forecast_run_id"] == 73

def test_pm_reduction_uses_central_engine_and_changes_dominant_pollutant():
    result = recalculate(record(), {"PM2.5": .5})
    assert result["scenario"]["aqi"] < result["baseline"]["aqi"]
    assert result["baseline"]["dominant_pollutant"] == "PM2.5"
    assert result["scenario"]["dominant_pollutant"] == "PM10"
    assert result["scenario"]["pollutants"]["PM2.5"]["concentration"] == 40

def test_saved_input_not_modified_and_missing_pollutant_not_imputed():
    saved = record(missing=("SO2",)); before = deepcopy(saved)
    result = recalculate(saved, {"PM2.5": .2})
    assert saved == before and result["scenario"]["pollutants"]["SO2"]["concentration"] is None

def test_gas_scenario_keeps_preceding_seven_hour_support():
    saved = record()
    times = saved["artifact"]["provider_input"]["hourly"]["time"]
    values = [18000 if t < START.timestamp() else 1000 for t in times]
    saved["artifact"]["provider_input"]["hourly"]["carbon_monoxide"] = values
    rows = [{"time": datetime.fromtimestamp(t, timezone.utc).isoformat(), "PM2.5": 80., "PM10": 130., "NO2": 30., "SO2": 10., "CO": v / 1000, "O3": 80.} for t, v in zip(times, values)]
    baseline = aggregate(rows, START, START + timedelta(days=1)); saved["predicted_aqi"] = baseline["aqi"]; saved["qualifier"] = baseline["qualifier"]
    result = recalculate(saved, {"CO": .2})
    assert result["baseline"]["pollutants"]["CO"]["concentration"] == 15.875
    assert result["scenario"]["pollutants"]["CO"]["concentration"] == 12.7

@pytest.mark.parametrize("changes", [{"forecast_run_id": True}, {"forecast_run_id": 0}, {"location_key": ""}, {"reductions": {"PM2.5": -1}}, {"reductions": {"PM2.5": 2}}, {"reductions": {"PM2.5": True}}, {"reductions": {"PM2.5": float('nan')}}, {"reductions": {"NH3": .2}}, {"cohort": "Asthma/COPD"}, {"city": "Delhi", "date": "2020-01-01"}])
def test_invalid_operational_input_rejected(changes):
    assert handle(request(**changes), store=MemoryStore(), now=NOW)[0] == 400

def test_missing_reference_cannot_select_historical_scenario():
    assert handle({"reductions": {"PM2.5": .2}}, store=MemoryStore(), now=NOW)[0] == 400

def test_mismatched_location_expiry_and_rate_limit():
    assert handle(request(location_key="Delhi"), store=MemoryStore(), now=NOW)[0] == 404
    assert handle(request(), store=MemoryStore(), now=START + timedelta(days=1))[0] == 409
    assert handle(request(), store=MemoryStore(limited=True), now=NOW)[0] == 429

def test_changed_method_or_input_cannot_silently_change_baseline():
    saved = record(); saved["predicted_aqi"] += 1
    assert handle(request(), store=MemoryStore(saved), now=NOW)[0] == 400
    saved = record(); saved["methodology_version"] = "different"
    assert handle(request(), store=MemoryStore(saved), now=NOW)[0] == 400
