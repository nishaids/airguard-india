"""Data-quality checks for incoming records.

The rule is to keep what can be kept. A reading that looks wrong but could be
real is stored with a flag saying why it looks wrong; only a record that cannot
be used at all -- no station, no time, a value that is not a number, a negative
concentration -- is rejected, and a rejection is itself recorded with its
reason. Nothing is dropped silently.

Check codes
-----------
Reject:  ``MISSING_STATION_ID``, ``MISSING_TIMESTAMP``, ``UNPARSABLE_VALUE``,
         ``MISSING_POLLUTANT``, ``NEGATIVE_VALUE``, ``FUTURE_TIMESTAMP``,
         ``DUPLICATE_IN_BATCH``.
Warning: ``UNIT_UNSPECIFIED``, ``UNSUPPORTED_UNIT``, ``IMPLAUSIBLE_VALUE``,
         ``COORDINATES_MISSING``, ``COORDINATES_INVALID``,
         ``COORDINATES_OUTSIDE_INDIA``, ``STALE``, ``UNAVAILABLE``.
Info:    ``DELAYED``, ``UNIT_CONVERTED``.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional, Set, Tuple

from src import config
from src.ingestion import units
from src.ingestion.schemas import (
    AirQualityObservation,
    FireDetection,
    Freshness,
    QualityState,
    RejectedRecord,
    Severity,
    ValueKind,
    WeatherForecast,
    utc_now,
)
from src.ingestion.settings import INDIA_BBOX, Settings, get_settings

#: Hard physical limits for forecast meteorology. Outside these the value is an
#: encoding fault, not weather.
WEATHER_LIMITS = {
    "temperature_2m": (-60.0, 60.0),
    "relative_humidity_2m": (0.0, 100.0),
    "precipitation": (0.0, 500.0),
    "wind_speed_10m": (0.0, 120.0),
    "wind_direction_10m": (0.0, 360.0),
    "surface_pressure": (300.0, 1100.0),
    "boundary_layer_height": (0.0, 10000.0),
}


def parse_number(value: Any) -> Optional[float]:
    """Parse a provider's value, returning ``None`` for anything that is not a finite number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        if text == "" or text.upper() in {"NA", "N/A", "NULL", "NONE", "-", "--"}:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def classify_freshness(observed_at: Optional[datetime], now: datetime, settings: Settings) -> Freshness:
    """How old a reading is, in the product's terms.

    ``fresh`` up to ``fresh_minutes``; ``delayed`` up to ``stale_minutes``;
    ``stale`` up to ``unavailable_hours``; beyond that, or with no reading at
    all, ``unavailable``. All three thresholds are configuration.
    """
    if observed_at is None:
        return Freshness.UNAVAILABLE
    age = now - observed_at
    if age < -timedelta(minutes=settings.future_tolerance_minutes):
        return Freshness.UNAVAILABLE
    if age <= timedelta(minutes=settings.fresh_minutes):
        return Freshness.FRESH
    if age <= timedelta(minutes=settings.stale_minutes):
        return Freshness.DELAYED
    if age <= timedelta(hours=settings.unavailable_hours):
        return Freshness.STALE
    return Freshness.UNAVAILABLE


def _check_coordinates(record: Any, lat: Optional[float], lon: Optional[float]) -> None:
    if lat is None or lon is None:
        record.add_flag("COORDINATES_MISSING", Severity.WARNING, "no coordinates supplied", "latitude")
        return
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0) or (lat == 0.0 and lon == 0.0):
        record.add_flag("COORDINATES_INVALID", Severity.WARNING, f"coordinates ({lat}, {lon}) are not a valid position", "latitude")
        return
    west, south, east, north = INDIA_BBOX
    if not (south <= lat <= north and west <= lon <= east):
        record.add_flag("COORDINATES_OUTSIDE_INDIA", Severity.WARNING, f"coordinates ({lat}, {lon}) fall outside the India bounding box", "latitude")


# A provider's unit label can be wrong, and a wrong label turns into a wrong number
# the moment it is converted. Carbon monoxide has a hard floor that exposes this:
# even the cleanest remote air holds roughly 0.05 mg/m3, so a positive reading far
# below that was reported in some other unit than the one stated. Canonical units.
AMBIENT_FLOOR = {"CO": 0.02}


