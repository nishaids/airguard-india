"""Bounded, thread-local SSL connections; shared DB cache and budgets.

No application connection pool, named prepared statements or session locks.
Compatible with session and transaction Supavisor pooling. SQL stays parameterized.
"""
from __future__ import annotations

import hashlib
import json
import uuid
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from psycopg2.extras import Json, RealDictCursor, execute_values
from src.ingestion.db import connect
from src.nationwide.aqi import METHOD


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


class BudgetExceeded(Exception):
    pass


class Store:
    def __init__(self):
        self._scope = threading.local()

    @contextmanager
    def session(self):
        """Reuse one client connection within a thread's bounded request scope.

        Each cursor still commits/rolls back separately. Nothing survives the
        outer scope, and concurrent provider workers never share a connection.
        """
        self._scope.depth = getattr(self._scope, 'depth', 0) + 1
        try:
            yield self
        finally:
            self._scope.depth -= 1
            if not self._scope.depth:
                connection = getattr(self._scope, 'connection', None)
                if connection is not None:
                    connection.close()
                    del self._scope.connection

    def enqueue_summary(self, key, lat, lon):
        with self.cursor() as cur:
            cur.execute('select airguard.enqueue_summary(%s,%s,%s) state', (key,lat,lon))
            return cur.fetchone()['state']

    def lookup_or_enqueue_summary(self,key,lat,lon,target_date):
        with self.cursor() as cur:
            cur.execute("""with cached as (
                select payload,fetched_at,expires_at from airguard.cache_metadata
                where cache_key=%s and payload is not null and expires_at>now()
                and payload->'tomorrow'->>'date'=%s)
                select payload,fetched_at,expires_at,null::text state from cached
                union all select null,null,null,airguard.enqueue_summary(%s,%s,%s)
                where not exists(select 1 from cached)""", (key,target_date,key,lat,lon))
            return dict(cur.fetchone())

    def summary_job_owned(self, key, token):
        with self.cursor() as cur:
            cur.execute("select 1 from airguard.cache_metadata where cache_key=%s and lease_token=%s and lease_until>now()", ('queue:'+key,token))
            return bool(cur.fetchone())

    def finish_summary_job(self, key, token, success):
        with self.cursor() as cur:
            cur.execute("update airguard.cache_metadata set payload=%s,lease_until=now()+interval '30 seconds' where cache_key=%s and lease_token=%s", (Json({'status':'COMPLETE' if success else 'FAILED'}),'queue:'+key,token))

    def research_snapshot(self, payload, lat, lon, station_pk=None):
        from src.research.storage import ResearchStore
        return ResearchStore(self).snapshot(payload,lat,lon,station_pk)

    @contextmanager
    def cursor(self):
        scoped = getattr(self._scope, 'depth', 0) > 0
        connection = getattr(self._scope, 'connection', None) if scoped else None
        if connection is None or connection.closed:
            connection = connect()
            if scoped: self._scope.connection = connection
        try:
            with connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SET LOCAL statement_timeout='8s'")
                yield cursor
        finally:
            if not scoped: connection.close()

    def get(self, key):
        with self.cursor() as cur:
            cur.execute("select payload,fetched_at,expires_at from airguard.cache_metadata where cache_key=%s", (key,))
            row = cur.fetchone()
            return dict(row) if row and row["payload"] is not None else None

    def claim(self, key, provider):
        token = str(uuid.uuid4())
        with self.cursor() as cur:
            cur.execute("""insert into airguard.cache_metadata(cache_key,provider,lease_until,lease_token)
                values(%s,%s,now()+interval '360 seconds',%s) on conflict(cache_key) do update
                set lease_until=excluded.lease_until,lease_token=excluded.lease_token
                where airguard.cache_metadata.lease_until is null or airguard.cache_metadata.lease_until<now()
                returning cache_key""", (key, provider, token))
            return token if cur.fetchone() else None

    def release(self, key, token):
        with self.cursor() as cur:
            cur.execute("update airguard.cache_metadata set lease_until=null where cache_key=%s and lease_token=%s", (key, token))

    def put(self, key, provider, payload, ttl, token):
        with self.cursor() as cur:
            cur.execute("""update airguard.cache_metadata set payload=%s,fetched_at=now(),expires_at=now()+%s*interval '1 second',
                lease_until=null where cache_key=%s and lease_token=%s""", (Json(payload), ttl, key, token))

    def budget(self, bucket, limit, seconds=3600):
        now = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(int(now.timestamp() // seconds) * seconds, timezone.utc)
        with self.cursor() as cur:
            cur.execute("""insert into airguard.request_budgets(bucket,window_start,used) values(%s,%s,1)
                on conflict(bucket) do update set window_start=excluded.window_start,
                used=case when airguard.request_budgets.window_start=excluded.window_start then airguard.request_budgets.used+1 else 1 end
                where airguard.request_budgets.window_start<>excluded.window_start or airguard.request_budgets.used<%s returning used""",
                (bucket, start, limit))
            if not cur.fetchone():
                raise BudgetExceeded(bucket)

    def budget_requests(self,bucket):
        now=datetime.now(timezone.utc)
        start=datetime.fromtimestamp(int(now.timestamp()//60)*60,timezone.utc)
        with self.cursor() as cur:
            cur.execute("""with client as (
                insert into airguard.request_budgets(bucket,window_start,used) values(%s,%s,1)
                on conflict(bucket) do update set window_start=excluded.window_start,
                used=case when airguard.request_budgets.window_start=excluded.window_start then airguard.request_budgets.used+1 else 1 end
                where airguard.request_budgets.window_start<>excluded.window_start or airguard.request_budgets.used<60 returning used
              ), shared as (
                insert into airguard.request_budgets(bucket,window_start,used) values('requests-all',%s,1)
                on conflict(bucket) do update set window_start=excluded.window_start,
                used=case when airguard.request_budgets.window_start=excluded.window_start then airguard.request_budgets.used+1 else 1 end
                where airguard.request_budgets.window_start<>excluded.window_start or airguard.request_budgets.used<120 returning used)
              select exists(select 1 from client) and exists(select 1 from shared) accepted""", (bucket,start,start))
            if not cur.fetchone()['accepted']: raise BudgetExceeded(bucket)

    def event(self, provider, operation, status, latency, count=0, http_status=None, error_class=None, detail=None):
        from src.ingestion.settings import redact
        with self.cursor() as cur:
            cur.execute("""insert into airguard.provider_events(provider,operation,status,latency_ms,record_count,http_status,error_class,detail)
                values(%s,%s,%s,%s,%s,%s,%s,%s)""", (provider, operation, status, latency, count, http_status, error_class, redact(detail)[:1000] if detail else None))

    def location(self, location):
        with self.cursor() as cur:
            cur.execute("""insert into airguard.locations(location_key,name,region,latitude,longitude,metadata)
                values(%s,%s,%s,%s,%s,%s) on conflict(location_key) do update set requested_at=now(),name=excluded.name,
                region=coalesce(excluded.region,airguard.locations.region)""",
                (location["key"], location["name"], location.get("region"), location["lat"], location["lon"], Json(location)))

    def records(self, rows):
        if not rows:
            return 0
        columns = ("record_key", "provider", "source_type", "model", "station_pk", "sensor_id", "latitude", "longitude", "pollutant", "raw_value", "raw_unit", "normalized_value", "normalized_unit", "valid_at", "issued_at", "provider_issued_at", "fetched_at", "quality_state", "provenance", "methodology_version")
        with self.cursor() as cur:
            values = [tuple(Json(r[c]) if c == "provenance" else r.get(c) for c in columns) for r in rows]
            execute_values(cur, "insert into airguard.environmental_records(" + ",".join(columns) + ") values %s on conflict(record_key) do nothing", values, page_size=2000)
            return cur.rowcount

    def weather(self, payload, lat, lon):
        now = datetime.fromisoformat(payload["fetched_at"])
        columns = ("temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_direction_10m", "surface_pressure", "boundary_layer_height")
        with self.cursor() as cur:
            values = []
            for row in payload["rows"]:
                at = datetime.fromisoformat(row["time"])
                if at < now:
                    continue
                values.append(("Open-Meteo", "gfs_seamless", f"{lat},{lon}", lat, lon, now.replace(minute=0, second=0, microsecond=0), now, at,
                    (at-now).total_seconds()/3600, *(row.get(c) for c in columns), Json(payload["units"]), "ok",
                    Json({"endpoint": "https://api.open-meteo.com/v1/forecast", "model": "gfs_seamless", "source_type": "weather_forecast", "provider_issued_at": None, "raw_reference": payload["raw_reference"], "attribution": "Weather data by Open-Meteo.com"})))
            if values:
                execute_values(cur, "insert into airguard.weather_forecasts(source_id,model,location_label,latitude,longitude,vintage_at,retrieved_at,valid_at,lead_time_hours," + ",".join(columns) + ",units,quality_state,provenance) values %s on conflict do nothing", values)

    def fire_context(self, lat, lon):
        with self.cursor() as cur:
            cur.execute("""select latitude,longitude,acquired_at,product,confidence from airguard.fire_detections
                where acquired_at>now()-interval '24 hours' and latitude between %s and %s and longitude between %s and %s
                order by acquired_at desc limit 100""", (lat-.5,lat+.5,lon-.6,lon+.6))
            return [dict(r,acquired_at=r["acquired_at"].isoformat()) for r in cur.fetchall()]

    def station(self, metadata):
        with self.cursor() as cur:
            cur.execute("""insert into airguard.stations(source_id,source_station_id,name,latitude,longitude,country,owner,upstream_provider,metadata)
                values('OpenAQ',%s,%s,%s,%s,'IN',%s,%s,%s) on conflict(source_id,source_station_id) do update
                set last_seen_at=now(),metadata=excluded.metadata returning station_pk""",
                (str(metadata["id"]), metadata.get("name"), metadata["coordinates"]["latitude"], metadata["coordinates"]["longitude"],
                 (metadata.get("owner") or {}).get("name"), (metadata.get("provider") or {}).get("name"), Json(metadata)))
            return cur.fetchone()["station_pk"]

    def sensor(self, station_pk, sensor):
        with self.cursor() as cur:
            cur.execute("""insert into airguard.sensors(sensor_id,station_pk,pollutant,raw_unit,metadata,fetched_at) values(%s,%s,%s,%s,%s,now())
                on conflict(sensor_id) do update set metadata=excluded.metadata,fetched_at=now()""",
                (str(sensor["id"]), station_pk, sensor["parameter"]["name"], sensor["parameter"]["units"], Json(sensor)))

    def issue(self, location, forecast, artifact, reference):
        with self.cursor() as cur:
            cur.execute("""insert into airguard.forecast_runs(location_key,latitude,longitude,region,provider,model,issued_at,provider_issued_at,
                target_start,target_end,predicted_aqi,predicted_category,dominant_pollutant,qualifier,raw_forecast_reference,methodology_version,artifact)
                values(%s,%s,%s,%s,'open_meteo','cams_global',%s,null,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(location_key,target_start,raw_forecast_reference,methodology_version) do nothing returning id""",
                (location["key"], location["lat"], location["lon"], location.get("region"), forecast["issued_at"], forecast["window_start"], forecast["window_end"],
                 forecast["aqi"], (forecast.get("category") or {}).get("label"), forecast["dominant_pollutant"], forecast["qualifier"], reference, METHOD, Json(artifact)))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute("select id,issued_at from airguard.forecast_runs where location_key=%s and target_start=%s and raw_forecast_reference=%s and methodology_version=%s",
                        (location["key"], forecast["window_start"], reference, METHOD))
            existing=cur.fetchone()
            # The saved artifact's first issue time remains the public issue time,
            # even when an upstream refetch yields byte-identical model inputs.
            forecast["issued_at"]=existing["issued_at"].isoformat()
            return existing["id"]

    def status(self):
        with self.cursor() as cur:
            cur.execute("select distinct on(provider) provider,operation,status,created_at,record_count,http_status,error_class from airguard.provider_events order by provider,created_at desc")
            rows=[dict(r, created_at=r["created_at"].isoformat()) for r in cur.fetchall()]
            cur.execute("""select distinct on(source_id) source_id as provider,status,finished_at as created_at,
                accepted as record_count from airguard.ingestion_runs where source_id in('CPCB/data.gov.in','NASA FIRMS')
                order by source_id,started_at desc""")
            rows.extend(dict(r,created_at=r["created_at"].isoformat() if r["created_at"] else None,operation="legacy_ingestion",freshness="STALE" if r["created_at"] and datetime.now(timezone.utc)-r["created_at"]>timedelta(hours=3) else "RECENT") for r in cur.fetchall())
            return rows

    def popular(self, limit=3):
        with self.cursor() as cur:
            cur.execute("select location_key as key,name,region,latitude as lat,longitude as lon from airguard.locations order by requested_at desc limit %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def metrics(self):
        with self.cursor() as cur:
            cur.execute("""select coalesce(f.region,'Unspecified') as region,f.predicted_category,
                case when v.lead_hours<12 then '<12h' when v.lead_hours<24 then '12-24h' else '24h+' end as lead,
                count(*) as n,avg(abs(v.error)) as mae,sqrt(avg(v.error*v.error)) as rmse,avg(v.error) as bias,
                avg((v.category_index=v.predicted_category_index)::int)::float as category_accuracy,
                avg((abs(v.category_index-v.predicted_category_index)<=1)::int)::float as within_one_category
                from airguard.forecast_verifications v join airguard.forecast_runs f on f.id=v.forecast_run_id
                where v.verified_at>now()-interval '30 days' group by 1,2,3""")
            return [dict(r) for r in cur.fetchall()]
