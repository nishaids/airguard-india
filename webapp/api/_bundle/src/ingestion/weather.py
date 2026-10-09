"""Forecast meteorology from Open-Meteo.

Why every retrieval is kept
---------------------------
A model that predicts tomorrow's air may use tomorrow's *forecast* weather,
because that forecast exists today. It may not use tomorrow's *observed*
weather, because nobody has it yet. If a stored forecast were overwritten when
a newer one arrived, the archive would slowly turn into near-observations, and
a model trained on it would look better in testing than it can ever be in use.

So a forecast row is identified by its valid hour **and the moment it was
retrieved**. A later retrieval of the same hour is a new row. Nothing here is
ever updated in place. To reconstruct what was known at a past issue time, read
the rows whose ``retrieved_at`` is the latest one not after that time.

Issue time
----------
``retrieved_at`` is always recorded and is the leakage-safe anchor: it is, by
construction, a time at which the forecast was available. ``issued_at`` is the
weather model's own run-initialisation time, read from the provider's model
metadata when it publishes one, and left empty when it does not rather than
guessed.

Model choice
------------
The default is ``gfs_seamless``. It was chosen because it supplies
boundary-layer height for India; ``ecmwf_ifs025`` was checked and returns none.
The model is configuration (``AIRGUARD_WEATHER_MODEL``) and is stored on every
row.

This is a third-party redistribution of national weather-model output, not an
official Indian meteorological source, and it is labelled accordingly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src import config
from src.ingestion.base import Batch
from src.ingestion.http import HttpClient, HttpError
from src.ingestion.schemas import RejectedRecord, WeatherForecast, utc_now
from src.ingestion.settings import TARGET_CITIES, Settings, get_settings
from src.ingestion.validation import parse_number

LOGGER = config.get_logger(__name__)

SOURCE = "Open-Meteo"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
METADATA_URL = "https://api.open-meteo.com/data/{dataset}/static/meta.json"

VARIABLES: Tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "boundary_layer_height",
)

#: Which metadata document describes the run behind each model option. Only
#: pairings that have been checked against the live service are listed; a model
#: missing from here simply gets no ``issued_at``.
RUN_METADATA = {"gfs_seamless": "ncep_gfs013", "ecmwf_ifs025": "ecmwf_ifs025"}


def model_run_time(client: HttpClient, model: str) -> Tuple[Optional[datetime], Dict[str, Any]]:
    """Best-effort lookup of the latest model run's initialisation time."""
    dataset = RUN_METADATA.get(model)
    if dataset is None:
        return None, {"issued_at_basis": "provider publishes no run time for this model option"}
    try:
        meta = client.get(METADATA_URL.format(dataset=dataset), label="open-meteo model metadata").json()
        initialised = parse_number(meta.get("last_run_initialisation_time"))
        available = parse_number(meta.get("last_run_availability_time"))
    except (HttpError, AttributeError):
        return None, {"issued_at_basis": "model metadata could not be read"}
    if not initialised:
        return None, {"issued_at_basis": "model metadata carried no run time"}
    return (
        datetime.fromtimestamp(initialised, timezone.utc),
        {
            "issued_at_basis": f"last_run_initialisation_time of {dataset}",
            "run_available_at": datetime.fromtimestamp(available, timezone.utc).isoformat() if available else None,
        },
    )


def parse_forecast(
    payload: Any,
    locations: Mapping[str, Tuple[float, float]],
    model: str,
    retrieved_at: datetime,
    issued_at: Optional[datetime],
    run_provenance: Dict[str, Any],
) -> Batch:
    batch = Batch(source=SOURCE, kind="weather")
    blocks = payload if isinstance(payload, list) else [payload]
    labels = list(locations.keys())

    if len(blocks) != len(labels):
        raise HttpError(f"open-meteo: asked for {len(labels)} locations and received {len(blocks)}", kind="malformed")

    for label, block in zip(labels, blocks):
        hourly = (block or {}).get("hourly") if isinstance(block, dict) else None
        if not isinstance(hourly, dict) or "time" not in hourly:
            batch.rejected.append(RejectedRecord(SOURCE, "MALFORMED_RECORD", f"no hourly block for {label}", {"location": label}))
            continue
        units = block.get("hourly_units") or {}
        requested_lat, requested_lon = locations[label]
        skipped_past = 0

        for index, stamp in enumerate(hourly["time"]):
            epoch = parse_number(stamp)
            if epoch is None:
                batch.rejected.append(RejectedRecord(SOURCE, "MISSING_TIMESTAMP", "forecast hour has no usable time", {"location": label, "time": stamp}))
                continue
            valid_at = datetime.fromtimestamp(epoch, timezone.utc)
            lead = (valid_at - retrieved_at).total_seconds() / 3600.0
            batch.retrieved += 1
            if lead < 0:
                skipped_past += 1  # hours already past are not forecasts and are not stored
                continue
            values = {
                name: parse_number(hourly[name][index]) if name in hourly and index < len(hourly[name]) else None
                for name in VARIABLES
            }
            batch.records.append(
                WeatherForecast(
                    source=SOURCE,
                    model=model,
                    location_label=label,
                    latitude=requested_lat,
                    longitude=requested_lon,
                    valid_at=valid_at,
                    retrieved_at=retrieved_at,
                    issued_at=issued_at,
                    lead_time_hours=round(lead, 2),
                    variables=values,
                    units={name: units.get(name, "") for name in VARIABLES},
                    provenance={
                        **run_provenance,
                        "grid_latitude": block.get("latitude"),
                        "grid_longitude": block.get("longitude"),
                        "grid_elevation_m": block.get("elevation"),
                    },
                )
            )
        if skipped_past:
            batch.notes.append(f"{label}: {skipped_past} past hours not stored")
    return batch


def collect(
    client: Optional[HttpClient] = None,
    settings: Optional[Settings] = None,
    limit: Optional[int] = None,
    locations: Optional[Mapping[str, Tuple[float, float]]] = None,
) -> Batch:
    """``limit`` caps the number of *locations* requested."""
    settings = settings or get_settings()
    client = client or HttpClient(settings)
    locations = dict(locations or TARGET_CITIES)
    if limit:
        locations = dict(list(locations.items())[:limit])

    retrieved_at = utc_now().replace(microsecond=0)
    issued_at, run_provenance = model_run_time(client, settings.weather_model)

    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat, _ in locations.values()),
        "longitude": ",".join(f"{lon:.4f}" for _, lon in locations.values()),
        "hourly": ",".join(VARIABLES),
        "forecast_days": settings.weather_forecast_days,
        "models": settings.weather_model,
        "wind_speed_unit": "ms",
        "timezone": "GMT",
        "timeformat": "unixtime",
    }
    payload = client.get(FORECAST_URL, params=params, label="open-meteo forecast").json()
    if isinstance(payload, dict) and payload.get("error"):
        raise HttpError(f"open-meteo: {str(payload.get('reason', 'error'))[:160]}", kind="http_error")

    batch = parse_forecast(payload, locations, settings.weather_model, retrieved_at, issued_at, run_provenance)
    batch.notes.append(
        f"model {settings.weather_model}; run initialised "
        f"{issued_at.isoformat() if issued_at else 'unknown'}; {len(locations)} locations"
    )
    return batch
