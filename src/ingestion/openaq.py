"""Station measurements from OpenAQ (API v3).

OpenAQ aggregates readings from government networks and other monitors. A
record from here is labelled ``source = "OpenAQ"`` and
``source_type = "measured"``. It is **never** labelled CPCB, even when OpenAQ
names CPCB as its upstream provider for a station: that relationship is kept as
provenance (``Station.upstream_provider``, ``Station.owner``) and is what the
matching step uses to recognise the same physical monitor arriving twice.

Approach
--------
1. *Discovery.* For each target city, ``GET /v3/locations`` with a coordinate
   and radius, following pagination.
2. *Latest values.* For each location that has reported recently,
   ``GET /v3/locations/{id}/latest``. A latest value is tied back to its sensor
   to learn which pollutant it measures and in which unit, because the latest
   endpoint itself returns only a sensor identifier.

Rate limits
-----------
The free tier allows 60 requests a minute and 2,000 an hour, and OpenAQ warns
that repeatedly exceeding them can lead to a ban. The connector reads
``x-ratelimit-remaining`` after every response and pauses until the window
resets rather than running into a 429. If it is rate limited anyway it stops
and reports the run as partial with whatever it has.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from src import config
from src.ingestion import units
from src.ingestion.base import Batch, CredentialMissing
from src.ingestion.http import HttpClient, HttpError, as_dict, header_int
from src.ingestion.schemas import (
    AirQualityObservation,
    RejectedRecord,
    SourceType,
    Station,
    ValueKind,
    utc_now,
)
from src.ingestion.settings import TARGET_CITIES, Settings, get_settings, secret

LOGGER = config.get_logger(__name__)

SOURCE = "OpenAQ"
BASE_URL = "https://api.openaq.org/v3"
PAGE_LIMIT = 100
MAX_PAGES = 10
MAX_RATE_WAIT_SECONDS = 65.0


def parse_utc(text: Any) -> Optional[datetime]:
    """Parse OpenAQ's ISO-8601 UTC timestamp (``2026-10-08T05:00:00Z``)."""
    if not text:
        return None
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _respect_rate_limit(client: HttpClient, headers: Mapping[str, str]) -> None:
    remaining = header_int(headers, "x-ratelimit-remaining")
    if remaining is None or remaining > 1:
        return
    reset = header_int(headers, "x-ratelimit-reset")
    if reset is None:
        wait = 60.0
    elif reset > 1_000_000_000:  # an epoch timestamp rather than seconds remaining
        wait = max(0.0, reset - utc_now().timestamp())
    else:
        wait = float(reset)
    wait = min(wait + 1.0, MAX_RATE_WAIT_SECONDS)
    LOGGER.info("openaq: rate-limit window nearly spent; pausing %.0fs", wait)
    client.sleep(wait)


def _get(client: HttpClient, path: str, key: str, params: Optional[Dict[str, Any]] = None, label: str = "openaq") -> Dict[str, Any]:
    response = client.get(f"{BASE_URL}{path}", params=params, headers={"X-API-Key": key, "Accept": "application/json"}, label=label)
    payload = as_dict(response.json(), label)
    _respect_rate_limit(client, response.headers)
    return payload


def station_from_location(location: Dict[str, Any], city_hint: Optional[str] = None) -> Station:
    coordinates = location.get("coordinates") or {}
    return Station(
        source=SOURCE,
        source_station_id=str(location.get("id")),
        name=location.get("name"),
        city=location.get("locality") or city_hint,
        country=(location.get("country") or {}).get("code") or "IN",
        latitude=coordinates.get("latitude"),
        longitude=coordinates.get("longitude"),
        timezone=location.get("timezone"),
        owner=(location.get("owner") or {}).get("name"),
        upstream_provider=(location.get("provider") or {}).get("name"),
        metadata={
            "is_monitor": location.get("isMonitor"),
            "is_mobile": location.get("isMobile"),
            "search_city": city_hint,
            "datetime_last_utc": (location.get("datetimeLast") or {}).get("utc"),
            "sensors": {
                str(s.get("id")): {
                    "parameter": (s.get("parameter") or {}).get("name"),
                    "units": (s.get("parameter") or {}).get("units"),
                }
                for s in location.get("sensors") or []
            },
        },
    )


