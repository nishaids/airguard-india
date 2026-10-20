"""On-demand nationwide orchestration with explicit failure and stale states."""
from __future__ import annotations

import copy
import math
import os
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from statistics import mean

from src.ingestion.settings import get_settings
from src.nationwide.aqi import CATEGORIES, IST, METHOD, SOURCE, aggregate, parse_time, tomorrow_period
from src.nationwide.providers import Providers, coordinates, grid, utcnow, distance
from src.nationwide.store import Store, digest
from src.features.exposure import VERSION as EXPOSURE_VERSION
from src.nationwide.cache_policy import remaining_seconds

#: A summary assembled while another request was refreshing one of its sources
#: carries that source's older copy. Fresh data is moments away, so such a
#: summary is kept only briefly instead of for the usual ten minutes.
STALE_SUMMARY_SECONDS = 30


def ttl(name, default):
    try:
        return max(60, min(86400*30, int(os.environ.get(name, default))))
    except ValueError:
        return default


class Service:
    def __init__(self, store=None, providers=None):
        self.store = store or Store()
        self.providers = providers or Providers(self.store)

    def cached(self, key, provider, fetch, seconds, *, stale_seconds=0, force=False):
        with self.store.session() if hasattr(self.store,'session') else nullcontext():
            return self._cached(key,provider,fetch,seconds,stale_seconds=stale_seconds,force=force)

    def _cached(self, key, provider, fetch, seconds, *, stale_seconds=0, force=False):
        now = utcnow()
        old = self.store.get(key)
        if old and old["expires_at"] > now and not force:
            return copy.deepcopy(old["payload"]), {"status": "SUCCESS", "cache": "HIT", "fetched_at": old["fetched_at"].isoformat()}
        token = self.store.claim(key, provider)
        if not token:
            if old and (now-old["fetched_at"]).total_seconds() <= stale_seconds:
                return copy.deepcopy(old["payload"]), {"status": "STALE", "cache": "REFRESH_IN_PROGRESS", "fetched_at": old["fetched_at"].isoformat()}
            return None, {"status": "FAILED", "reason": "Refresh in progress; retry shortly."}
        try:
            if provider=="open_meteo" and old is None:
                self.store.budget("new-model-grids-day",50,86400)
            data = fetch()
            self.store.put(key, provider, data, seconds, token)
            return data, {"status": data.get("status", "SUCCESS"), "cache": "MISS", "fetched_at": data["fetched_at"]}
        except Exception as exc:
            self.store.event(provider, "validated_fetch", "FAILED", 0, error_class=type(exc).__name__, detail=str(exc))
            if old and (now-old["fetched_at"]).total_seconds() <= stale_seconds:
                return copy.deepcopy(old["payload"]), {"status": "STALE", "cache": "STALE_FALLBACK", "fetched_at": old["fetched_at"].isoformat(), "error_class": type(exc).__name__}
            return None, {"status": "FAILED", "error_class": type(exc).__name__, "reason": "Provider or new-grid budget reached. Try a cached location or retry later." if type(exc).__name__=="BudgetExceeded" else "Provider unavailable or validation failed."}
        finally:
            self.store.release(key, token)

    def search(self, query):
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 100 or any(ord(c)<32 for c in query):
            raise ValueError("Search must contain 2–100 characters.")
        # Coordinate entry uses exactly the same validation as the summary API.
        parts = query.split(",")
        if len(parts) == 2:
            try:
                lat, lon = coordinates(*parts)
            except ValueError:
                if all(p.strip().replace(".", "").replace("-", "").isdigit() for p in parts):
                    raise
            else:
                return {"ok": True, "results": [{"key": f"{lat:.4f},{lon:.4f}", "name": f"Coordinates {lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon, "region": None}], "provider": "User-entered coordinates", "coordinate_validation": "Regional bounding box, not a political boundary determination."}
        data, status = self.cached("geocode:" + query.strip().casefold(), "geocoding", lambda: self.providers.search(query), ttl("AIRGUARD_GEOCODE_TTL",86400*7), stale_seconds=86400*30)
        return {"ok": data is not None, **(data or {"results": []}), "provider_status": status}

    def summary(self, lat, lon, name=None, region=None, force=False, defer=False):
        """Read a precomputed summary first; cache expires at hour/day boundaries.

        Scheduler warming uses force=True. A miss uses the existing bounded
        provider path. This does not create a calibrated station forecast.
        """
        lat, lon = coordinates(lat, lon)
        for value, limit in ((name,160),(region,100)):
            if value is not None and (not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value)):
                raise ValueError('Invalid location label.')
        now = utcnow()
        key = self.summary_key(lat,lon,now)
        if not force:
            if defer and hasattr(self.store,'lookup_or_enqueue_summary'):
                hit=self.store.lookup_or_enqueue_summary(key,lat,lon,tomorrow_period(now)[0].astimezone(IST).date().isoformat())
                if hit.get('state'):
                    return self.pending(hit['state'],lat,lon,name,region)
            else:
                hit = self.store.get(key)
            if hit and hit['expires_at'] > now:
                result = copy.deepcopy(hit['payload'])
                if result.get('tomorrow',{}).get('date') == tomorrow_period(now)[0].astimezone(IST).date().isoformat():
                    if name: result['location']['name'] = name
                    if region: result['location']['region'] = region
                    result['response_cache'] = {'status':'HIT','computed_at':result['refreshed_at'],'expires_at':hit['expires_at'].isoformat()}
                    return result
        if defer and not force and hasattr(self.store,'enqueue_summary'):
            state = self.store.enqueue_summary(key,lat,lon)
            return self.pending(state,lat,lon,name,region)
        result = self._build_summary(lat,lon,name,region,force)
        # Cache successful values only; failures must be retried and never
        # remain labelled fresh after the next IST hour or calendar day.
        if result.get('ok'):
            seconds = min(600,remaining_seconds(result,now,ttl('AIRGUARD_AIR_TTL',3600),ttl('AIRGUARD_WEATHER_TTL',7200)))
            if any(isinstance(state,dict) and state.get('status')=='STALE' for state in (result.get('provider_status') or {}).values()):
                seconds = min(seconds, STALE_SUMMARY_SECONDS)
            if seconds < 1: return result
            token = self.store.claim(key,'summary')
            if token:
                try: self.store.put(key,'summary',result,seconds,token)
                finally: self.store.release(key,token)
            result['response_cache'] = {'status':'MISS','computed_at':result['refreshed_at'],'expires_at':(now+timedelta(seconds=seconds)).isoformat()}
        return result

    @staticmethod
    def pending(state,lat,lon,name,region):
        return {'ok':False,'state':state,'retry_after':5,'location':{'key':f'{lat:.4f},{lon:.4f}','lat':lat,'lon':lon,'name':name or 'Selected coordinates','region':region,'timezone':'Asia/Kolkata'},
                'message':'Live providers are being retrieved. No estimated values are shown yet.' if state!='FAILED' else 'Provider retrieval failed. Please retry shortly.'}

    @staticmethod
    def summary_key(lat,lon,now=None):
        hour = (now or utcnow()).astimezone(IST).replace(minute=0,second=0,microsecond=0)
        return 'summary:' + METHOD + ':' + EXPOSURE_VERSION + ':' + digest([lat,lon,hour.isoformat()])

    def run_summary_job(self,lat,lon,token):
        # Check both possible hours at rollover; computation always uses now.
        key = self.summary_key(lat,lon)
        if not self.store.summary_job_owned(key,token):
            key = self.summary_key(lat,lon,utcnow()-timedelta(hours=1))
            if not self.store.summary_job_owned(key,token):
                return {'ok':False,'state':'EXPIRED_JOB'}
        success = False
        try:
            result = self.summary(lat,lon)
            success = bool(result.get('ok'))
            return {'ok':success,'state':'COMPLETE' if success else 'FAILED'}
        finally:
            self.store.finish_summary_job(key,token,success)

    def _build_summary(self, lat, lon, name=None, region=None, force=False):
        lat, lon = coordinates(lat, lon)
        now = utcnow()
        location = {"key": f"{lat:.4f},{lon:.4f}", "lat": lat, "lon": lon, "name": (name or f"Coordinates {lat:.4f}, {lon:.4f}")[:160], "region": region[:100] if region else None, "country": "IN", "timezone": "Asia/Kolkata"}
        self.store.location(location)
        gx, gy = grid(lat, lon)
        # Station cache uses 0.01°, never the 45km model grid.
        work = {
            "air": (f"cams:{METHOD}:{gx},{gy}", "open_meteo", lambda: self.providers.air(gx,gy), ttl("AIRGUARD_AIR_TTL",3600), 6*3600),
            "weather": (f"weather:{gx},{gy}", "weather", lambda: self.providers.weather(gx,gy), ttl("AIRGUARD_WEATHER_TTL",7200), 6*3600),
            "measured": (f"stations:{round(lat,2)},{round(lon,2)}", "openaq", lambda: self.providers.measured(lat,lon), ttl("AIRGUARD_STATION_TTL",1800), 3*3600),
        }
        datasets, states = {}, {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(self.cached, key, provider, fetch, seconds, stale_seconds=stale, force=force): label for label,(key,provider,fetch,seconds,stale) in work.items()}
            for future in as_completed(futures):
                label = futures[future]
                datasets[label], states[label] = future.result()
        air, measured, weather = (datasets.get(p) for p in ("air", "measured", "weather"))
        empty = aggregate([], now-timedelta(hours=24), now)
        current = dict(empty, source_type="unavailable", measured_or_modelled="UNAVAILABLE", source=None, timestamp=None, freshness="UNAVAILABLE", station=None)
        measured_context = copy.deepcopy(measured or {"stations": [], "status": "UNAVAILABLE", "reason": "OpenAQ unavailable."})
        if measured:
            for station in measured_context["stations"]:
                station["distance_km"] = round(distance(lat,lon,station["coordinates"]),2)
                last = parse_time(station["last_observed_at"]) if station.get("last_observed_at") else None
                age = (now-last).total_seconds()/60 if last else float("inf")
                station["freshness"] = "FRESH" if 0 <= age <= get_settings().fresh_minutes else "DELAYED" if 0 <= age <= get_settings().stale_minutes else "STALE"
                # Re-evaluate completeness at request time, not at cache fetch time.
                current_end = now.replace(minute=0,second=0,microsecond=0)
                calc = aggregate(station["rows"], current_end-timedelta(hours=24), current_end, rolling=True)
                station["calculation"] = calc
                # Every contributing pollutant, not just the newest sensor, must be recent.
                contributing = set(calc["sub_indices"])
                recent = {r["pollutant"] for r in station["latest"] if 0 <= (now-parse_time(r["observed_at"])).total_seconds()/60 <= get_settings().stale_minutes}
                if calc["aqi"] is not None and contributing <= recent and age <= get_settings().stale_minutes and station["distance_km"] <= get_settings().openaq_search_radius_m/1000:
                    current = dict(calc, source_type="measured", measured_or_modelled="MEASURED", source="OpenAQ / " + ((station.get("provider") or {}).get("name") or "upstream provider"), timestamp=last.isoformat(), fetched_at=measured["fetched_at"], freshness=station["freshness"], station={k:v for k,v in station.items() if k not in ("rows","calculation")})
                    break
        end = now.astimezone(IST).replace(minute=0,second=0,microsecond=0).astimezone(now.tzinfo)
        if current["aqi"] is None and air:
            calc = aggregate(air["rows"], end-timedelta(hours=24), end, rolling=True)
            current = dict(calc, source_type="modelled_forecast", measured_or_modelled="MODELLED", source="Open-Meteo / CAMS global", timestamp=(end-timedelta(hours=1)).isoformat(), fetched_at=air["fetched_at"], freshness="STALE" if states["air"]["status"] == "STALE" else "FRESH", station=None, fallback_reason="Modelled air-quality estimate — no sufficiently recent nearby station with adequate hourly pollutant data.", model=air["model"], grid=air["grid"])
            if calc["aqi"] is None:
                current["freshness"]="UNAVAILABLE"
        target_start, target_end = tomorrow_period(now)
        tomorrow = dict(aggregate([],target_start,target_end), date=target_start.astimezone(IST).date().isoformat(), source_type="modelled_forecast", provider="open_meteo", model="cams_global", issued_at=None, freshness="UNAVAILABLE", peak_aqi=None, peak_hour=None, lower_exposure_window=None, highest_exposure_window=None)
        timeline = []
        tomorrow.update(forecast_mode='CAMS_BASED_NATIONWIDE',correction_status='NOT_VALIDATED',
            correction_notice='AirGuard station correction is not validated for this location.',cams_baseline_aqi=None,corrected_aqi=None,prediction_interval=None,model_version=None)
        if air:
            tomorrow.update(aggregate(air["rows"],target_start,target_end))
            tomorrow['cams_baseline_aqi']=tomorrow['aqi']
            tomorrow.update(issued_at=air["issued_at"], fetched_at=air["fetched_at"], provider_issued_at=None, freshness="STALE" if states["air"]["status"] == "STALE" else "FRESH", grid=air["grid"], raw_forecast_reference=air["raw_reference"])
            if tomorrow["aqi"] is None:
                tomorrow["freshness"]="UNAVAILABLE"
            for row in air["rows"]:
                at = parse_time(row["time"])
                if end <= at < target_end:
                    calc = aggregate(air["rows"],at-timedelta(hours=23),at+timedelta(hours=1),rolling=True)
                    timeline.append({"time":row["time"], "aqi":calc["aqi"], "category":calc["category"], "status":calc["status"], "dominant_pollutant":calc["dominant_pollutant"], "concentrations":{p:v for p,v in row.items() if p!="time"}, "source_type":"modelled_forecast"})
            day = [r for r in timeline if target_start <= parse_time(r["time"]) < target_end and r["aqi"] is not None]
            if day:
                peak, low = max(day,key=lambda r:r["aqi"]), min(day,key=lambda r:r["aqi"])
                tomorrow.update(peak_aqi=peak["aqi"],peak_hour=peak["time"], range={"min":low["aqi"],"max":peak["aqi"],"meaning":"Expected AQI variation through the day; not a confidence interval"})
                from src.features.exposure import forecast_windows
                tomorrow.update(forecast_windows(air['rows'],target_start,target_end,(weather or {}).get('rows',[])))
            if tomorrow["aqi"] is not None and parse_time(tomorrow["issued_at"]) < target_start:
                tomorrow["forecast_run_id"] = self.store.issue(location,tomorrow,{"forecast":tomorrow,"hourly":timeline,"provider_input":air["raw"],"location":location},air["raw_reference"])
        # Expose only metadata/readings, never the large raw measurement series.
        for station in measured_context["stations"]:
            station.pop("rows",None)
        weather_rows = [r for r in (weather or {}).get("rows",[]) if end <= parse_time(r["time"]) < target_end]
        fires = self.store.fire_context(lat,lon)
        fire_records = [r for r in fires if distance(lat,lon,r) <= 50]
        from src.nationwide.contracts import validate_summary
        return validate_summary({"ok":current["aqi"] is not None or tomorrow["aqi"] is not None,"schema_version":"1.0","location":location,
            "current":current,"tomorrow":tomorrow,"hourly_forecast":timeline,"measured_context":measured_context,
            "weather_context":{"status":states["weather"]["status"],"provider":"Open-Meteo","model":"gfs_seamless","fetched_at":(weather or {}).get("fetched_at"),"units":(weather or {}).get("units",{}),"hourly":weather_rows},
            "fire_context":{"source":"NASA FIRMS","source_type":"satellite_fire_detection","radius_km":50,"detections":fire_records,"meaning":"Stored satellite detections in the last 24h; not AQI, no AQI adjustment.","freshness":"CHECK_OBSERVATION_TIMES"},
            "provider_status":states,"categories":CATEGORIES,"data_quality":{"measured_pollutant_minimum":3,"minimum_valid_hours":16,"missing_CAMS_pollutants":["NH3","Pb"],"native_grid_degrees":.4,"coordinate_scope":"India-region bounding box; geocoding results country-filtered IN"},
            "provenance":{"methodology_version":METHOD,"methodology_source":SOURCE,"current_averaging":"trailing 24h / trailing 8h; minimum 16 valid hourly bins per pollutant",
                "tomorrow_averaging":"IST daily means for 24h pollutants; maximum full trailing 8h CO/O3 mean ending in the day; high O3 uses 1h mathematical bands",
                "forecast":"AirGuard CPCB-style modelled forecast, not an official CPCB forecast", "issue_time_basis":"AirGuard retrieval; upstream model run initialization is not exposed by this API", "attribution":["Open-Meteo.com","Copernicus Atmosphere Monitoring Service (CAMS)","OpenAQ and station-specific upstream providers","NASA FIRMS for satellite fire context"]},"refreshed_at":now.isoformat(),"track_record":self.store.metrics()})
