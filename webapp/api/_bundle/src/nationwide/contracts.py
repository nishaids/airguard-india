"""Runtime checks for the versioned public air-quality response contract."""
from src.nationwide.aqi import METHOD, parse_time


class ContractError(RuntimeError):
    pass


def validate_summary(payload):
    required={"ok","schema_version","location","current","tomorrow","hourly_forecast","provider_status","provenance","refreshed_at"}
    if not required<=set(payload) or payload["schema_version"]!="1.0":
        raise ContractError("Invalid summary envelope")
    for key in ("current","tomorrow"):
        result=payload[key]
        value=result["aqi"]
        if value is None:
            if result["status"]!="INSUFFICIENT_DATA":raise ContractError("Missing AQI status")
        elif not isinstance(value,int) or not 0<=value<=500 or not result.get("category") or not result.get("dominant_pollutant"):
            raise ContractError("Invalid AQI")
        if result["methodology_version"]!=METHOD:raise ContractError("Method mismatch")
    for hour in payload["hourly_forecast"]:
        parse_time(hour["time"])
        if hour["aqi"] is not None and not (isinstance(hour["aqi"],int) and 0<=hour["aqi"]<=500):raise ContractError("Invalid hourly AQI")
    tomorrow=payload["tomorrow"]
    if tomorrow.get("issued_at") and parse_time(tomorrow["issued_at"])>=parse_time(tomorrow["window_start"]):raise ContractError("Late forecast issuance")
    if payload["current"]["measured_or_modelled"]=="MEASURED" and not payload["current"]["station"]:raise ContractError("Measured AQI needs a station")
    # Track-record scores exist only for cells that meet the publication rule.
    for cell in payload.get("track_record") or []:
        if not isinstance(cell.get("eligible"),bool):raise ContractError("Track-record cell without eligibility")
        scored=[cell.get(k) is not None for k in ("mae","rmse","bias","category_accuracy","within_one_category")]
        if any(scored)!=cell["eligible"] or (cell["eligible"] and not all(scored)):raise ContractError("Track-record score published without enough forecasts")
    return payload
