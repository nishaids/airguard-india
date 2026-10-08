"""Active-fire detections from NASA FIRMS.

A fire detection is **not** an air-quality measurement. Every record from this
connector is labelled ``source_type = "satellite_fire_detection"`` and lives in
its own table; it can become a model input (fires upwind) but is never shown as
air quality.

Feeds
-----
The VIIRS near-real-time products from NOAA-20 and NOAA-21 are used
(``VIIRS_NOAA20_NRT``, ``VIIRS_NOAA21_NRT``). The older Suomi-NPP and MODIS
feeds are deliberately not depended on, so that the pipeline does not have to
be rebuilt when an ageing platform is retired. The list is configuration.

The credential
--------------
FIRMS puts the MAP_KEY in the URL *path*. The HTTP client never logs a URL, and
``settings.redact`` masks that path segment in any error text, including text
echoed back by the provider.

Request shape
-------------
``/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}``, with
``DAY_RANGE`` between 1 and 5. A problem may be reported as plain text instead
of CSV, so a body whose first line is not the expected header is treated as a
failure whatever the status code.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from src import config
from src.ingestion.base import Batch, CredentialMissing
from src.ingestion.http import HttpClient, HttpError
from src.ingestion.schemas import FireDetection, record_hash, utc_now
from src.ingestion.settings import INDIA_BBOX, Settings, get_settings, redact, secret
from src.ingestion.validation import parse_number

LOGGER = config.get_logger(__name__)

SOURCE = "NASA FIRMS"
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}


def parse_acquired(date_text: Any, time_text: Any) -> Optional[datetime]:
    """FIRMS gives a UTC date and an ``HHMM`` time that drops leading zeros."""
    if not date_text or time_text in (None, ""):
        return None
    try:
        clock = str(int(float(time_text))).zfill(4)
        return datetime.strptime(f"{date_text} {clock}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def parse_csv(text: str, product: str, retrieved_at: datetime) -> List[FireDetection]:
    """Parse one FIRMS CSV response. Raises ``HttpError`` if it is not CSV at all."""
    body = (text or "").strip()
    header = body.splitlines()[0].lower() if body else ""
    if "latitude" not in header or "longitude" not in header:
        reason = redact(" ".join(body.split())[:160]) or "empty response"
        raise HttpError(f"firms {product}: provider did not return detections ({reason})", kind="malformed")

    detections: List[FireDetection] = []
    for row in csv.DictReader(io.StringIO(body)):
        latitude, longitude = parse_number(row.get("latitude")), parse_number(row.get("longitude"))
        acquired = parse_acquired(row.get("acq_date"), row.get("acq_time"))
        raw_confidence = (row.get("confidence") or "").strip()
        detections.append(
            FireDetection(
                source=SOURCE,
                product=product,
                satellite=(row.get("satellite") or "").strip() or None,
                instrument=(row.get("instrument") or "").strip() or None,
                latitude=latitude,
                longitude=longitude,
                acquired_at=acquired,
                retrieved_at=retrieved_at,
                confidence=CONFIDENCE.get(raw_confidence.lower(), raw_confidence or None),
                frp_mw=parse_number(row.get("frp")),
                brightness_k=parse_number(row.get("bright_ti4") or row.get("brightness")),
                day_night=(row.get("daynight") or "").strip() or None,
                version=(row.get("version") or "").strip() or None,
                source_record_id=record_hash(product, row.get("latitude"), row.get("longitude"), row.get("acq_date"), row.get("acq_time"), row.get("satellite")),
                provenance={"raw_confidence": raw_confidence, "scan": row.get("scan"), "track": row.get("track"), "bright_ti5": row.get("bright_ti5")},
            )
        )
    return detections


def collect(
    client: Optional[HttpClient] = None,
    settings: Optional[Settings] = None,
    limit: Optional[int] = None,
    bbox: Tuple[float, float, float, float] = INDIA_BBOX,
) -> Batch:
    settings = settings or get_settings()
    client = client or HttpClient(settings)
    key = secret("NASA_FIRMS_MAP_KEY")
    if not key:
        raise CredentialMissing("NASA_FIRMS_MAP_KEY")

    retrieved_at = utc_now().replace(microsecond=0)
    area = ",".join(f"{v:g}" for v in bbox)
    days = max(1, min(5, settings.firms_day_range))
    batch = Batch(source=SOURCE, kind="fire")
    failures: List[str] = []

    for product in settings.firms_sources:
        url = f"{BASE_URL}/{key}/{product}/{area}/{days}"
        try:
            detections = parse_csv(client.get(url, label=f"firms {product}").text, product, retrieved_at)
        except HttpError as exc:
            failures.append(f"{product}: {exc}")
            LOGGER.warning("firms: %s failed (%s)", product, exc.kind)
            continue
        batch.retrieved += len(detections)
        batch.records.extend(detections)
        batch.notes.append(f"{product}: {len(detections)} detections in the last {days} day(s) inside {area}")

    if failures and len(failures) == len(settings.firms_sources):
        raise HttpError("; ".join(failures), kind="http_error")
    if failures:
        batch.partial = True
        batch.notes.extend(failures)
    if limit:
        batch.records = batch.records[:limit]
    return batch
