"""Bounded, replaceable providers with validated units and explicit provenance."""
from __future__ import annotations

import json
import math
import os
import time
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from dataclasses import replace

from src.ingestion.http import HttpClient, HttpError, as_dict
from src.ingestion.settings import get_settings, secret, redact
from src.nationwide.aqi import IST, METHOD, aggregate, normalize, parse_time, valid
from src.nationwide.store import digest, BudgetExceeded

AIR_FIELDS = {"pm2_5": "PM2.5", "pm10": "PM10", "nitrogen_dioxide": "NO2", "sulphur_dioxide": "SO2", "carbon_monoxide": "CO", "ozone": "O3"}
WEATHER_FIELDS = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_direction_10m", "surface_pressure", "boundary_layer_height")
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPENAQ_URL = "https://api.openaq.org/v3"


def utcnow():
    return datetime.now(timezone.utc)


def coordinates(lat, lon):
    try:
        latitude, longitude = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("Supply numeric lat and lon.") from None
    if not math.isfinite(latitude) or not math.isfinite(longitude) or not (6 <= latitude <= 38 and 68 <= longitude <= 98):
        raise ValueError("Coordinates must be within the India service region (6–38°N, 68–98°E).")
    return latitude, longitude


def grid(lat, lon):
    # CAMS global native resolution 0.4°, not a station-level location.
    return round(round(lat / .4) * .4, 1), round(round(lon / .4) * .4, 1)


def distance(lat, lon, station):
    a, b = map(math.radians, (lat, station["latitude"]))
    dlat, dlon = b - a, math.radians(station["longitude"] - lon)
    return 6371 * 2 * math.asin(min(1, math.sqrt(math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2)))