def discover_locations(client: HttpClient, key: str, settings: Settings, cities: Mapping[str, Tuple[float, float]]) -> Tuple[List[Dict[str, Any]], bool]:
    """Find OpenAQ locations around each target city. Returns (locations, partial)."""
    found: Dict[str, Dict[str, Any]] = {}
    partial = False
    for city, (lat, lon) in cities.items():
        for page in range(1, MAX_PAGES + 1):
            params = {"coordinates": f"{lat},{lon}", "radius": settings.openaq_search_radius_m, "limit": PAGE_LIMIT, "page": page}
            try:
                payload = _get(client, "/locations", key, params, label=f"openaq locations {city}")
            except HttpError as exc:
                if exc.status in (401, 403):
                    raise  # a rejected key is a failed run, not a partial one
                partial = True
                LOGGER.warning("openaq: discovery for %s stopped (%s)", city, exc.kind)
                if exc.kind == "rate_limited":
                    return list(found.values()), True
                break
            results = payload.get("results") or []
            for location in results:
                if isinstance(location, dict) and location.get("id") is not None:
                    location["_search_city"] = city
                    found.setdefault(str(location["id"]), location)
            if len(results) < PAGE_LIMIT:
                break
    return list(found.values()), partial


def _recently_active(location: Dict[str, Any], now: datetime, days: int) -> bool:
    last = parse_utc((location.get("datetimeLast") or {}).get("utc"))
    return last is not None and now - last <= timedelta(days=days)


def observations_from_latest(location: Dict[str, Any], results: Iterable[Dict[str, Any]], retrieved_at: datetime) -> Tuple[List[AirQualityObservation], List[RejectedRecord]]:
    """Turn a location's latest values into observations, one per sensor."""
    sensors = {str(s.get("id")): (s.get("parameter") or {}) for s in location.get("sensors") or []}
    station = station_from_location(location, location.get("_search_city"))
    observations: List[AirQualityObservation] = []
    rejected: List[RejectedRecord] = []

    for result in results:
        if not isinstance(result, dict):
            rejected.append(RejectedRecord(SOURCE, "MALFORMED_RECORD", "latest value is not an object", {"record": str(result)[:120]}))
            continue
        sensor_id = str(result.get("sensorsId")) if result.get("sensorsId") is not None else None
        parameter = sensors.get(sensor_id or "", {})
        raw_pollutant = parameter.get("name")
        pollutant = units.canonical_pollutant(raw_pollutant)
        if raw_pollutant and pollutant is None:
            continue  # a non-pollutant sensor (temperature, humidity, particle counts): out of scope, not an error

        when = result.get("datetime") or {}
        coordinates = result.get("coordinates") or {}
        observed_at = parse_utc(when.get("utc"))
        observations.append(
            AirQualityObservation(
                source=SOURCE,
                source_type=SourceType.MEASURED,
                source_station_id=station.source_station_id,
                sensor_id=sensor_id,
                source_record_id=f"{sensor_id}:{when.get('utc')}" if sensor_id else None,
                pollutant=pollutant,
                raw_pollutant=raw_pollutant,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                raw_value=result.get("value"),
                raw_unit=parameter.get("units"),
                value_kind=ValueKind.CONCENTRATION,
                averaging_period="native",
                station_name=station.name, city=station.city,
                latitude=coordinates.get("latitude", station.latitude),
                longitude=coordinates.get("longitude", station.longitude),
                local_timezone=station.timezone,
                provenance={
                    "openaq_location_id": station.source_station_id,
                    "openaq_sensor_id": sensor_id,
                    "upstream_provider": station.upstream_provider,
                    "owner": station.owner,
                    "is_reference_monitor": location.get("isMonitor"),
                    "reported_local_time": when.get("local"),
                },
            )
        )
    return observations, rejected


def collect(
    client: Optional[HttpClient] = None,
    settings: Optional[Settings] = None,
    limit: Optional[int] = None,
    cities: Optional[Mapping[str, Tuple[float, float]]] = None,
) -> Batch:
    """``limit`` caps the number of *locations* whose latest values are fetched."""
    settings = settings or get_settings()
    client = client or HttpClient(settings)
    key = secret("OPENAQ_API_KEY")
    if not key:
        raise CredentialMissing("OPENAQ_API_KEY")

    now = utc_now()
    retrieved_at = now.replace(microsecond=0)
    batch = Batch(source=SOURCE, kind="air_quality")

    locations, batch.partial = discover_locations(client, key, settings, cities or TARGET_CITIES)
    active = [loc for loc in locations if _recently_active(loc, now, settings.openaq_active_within_days)]
    batch.notes.append(f"{len(locations)} locations found near target cities; {len(active)} reported in the last {settings.openaq_active_within_days} days")
    batch.stations = [station_from_location(loc, loc.get("_search_city")) for loc in active]

    for location in active[:limit] if limit else active:
        try:
            payload = _get(client, f"/locations/{location['id']}/latest", key, {"limit": PAGE_LIMIT}, label="openaq latest")
        except HttpError as exc:
            batch.partial = True
            LOGGER.warning("openaq: latest values for location %s failed (%s)", location.get("id"), exc.kind)
            if exc.kind == "rate_limited":
                batch.notes.append("stopped early: rate limited")
                break
            continue
        results = payload.get("results") or []
        batch.retrieved += len(results)
        observations, rejected = observations_from_latest(location, results, retrieved_at)
        batch.records.extend(observations)
        batch.rejected.extend(rejected)

    return batch
