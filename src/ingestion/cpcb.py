"""Official CPCB station data, through the Government of India open-data API.

Source label
------------
Every record from this connector carries ``source = "CPCB/data.gov.in"`` and
``source_type = "measured"``. Nothing else is ever given that label: if this
feed cannot be reached the run fails with "Official measured source
unavailable" and no other provider is relabelled to stand in for it.

Resource discovery
------------------
data.gov.in addresses a dataset by a resource identifier. The identifier used
is configuration (``DATA_GOV_AQI_RESOURCE_ID``), and it is not trusted blindly:
every run reads the metadata the API returns with the data -- the dataset
title, the publishing organisation and the field list -- and refuses to parse
anything that does not describe a CPCB air-quality dataset with the fields this
connector needs. A retired or repurposed identifier therefore fails loudly
instead of being ingested as if it were air quality.

What the numbers are
--------------------
The feed gives a minimum, maximum and average per station and pollutant with a
``last_update`` time. In the releases examined it publishes **no unit**, and
its title describes an index rather than concentrations. This connector
therefore does not assume micrograms per cubic metre. Each value is stored
exactly as received, its ``value_kind`` is ``unknown`` unless the payload
itself supplies a recognised unit, and validation attaches
``UNIT_UNSPECIFIED`` so the record cannot be mistaken for a normalised
concentration downstream.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src import config
from src.ingestion import units
from src.ingestion.base import Batch, CredentialMissing, SourceUnavailable
from src.ingestion.http import HttpClient, HttpError, as_dict
from src.ingestion.schemas import (
    AirQualityObservation,
    RejectedRecord,
    SourceType,
    Station,
    ValueKind,
    utc_now,
)
from src.ingestion.settings import INDIA_TIMEZONE, Settings, get_settings, secret
from src.ingestion.validation import parse_number

LOGGER = config.get_logger(__name__)

SOURCE = "CPCB/data.gov.in"
BASE_URL = "https://api.data.gov.in/resource/{resource_id}"
PAGE_SIZE = 1000
MAX_PAGES = 20

REQUIRED_FIELDS = ("station", "pollutant_id", "last_update")
VALUE_FIELDS = ("pollutant_avg", "avg_value")
TIME_FORMATS = ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")

UNAVAILABLE = "Official measured source unavailable."


def _first(record: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record and record[name] not in (None, ""):
            return record[name]
    return None


def _slug(*parts: Optional[str]) -> Optional[str]:
    cleaned = [re.sub(r"[^a-z0-9]+", "-", str(p).strip().lower()).strip("-") for p in parts if p]
    return "|".join(cleaned) if cleaned else None


def parse_timestamp(text: Any) -> Optional[datetime]:
    """The feed reports Indian Standard Time without saying so; convert to UTC."""
    if not text:
        return None
    for fmt in TIME_FORMATS:
        try:
            local = datetime.strptime(str(text).strip(), fmt).replace(tzinfo=ZoneInfo(INDIA_TIMEZONE))
            return local.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def verify_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Confirm the resource is the CPCB air-quality dataset before parsing it."""
    title = str(payload.get("title", ""))
    fields = [str(f.get("id", "")).lower() for f in payload.get("field", []) if isinstance(f, dict)]
    records = payload.get("records")

    if "air quality" not in title.lower():
        raise SourceUnavailable(f"{UNAVAILABLE} The resource is titled {title[:80]!r}, which is not an air-quality dataset.")
    if not isinstance(records, list):
        raise SourceUnavailable(f"{UNAVAILABLE} The response carries no record list.")

    available = set(fields) or (set(records[0].keys()) if records else set())
    missing = [f for f in REQUIRED_FIELDS if f not in available]
    if available and missing:
        raise SourceUnavailable(f"{UNAVAILABLE} The dataset no longer has the field(s) {missing}.")
    if available and not any(v in available for v in VALUE_FIELDS):
        raise SourceUnavailable(f"{UNAVAILABLE} The dataset has no average-value field.")

    return {
        "dataset_title": title,
        "publisher": payload.get("org") or payload.get("org_type"),
        "dataset_source": payload.get("source"),
        "dataset_updated": payload.get("updated_date"),
        "total_records": payload.get("total"),
    }