class Providers:
    def __init__(self, store, client=None):
        self.store = store
        self.client = client or HttpClient(replace(get_settings(), http_timeout_seconds=8, http_max_retries=1, http_max_backoff_seconds=2))

    def get_json(self, provider, url, params=None, headers=None):
        with self.store.session() if hasattr(self.store,'session') else nullcontext():
            return self._get_json(provider,url,params,headers)

    def _get_json(self, provider, url, params=None, headers=None):
        started = time.monotonic()
        try:
            result = as_dict(self.client.get(url, params, headers, label=provider, before_attempt=lambda: self.request_budget(provider)).json(), provider)
            count = len(result.get("results", result.get("hourly", {}).get("time", [])))
            self.store.event(provider, url.split("/")[-1], "SUCCESS", int((time.monotonic() - started) * 1000), count)
            return result
        except HttpError as exc:
            self.store.event(provider, url.split("/")[-1], "FAILED", int((time.monotonic() - started) * 1000), http_status=exc.status, error_class=exc.kind, detail=redact(exc))
            raise

    def request_budget(self, provider):
        # Every transport attempt, including retries, consumes the shared budget.
        # Fixed URLs only; inputs never become an outbound host or arbitrary URL.
        self.store.budget("provider-hour:" + provider, 200 if provider == "openaq" else 600)
        self.store.budget("provider-day:" + provider, 4000 if provider == "openaq" else 8000, 86400)
        self.store.budget("provider-minute:"+provider,55 if provider=="openaq" else 400,60)
        if provider in ("open_meteo","weather","geocoding"):
            self.store.budget("open-meteo-all-day",9000,86400)
            self.store.budget("open-meteo-all-hour",4000,3600)
            self.store.budget("open-meteo-all-minute",500,60)

    def air(self, lat, lon):
        payload = self.get_json("open_meteo", AIR_URL, {"latitude": lat, "longitude": lon, "domains": "cams_global", "hourly": ",".join(AIR_FIELDS), "timezone": "Asia/Kolkata", "timeformat": "unixtime", "past_days": 2, "forecast_days": 3})
        return self.parse_series(payload, lat, lon, AIR_FIELDS, "open_meteo", "cams_global", "modelled_forecast", AIR_URL)

    def weather(self, lat, lon):
        payload = self.get_json("weather", WEATHER_URL, {"latitude": lat, "longitude": lon, "models": "gfs_seamless", "hourly": ",".join(WEATHER_FIELDS), "timezone": "Asia/Kolkata", "timeformat": "unixtime", "forecast_days": 3})
        result = self.parse_series(payload, lat, lon, dict(zip(WEATHER_FIELDS, WEATHER_FIELDS)), "open_meteo", "gfs_seamless", "weather_forecast", WEATHER_URL)
        self.store.weather(result, lat, lon)
        return result

    def parse_series(self, payload, lat, lon, fields, provider, model, source_type, url):
        hourly, units = payload.get("hourly"), payload.get("hourly_units")
        if not isinstance(hourly, dict) or not isinstance(units, dict) or not isinstance(hourly.get("time"), list) or not hourly["time"]:
            raise HttpError("Provider returned no hourly series or unit metadata.", kind="schema")
        if len(hourly["time"]) > 240:
            raise HttpError("Hourly response exceeded the configured bound.", kind="schema")
        now = utcnow().isoformat()
        rows, records = [], []
        for i, timestamp in enumerate(hourly["time"]):
            if not isinstance(timestamp, (float, int)) or not math.isfinite(timestamp):
                raise HttpError("Invalid provider timestamp.", kind="schema")
            at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            row = {"time": at}
            for field, pollutant in fields.items():
                values = hourly.get(field)
                if not isinstance(values, list) or len(values) != len(hourly["time"]):
                    raise HttpError("Missing or mismatched hourly field: " + field, kind="schema")
                raw_value, unit = values[i], units.get(field)
                if source_type == "weather_forecast":
                    # Temperature and direction can be zero/negative; weather is
                    # kept in the immutable provider payload, not the AQ table.
                    if isinstance(raw_value, (int, float)) and math.isfinite(raw_value) and isinstance(unit, str):
                        row[pollutant] = raw_value
                    continue
                value = normalize(pollutant, raw_value, unit or "")
                if raw_value is not None and value is None:
                    raise HttpError("Unusable concentration or mass unit: " + field, kind="unit_validation")
                if value is None:
                    continue
                row[pollutant] = value
                provenance = {"endpoint": url, "model": model, "configured_domain": model, "native_grid_degrees": .4, "provider_grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude")}, "raw_unit": unit, "raw_value": raw_value, "provider_issued_at": None, "issue_time_basis": "AirGuard retrieval; provider API does not publish model run time", "attribution": "Open-Meteo.com / Copernicus Atmosphere Monitoring Service", "time_semantics": "hourly model value; native 3h CAMS data interpolated by provider"}
                records.append({"record_key": digest([provider, model, lat, lon, at, pollutant, raw_value]), "provider": provider, "source_type": source_type,
                    "model": model, "latitude": lat, "longitude": lon, "pollutant": pollutant, "raw_value": raw_value, "raw_unit": unit,
                    "normalized_value": value, "normalized_unit": "mg/m3" if pollutant == "CO" else "ug/m3", "valid_at": at,
                    "issued_at": now, "provider_issued_at": None, "fetched_at": now, "quality_state": "VALID", "provenance": provenance, "methodology_version": METHOD})
            rows.append(row)
        if len({r["time"] for r in rows}) != len(rows):
            raise HttpError("Duplicate provider timestamps.", kind="schema")
        self.store.records(records)
        result = {"rows": rows, "provider": provider, "model": model, "source_type": source_type, "fetched_at": now, "issued_at": now,
            "provider_issued_at": None, "grid": {"lat": payload.get("latitude"), "lon": payload.get("longitude"), "native_resolution_degrees": .4 if model == "cams_global" else None},
            "units": units, "raw": payload, "raw_reference": digest(payload), "quality": "VALID"}
        if hasattr(self.store,'research_snapshot'):
            try: self.store.research_snapshot(result,lat,lon)
            except Exception: self.store.event('research','snapshot','FAILED',0,error_class='SnapshotPersistenceFailure')
        return result

    def search(self, query):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 100 or any(ord(c) < 32 for c in query):
            raise ValueError("Search must contain 2–100 characters.")
        payload = self.get_json("geocoding", GEO_URL, {"name": query.strip(), "countryCode": "IN", "count": 10, "language": "en", "format": "json"})
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise HttpError("Invalid geocoding response.", kind="schema")
        locations = []
        for r in results[:10]:
            if r.get("country_code") != "IN":
                continue
            lat, lon = coordinates(r.get("latitude"), r.get("longitude"))
            label = ", ".join(dict.fromkeys(x for x in (r.get("name"), r.get("admin2"), r.get("admin1"), "India") if x))
            locations.append({"key": f"{lat:.4f},{lon:.4f}", "name": label, "region": r.get("admin1"), "district": r.get("admin2"), "lat": lat, "lon": lon, "geonames_id": r.get("id"), "country_code": "IN", "country": "IN"})
        return {"results": locations, "provider": "Open-Meteo / GeoNames", "fetched_at": utcnow().isoformat(), "postal_code_support": "Provider dependent; empty results are not replaced by a city guess."}

    def measured(self, lat, lon, start=None, end=None):
        key = secret("OPENAQ_API_KEY")
        if not key:
            return {"status": "UNAVAILABLE", "reason": "OpenAQ is not configured on this runtime.", "stations": [], "fetched_at": utcnow().isoformat()}
        now = utcnow()
        end = end or now
        start = start or end - timedelta(hours=32)
        headers = {"X-API-Key": key}
        payload = self.get_json("openaq", OPENAQ_URL + "/locations", {"coordinates": f"{lat},{lon}", "radius": get_settings().openaq_search_radius_m, "limit": 100}, headers)
        if not isinstance(payload.get("results"), list):
            raise HttpError("Invalid station discovery response.", kind="schema")
        candidates = []
        for station in payload["results"]:
            coords = station.get("coordinates") or {}
            if not isinstance(coords.get("latitude"), (float, int)) or not isinstance(coords.get("longitude"), (float, int)):
                continue
            km = distance(lat, lon, coords)
            if km > get_settings().openaq_search_radius_m / 1000 or (station.get("country") or {}).get("code") != "IN":
                continue
            # Never query old inactive stations as if they were current.
            try:
                last = parse_time(station["datetimeLast"]["utc"])
                if last < start or last > now + timedelta(minutes=30):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            sensors = [s for s in station.get("sensors", []) if s.get("parameter", {}).get("name") in ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "pb")]
            candidates.append((station, km, sensors))
        candidates.sort(key=lambda x: (len({s["parameter"]["name"] for s in x[2]}) < 3, x[1]))
        stations, partial_errors = [], []
        for metadata, km, sensors in candidates[:2]:
            station_pk = self.store.station(metadata)
            rows_by_time, records, readings = {}, [], []
            mapping = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO2", "so2": "SO2", "co": "CO", "o3": "O3", "nh3": "NH3", "pb": "Pb"}
            # One sensor per pollutant, no mixing measurements from different stations.
            seen, jobs = set(), []
            for sensor in sensors:
                pollutant = mapping[sensor["parameter"]["name"]]
                if pollutant in seen or normalize(pollutant, 1, sensor["parameter"].get("units", "")) is None:
                    continue
                seen.add(pollutant)
                jobs.append((sensor, pollutant))
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(self.get_json, "openaq", OPENAQ_URL + f"/sensors/{int(sensor['id'])}/hours", {"datetime_from": start.isoformat(), "datetime_to": end.isoformat(), "limit": 100}, headers): (sensor, pollutant) for sensor, pollutant in jobs[:8]}
                for future in as_completed(futures):
                    sensor, pollutant = futures[future]
                    try:
                        data = future.result()
                        if not isinstance(data.get("results"), list):
                            raise HttpError("Missing hourly station results", kind="schema")
                        self.store.sensor(station_pk, sensor)
                        for item in data["results"]:
                            parameter = item.get("parameter") or {}
                            if parameter.get("name") != sensor["parameter"]["name"]:
                                raise HttpError("Hourly pollutant identity does not match the requested sensor",kind="schema")
                            unit = parameter.get("units", "")
                            value = normalize(pollutant, item.get("value"), unit)
                            if value is None or (item.get("flagInfo") or {}).get("hasFlags"):
                                continue
                            at = parse_time(item["period"]["datetimeFrom"]["utc"])
                            until = parse_time(item["period"]["datetimeTo"]["utc"])
                            if not start <= at < end or until > end or until-at != timedelta(hours=1):
                                continue
                            # Reject hourly bins with <75% reporting coverage when reported.
                            coverage = (item.get("coverage") or {}).get("percentCoverage")
                            if coverage is not None and coverage < 75:
                                continue
                            rows_by_time.setdefault(at.isoformat(), {"time": at.isoformat()})[pollutant] = value
                            provenance = {"endpoint": f"{OPENAQ_URL}/sensors/{int(sensor['id'])}/hours", "station": metadata, "sensor": sensor, "hourly_record": item, "upstream_provider": metadata.get("provider"), "owner": metadata.get("owner"), "distance_km": round(km, 2)}
                            records.append({"record_key": digest(["openaq", sensor["id"], at.isoformat(), pollutant]), "provider": "openaq", "source_type": "measured", "station_pk": station_pk, "sensor_id": str(sensor["id"]), "latitude": metadata["coordinates"]["latitude"], "longitude": metadata["coordinates"]["longitude"], "pollutant": pollutant, "raw_value": item["value"], "raw_unit": unit, "normalized_value": value, "normalized_unit": "mg/m3" if pollutant == "CO" else "ug/m3", "valid_at": at.isoformat(), "issued_at": None, "fetched_at": now.isoformat(), "quality_state": "VALID", "provenance": provenance, "methodology_version": METHOD})
                            readings.append({"pollutant": pollutant, "value": value, "unit": "mg/m³" if pollutant == "CO" else "µg/m³", "raw_unit": unit, "raw_value": item["value"], "sensor": sensor["id"], "observed_at": until.isoformat()})
                    except (HttpError, KeyError, ValueError, TypeError, BudgetExceeded) as exc:
                        partial_errors.append(type(exc).__name__)
            self.store.records(records)
            rows = list(rows_by_time.values())
            last = max((parse_time(r["observed_at"]) for r in readings), default=None)
            snapshot_end = max((parse_time(r["time"]) for r in rows), default=end - timedelta(hours=1)) + timedelta(hours=1)
            calculation = aggregate(rows, snapshot_end-timedelta(hours=24), snapshot_end, rolling=True)
            # Latest context remains visible even when a complete AQI is impossible.
            latest = {r["pollutant"]: r for r in sorted(readings, key=lambda r: r["observed_at"])}
            stations.append({"id": metadata["id"], "station_pk": station_pk, "name": metadata.get("name"), "coordinates": metadata["coordinates"], "distance_km": round(km, 2), "provider": metadata.get("provider"), "owner": metadata.get("owner"), "licenses": metadata.get("licenses"), "last_observed_at": last.isoformat() if last else None, "calculation": calculation, "latest": list(latest.values()), "rows": rows})
        if hasattr(self.store,'research_snapshot'):
            for station in stations:
                try:
                    self.store.research_snapshot(dict(station,source_type='measured',provider='openaq',fetched_at=now.isoformat()),
                        station['coordinates']['latitude'],station['coordinates']['longitude'],station['station_pk'])
                except Exception: self.store.event('research','snapshot','FAILED',0,error_class='SnapshotPersistenceFailure')
        return {"status": "PARTIAL" if partial_errors else "SUCCESS", "stations": stations, "fetched_at": now.isoformat(), "reason": "No sufficiently recent nearby station with adequate hourly pollutants." if not stations else "Station hourly series evaluated; partial pollutant coverage is not a complete AQI.", "errors": partial_errors}