def validate_observation(
    obs: AirQualityObservation,
    now: Optional[datetime] = None,
    settings: Optional[Settings] = None,
    seen: Optional[Set[tuple]] = None,
) -> AirQualityObservation:
    """Attach quality flags to one observation and fill its normalised value.

    Freshness and the future-timestamp check are judged against the moment the
    reading was retrieved, not the moment this function runs: validation can
    happen long after retrieval when a run is paused. ``now`` is used only for
    a record that carries no retrieval time.
    """
    now = obs.retrieved_at or now or utc_now()
    settings = settings or get_settings()

    if not obs.source_station_id:
        obs.add_flag("MISSING_STATION_ID", Severity.REJECT, "the record names no station", "source_station_id")
    if obs.observed_at is None:
        obs.add_flag("MISSING_TIMESTAMP", Severity.REJECT, "the record has no usable measurement time", "observed_at")
    if not obs.pollutant:
        obs.add_flag("MISSING_POLLUTANT", Severity.REJECT, f"pollutant {obs.raw_pollutant!r} is not recognised", "pollutant")

    value = parse_number(obs.raw_value)
    if value is None:
        obs.add_flag("UNPARSABLE_VALUE", Severity.REJECT, f"value {obs.raw_value!r} is not a number", "raw_value")
    elif value < 0:
        obs.add_flag("NEGATIVE_VALUE", Severity.REJECT, f"value {value} is negative, which is physically impossible", "raw_value")

    if obs.observed_at is not None and obs.observed_at > now + timedelta(minutes=settings.future_tolerance_minutes):
        obs.add_flag("FUTURE_TIMESTAMP", Severity.REJECT, f"measurement time {obs.observed_at.isoformat()} is in the future", "observed_at")

    if obs.quality_state is QualityState.REJECTED:
        return obs

    if seen is not None:
        if obs.unique_key in seen:
            obs.add_flag("DUPLICATE_IN_BATCH", Severity.REJECT, "the same station, pollutant and time already appeared in this batch")
            return obs
        seen.add(obs.unique_key)

    # --- unit normalisation -------------------------------------------------- #
    if obs.value_kind is ValueKind.CONCENTRATION:
        try:
            converted, unit, note = units.normalise(obs.pollutant, value, obs.raw_unit)
            floor = AMBIENT_FLOOR.get(obs.pollutant)
            if floor is not None and 0 < converted < floor:
                # Not corrected by guessing the real unit: kept raw, like any value whose unit is unknown.
                obs.provenance["unit_suspect"] = {"stated_unit": obs.raw_unit, "would_be": converted, "in": unit, "floor": floor}
                obs.add_flag(
                    "UNIT_SUSPECT",
                    Severity.WARNING,
                    f"{value:g} {obs.raw_unit} would be {converted:g} {unit}, below any ambient level; "
                    "the stated unit is probably wrong, so the value is stored raw and not normalised",
                    "raw_unit",
                )
            else:
                obs.normalized_value, obs.normalized_unit = converted, unit
                if note:
                    obs.provenance["unit_conversion"] = note
                    obs.add_flag("UNIT_CONVERTED", Severity.INFO, f"{obs.raw_unit} -> {obs.normalized_unit}; {note}", "raw_unit")
        except units.UnsupportedUnit as exc:
            obs.add_flag("UNSUPPORTED_UNIT", Severity.WARNING, str(exc), "raw_unit")
    else:
        # The provider did not say what the number measures. It is kept exactly
        # as received and is not converted into a concentration by assumption.
        obs.add_flag(
            "UNIT_UNSPECIFIED",
            Severity.WARNING,
            "the provider publishes no unit for this value, so it is stored raw and not normalised",
            "raw_unit",
        )

    if obs.normalized_value is not None:
        ceiling = config.POLLUTANT_PLAUSIBLE_MAX.get(obs.pollutant)
        if ceiling is not None and obs.normalized_value > ceiling:
            obs.add_flag(
                "IMPLAUSIBLE_VALUE",
                Severity.WARNING,
                f"{obs.normalized_value:g} {obs.normalized_unit} exceeds the plausibility ceiling of {ceiling:g}",
                "normalized_value",
            )

    _check_coordinates(obs, obs.latitude, obs.longitude)

    obs.freshness = classify_freshness(obs.observed_at, now, settings)
    if obs.freshness is Freshness.DELAYED:
        obs.add_flag("DELAYED", Severity.INFO, "reading is older than the fresh threshold", "observed_at")
    elif obs.freshness is Freshness.STALE:
        obs.add_flag("STALE", Severity.WARNING, f"reading is older than {settings.stale_minutes} minutes", "observed_at")
    elif obs.freshness is Freshness.UNAVAILABLE:
        obs.add_flag("UNAVAILABLE", Severity.WARNING, f"reading is older than {settings.unavailable_hours} hours", "observed_at")
    return obs