def parse_records(records: List[Dict[str, Any]], metadata: Dict[str, Any], resource_id: str, retrieved_at: datetime) -> Batch:
    batch = Batch(source=SOURCE, kind="air_quality", retrieved=len(records))
    stations: Dict[str, Station] = {}

    for record in records:
        if not isinstance(record, dict):
            batch.rejected.append(RejectedRecord(SOURCE, "MALFORMED_RECORD", "record is not an object", {"record": str(record)[:120]}))
            continue

        station_name = _first(record, "station")
        city, state = _first(record, "city"), _first(record, "state")
        station_id = _slug(state, city, station_name) if station_name else None
        latitude, longitude = parse_number(_first(record, "latitude")), parse_number(_first(record, "longitude"))

        raw_pollutant = _first(record, "pollutant_id")
        raw_unit = _first(record, "pollutant_unit", "unit")
        if raw_unit and str(raw_unit).strip().upper() in {"NA", "N/A", "NULL"}:
            raw_unit = None

        if station_id and station_id not in stations:
            stations[station_id] = Station(
                source=SOURCE, source_station_id=station_id, name=station_name, city=city,
                state=str(state).replace("_", " ") if state else None, country="IN",
                latitude=latitude, longitude=longitude, timezone=INDIA_TIMEZONE,
                owner="CPCB / State Pollution Control Board", upstream_provider="CPCB",
            )

        batch.records.append(
            AirQualityObservation(
                source=SOURCE,
                source_type=SourceType.MEASURED,
                source_station_id=station_id,
                pollutant=units.canonical_pollutant(raw_pollutant),
                raw_pollutant=raw_pollutant,
                observed_at=parse_timestamp(_first(record, "last_update")),
                retrieved_at=retrieved_at,
                raw_value=_first(record, *VALUE_FIELDS),
                raw_min=_first(record, "pollutant_min", "min_value"),
                raw_max=_first(record, "pollutant_max", "max_value"),
                raw_unit=raw_unit,
                value_kind=ValueKind.CONCENTRATION if units.canonical_unit(raw_unit) else ValueKind.UNKNOWN,
                averaging_period="unspecified",
                station_name=station_name, city=city, state=state,
                latitude=latitude, longitude=longitude, local_timezone=INDIA_TIMEZONE,
                provenance={
                    **metadata,
                    "resource_id": resource_id,
                    "statistic": "average, with provider minimum and maximum",
                    "reported_local_time": _first(record, "last_update"),
                },
            )
        )

    batch.stations = list(stations.values())
    return batch


def collect(client: Optional[HttpClient] = None, settings: Optional[Settings] = None, limit: Optional[int] = None) -> Batch:
    settings = settings or get_settings()
    client = client or HttpClient(settings)
    key = secret("DATA_GOV_API_KEY")
    if not key:
        raise CredentialMissing("DATA_GOV_API_KEY")

    url = BASE_URL.format(resource_id=settings.data_gov_resource_id)
    page_size = min(PAGE_SIZE, limit) if limit else PAGE_SIZE

    records: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    partial = False
    offset = 0

    for page in range(MAX_PAGES):
        params = {"api-key": key, "format": "json", "offset": offset, "limit": page_size}
        try:
            payload = as_dict(client.get(url, params=params, label="cpcb data.gov.in").json(), "cpcb data.gov.in")
        except HttpError as exc:
            if page == 0:
                raise SourceUnavailable(f"{UNAVAILABLE} {exc}") from None
            partial = True
            LOGGER.warning("cpcb: page %d failed (%s); keeping the %d records already retrieved", page + 1, exc.kind, len(records))
            break

        if str(payload.get("status", "ok")).lower() == "error":
            raise SourceUnavailable(f"{UNAVAILABLE} data.gov.in reported: {str(payload.get('message', 'error'))[:160]}")
        if page == 0:
            metadata = verify_metadata(payload)

        page_records = payload.get("records") or []
        records.extend(page_records)
        offset += len(page_records)

        total = parse_number(payload.get("total")) or 0
        if not page_records or offset >= total or (limit and len(records) >= limit):
            break
    else:
        partial = True

    # Stamped when the last page arrived: never earlier than the moment the data was really held.
    batch = parse_records(records[:limit] if limit else records, metadata, settings.data_gov_resource_id, utc_now().replace(microsecond=0))
    batch.partial = partial
    batch.notes.append(f"dataset: {metadata.get('dataset_title')!r}, last updated {metadata.get('dataset_updated')}")
    return batch
