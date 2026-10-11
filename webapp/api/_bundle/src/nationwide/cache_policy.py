"""A cached freshness label cannot outlive its next classification boundary."""
from datetime import timedelta
from src.ingestion.settings import get_settings
from src.nationwide.aqi import IST, parse_time


def remaining_seconds(payload, now, air_ttl=3600, weather_ttl=7200):
    local = now.astimezone(IST)
    deadlines = [(local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)]
    if payload.get('current'):
        deadlines.append((local + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0))
    for key in ('current', 'tomorrow'):
        item = payload.get(key) or {}
        stamp = item.get('fetched_at') or item.get('issued_at')
        if item.get('measured_or_modelled') == 'MEASURED':
            stamp = item.get('timestamp')
            duration = get_settings().fresh_minutes * 60 if item.get('freshness') == 'FRESH' else get_settings().stale_minutes * 60
        else:
            duration = 6 * 3600 if item.get('freshness') == 'STALE' else air_ttl
        if stamp:
            deadlines.append(parse_time(stamp) + timedelta(seconds=duration))
    weather = payload.get('weather_context') or {}
    if weather.get('fetched_at'):
        duration = 6 * 3600 if weather.get('status') == 'STALE' else weather_ttl
        deadlines.append(parse_time(weather['fetched_at']) + timedelta(seconds=duration))
    return max(0, int(min((deadline - now).total_seconds() for deadline in deadlines)) - 1)