def validate_fire(fire: FireDetection, now: Optional[datetime] = None, settings: Optional[Settings] = None, seen: Optional[Set[tuple]] = None) -> FireDetection:
    now = now or utc_now()
    settings = settings or get_settings()

    if fire.latitude is None or fire.longitude is None:
        fire.add_flag("COORDINATES_MISSING", Severity.REJECT, "a detection without a position cannot be used", "latitude")
    elif not (-90.0 <= fire.latitude <= 90.0 and -180.0 <= fire.longitude <= 180.0):
        fire.add_flag("COORDINATES_INVALID", Severity.REJECT, "position is not on the globe", "latitude")
    if fire.acquired_at is None:
        fire.add_flag("MISSING_TIMESTAMP", Severity.REJECT, "no usable acquisition time", "acquired_at")
    elif fire.acquired_at > now + timedelta(minutes=settings.future_tolerance_minutes):
        fire.add_flag("FUTURE_TIMESTAMP", Severity.REJECT, "acquisition time is in the future", "acquired_at")
    if fire.quality_state is QualityState.REJECTED:
        return fire

    if seen is not None:
        if fire.unique_key in seen:
            fire.add_flag("DUPLICATE_IN_BATCH", Severity.REJECT, "the same detection already appeared in this batch")
            return fire
        seen.add(fire.unique_key)

    if fire.frp_mw is not None and fire.frp_mw < 0:
        fire.add_flag("NEGATIVE_VALUE", Severity.WARNING, "fire radiative power is negative", "frp_mw")
    if fire.confidence is None:
        fire.add_flag("CONFIDENCE_MISSING", Severity.INFO, "no detection confidence supplied", "confidence")
    return fire


def validate_weather(forecast: WeatherForecast, seen: Optional[Set[tuple]] = None) -> WeatherForecast:
    if seen is not None:
        if forecast.unique_key in seen:
            forecast.add_flag("DUPLICATE_IN_BATCH", Severity.REJECT, "the same forecast hour already appeared in this batch")
            return forecast
        seen.add(forecast.unique_key)

    if all(v is None for v in forecast.variables.values()):
        forecast.add_flag("UNPARSABLE_VALUE", Severity.REJECT, "every variable is missing for this hour")
        return forecast

    for name, value in forecast.variables.items():
        if value is None:
            forecast.add_flag("VARIABLE_MISSING", Severity.WARNING, f"{name} is missing for this hour", name)
            continue
        low, high = WEATHER_LIMITS.get(name, (-math.inf, math.inf))
        if not (low <= value <= high):
            forecast.add_flag("IMPLAUSIBLE_VALUE", Severity.WARNING, f"{name} = {value:g} is outside [{low:g}, {high:g}]", name)
    if forecast.lead_time_hours < 0:
        forecast.add_flag("NOT_A_FORECAST", Severity.REJECT, "valid time precedes retrieval; this is not a forecast", "valid_at")
    return forecast


def split(records: Iterable[Any]) -> Tuple[List[Any], List[Any], List[Any]]:
    """Partition validated records into (clean, flagged, rejected)."""
    clean: List[Any] = []
    flagged: List[Any] = []
    rejected: List[Any] = []
    for record in records:
        if record.quality_state is QualityState.REJECTED:
            rejected.append(record)
        elif record.quality_state is QualityState.FLAGGED:
            flagged.append(record)
        else:
            clean.append(record)
    return clean, flagged, rejected


def rejection_of(record: Any) -> RejectedRecord:
    """Summarise a rejected record so its reason can be stored."""
    reasons = [f for f in record.quality_flags if f.severity is Severity.REJECT]
    first = reasons[0]
    excerpt = {
        k: (v.isoformat() if isinstance(v, datetime) else v)
        for k, v in {
            "station": getattr(record, "source_station_id", None),
            "pollutant": getattr(record, "raw_pollutant", None),
            "value": getattr(record, "raw_value", None),
            "unit": getattr(record, "raw_unit", None),
            "time": getattr(record, "observed_at", None) or getattr(record, "acquired_at", None) or getattr(record, "valid_at", None),
            "record_id": getattr(record, "source_record_id", None),
        }.items()
        if v is not None
    }
    return RejectedRecord(record.source, first.code, "; ".join(f.message for f in reasons), excerpt)
