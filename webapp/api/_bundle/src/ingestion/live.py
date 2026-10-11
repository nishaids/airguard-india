"""Read the stored live feed. Freshness is evaluated at request time, never cached in DB."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.ingestion.db import PostgresStore
from src.ingestion.schemas import utc_now
from src.ingestion.settings import TARGET_CITIES, get_settings, redact
from src.ingestion.validation import classify_freshness


def _rows(store, sql, params=()):
    from psycopg2.extras import RealDictCursor

    with store.connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def _public(value: Any):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _public(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public(v) for v in value]
    return redact(value) if isinstance(value, str) else value


def snapshot(city: str | None = None, store=None, now=None):
    """Bounded public samples and full source counts, from one read-only DB snapshot."""
    if city and city not in TARGET_CITIES:
        raise ValueError("Unknown city")
    now = now or utc_now()
    settings = get_settings()
    own = store is None
    store = store or PostgresStore()
    try:
        with store.connection:
            with store.connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '10000ms'")
            sources = _rows(store, """
                select r.source_id, r.display_name, r.source_type, r.is_official, r.attribution, r.homepage,
                  j.status as last_run_status, j.started_at, j.finished_at, j.error,
                  j.retrieved, j.accepted, j.written, j.duplicates, j.notes
                from airguard.source_registry r
                left join lateral (select * from airguard.ingestion_runs i
                  where i.source_id=r.source_id order by started_at desc limit 1) j on true
                where r.source_id <> 'CAMS/Open-Meteo' order by r.source_id
            """)
            # A successful request may contain old readings. Count current usable measurements separately.
            observations = _rows(store, """
                select distinct on (o.source_id, o.source_station_id, o.pollutant, o.averaging_period)
                  o.source_id, o.source_type, o.source_station_id, s.name as station_name, s.city,
                  s.latitude, s.longitude, s.upstream_provider, s.metadata->>'is_monitor' as is_monitor,
                  o.pollutant, o.averaging_period, o.value_kind, o.raw_value, o.raw_unit, o.normalized_value, o.normalized_unit,
                  o.observed_at, o.retrieved_at, o.quality_state, o.use_for_modelling, o.provenance,
                  coalesce((select jsonb_agg(f.code) from airguard.data_quality_flags f
                    where f.observation_id=o.observation_id), '[]'::jsonb) as quality_flags
                from airguard.air_quality_observations o
                left join airguard.stations s using (station_pk)
                where (%s::text is null or s.city=%s or s.metadata->>'search_city'=%s)
                order by o.source_id, o.source_station_id, o.pollutant, o.averaging_period, o.observed_at desc
            """, (city, city, city))
            for row in observations:
                row['freshness'] = classify_freshness(row['observed_at'], now, settings).value
                row['age_minutes'] = round((now - row['observed_at']).total_seconds() / 60, 1)
                row['usable_now'] = (row['source_type'] == 'measured' and row['freshness'] in ('fresh', 'delayed') and row['use_for_modelling']
                                     and row['normalized_value'] is not None)
            weather = _rows(store, """
                select distinct on (location_label, model) source_id, model, location_label,
                  issued_at, retrieved_at, valid_at, temperature_2m, relative_humidity_2m,
                  precipitation, wind_speed_10m, wind_direction_10m, surface_pressure,
                  boundary_layer_height, units, quality_state, provenance
                from airguard.weather_forecasts
                where valid_at >= %s and retrieved_at <= %s
                  and (%s::text is null or location_label=%s)
                order by location_label, model, retrieved_at desc, valid_at asc
            """, (now, now, city, city))
            for row in weather:
                row['freshness'] = classify_freshness(row['retrieved_at'], now, settings).value
            # Fire context is regional; city selection intentionally does not turn the bounding box into a city count.
            fires = _rows(store, """
                select count(*) as count_last_24h, max(acquired_at) as latest_acquired_at,
                  max(retrieved_at) as latest_retrieved_at
                from airguard.fire_detections where acquired_at between %s and %s
            """, (now - timedelta(hours=24), now))[0]
            totals = _rows(store, """
                select source_id, count(*) as stored, max(retrieved_at) as latest_retrieved_at
                  from airguard.air_quality_observations group by source_id
                union all select source_id, count(*), max(retrieved_at)
                  from airguard.weather_forecasts group by source_id
                union all select source_id, count(*), max(retrieved_at)
                  from airguard.fire_detections group by source_id
            """)
            totals = {r['source_id']: r for r in totals}
            for source in sources:
                source.update(totals.get(source['source_id'], {'stored': 0, 'latest_retrieved_at': None}))
                relevant = [o for o in observations if o['source_id'] == source['source_id']]
                source['latest_measurements'] = len(relevant)
                source['usable_measurements_now'] = sum(o['usable_now'] for o in relevant)
                source['freshness_counts'] = {label: sum(o['freshness'] == label for o in relevant)
                    for label in ('fresh', 'delayed', 'stale', 'unavailable')}
            observations.sort(key=lambda r: (not r['usable_now'], -r['observed_at'].timestamp()))
            result = {
                'ok': True, 'generated_at': now, 'city': city, 'cities': list(TARGET_CITIES),
                'freshness_thresholds': {'fresh_minutes': settings.fresh_minutes,
                    'stale_minutes': settings.stale_minutes, 'unavailable_hours': settings.unavailable_hours},
                'sources': sources, 'measurements': observations[:30], 'weather': weather,
                'fires': {'source_id': 'NASA FIRMS', 'source_type': 'satellite_fire_detection',
                    'scope': 'Regional bounding box 68,6,97.5,37.5; includes neighbouring countries', **fires},
                'prediction': {'ready': False, 'message':
                    'Stored observations and context are not yet connected to a validated tomorrow-AQI model.'},
            }
        return _public(result)
    finally:
        if own:
            store.close()
