"""Canonical records for live environmental data.

Every provider speaks its own dialect. A connector's whole job is to translate
that dialect into these types, preserving what the provider actually said
(``raw_*`` fields) beside what AirGuard understands it to mean
(``normalized_*`` fields). The two are never merged: a later reader can always
see the original value and unit and judge the conversion for themselves.

Timestamps are timezone-aware and stored in UTC. Where a provider reported a
local time, the zone it was reported in is kept alongside.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SourceType(str, Enum):
    """What kind of thing a record is. This label travels with every record."""

    MEASURED = "measured"  # an instrument at a station observed it
    MODELLED = "modelled"  # a model estimated it; never shown as a measurement
    SATELLITE_FIRE_DETECTION = "satellite_fire_detection"  # a hotspot, not air quality
    WEATHER_FORECAST = "weather_forecast"


class QualityState(str, Enum):
    OK = "ok"
    FLAGGED = "flagged"  # stored, with one or more warnings attached
    REJECTED = "rejected"  # not stored as data; the reason is recorded


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    REJECT = "reject"


class Freshness(str, Enum):
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ValueKind(str, Enum):
    """What the number is. Providers do not all publish concentrations."""

    CONCENTRATION = "concentration"
    INDEX = "index"
    UNKNOWN = "unknown"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Return an aware UTC datetime; a naive one is rejected rather than guessed."""
    if value.tzinfo is None:
        raise ValueError("naive datetime: the timezone must be explicit")
    return value.astimezone(timezone.utc)


def record_hash(*parts: Any) -> str:
    """Stable identity for a record whose provider supplies none."""
    text = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass
class DataQualityFlag:
    code: str
    severity: Severity
    message: str
    field_name: Optional[str] = None


class _Flaggable:
    """Shared behaviour for records that carry quality flags.

    An informational flag leaves a record ``ok``; a warning marks it
    ``flagged``; a reject marks it ``rejected`` and nothing can undo that.
    """

    quality_flags: List["DataQualityFlag"]
    quality_state: QualityState

    def add_flag(self, code: str, severity: Severity, message: str, field_name: Optional[str] = None) -> None:
        self.quality_flags.append(DataQualityFlag(code, severity, message, field_name))
        if severity is Severity.REJECT:
            self.quality_state = QualityState.REJECTED
        elif severity is Severity.WARNING and self.quality_state is QualityState.OK:
            self.quality_state = QualityState.FLAGGED


@dataclass
class Station:
    source: str
    source_station_id: str
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "IN"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    owner: Optional[str] = None  # who operates the instrument, as the provider reports it
    upstream_provider: Optional[str] = None  # where an aggregator obtained the data
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Set by matching: another source's station that is the same physical monitor.
    same_as: Optional[tuple] = None  # (source, source_station_id)
    match_method: Optional[str] = None
    match_distance_m: Optional[float] = None

    @property
    def key(self) -> tuple:
        return (self.source, self.source_station_id)


@dataclass
class AirQualityObservation(_Flaggable):
    source: str
    source_type: SourceType
    source_station_id: Optional[str]
    pollutant: Optional[str]  # canonical name, e.g. "PM2.5"
    observed_at: Optional[datetime]
    retrieved_at: datetime
    raw_value: Any
    raw_unit: Optional[str]
    raw_pollutant: Optional[str] = None
    raw_min: Any = None
    raw_max: Any = None
    value_kind: ValueKind = ValueKind.UNKNOWN
    averaging_period: str = "unspecified"
    normalized_value: Optional[float] = None
    normalized_unit: Optional[str] = None
    source_record_id: Optional[str] = None
    sensor_id: Optional[str] = None
    station_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    local_timezone: Optional[str] = None
    quality_state: QualityState = QualityState.OK
    quality_flags: List[DataQualityFlag] = field(default_factory=list)
    freshness: Optional[Freshness] = None
    use_for_modelling: bool = True
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def unique_key(self) -> tuple:
        """The identity that makes ingestion idempotent."""
        return (self.source, self.source_station_id, self.pollutant, self.averaging_period, self.observed_at)


@dataclass
class WeatherForecast(_Flaggable):
    """One forecast hour from one run of the weather model.

    The model run is part of the record's identity. A later run's forecast for
    the same valid hour is a *different* record and never overwrites this one:
    for training, the model may only ever see the forecast that existed at the
    moment a prediction would have been issued.

    Fetching the same run again is the same record, so re-running ingestion
    adds nothing. The copy kept is the first one, and its ``retrieved_at`` is
    the earliest moment AirGuard is known to have held that forecast.
    """

    source: str
    model: str
    location_label: str
    latitude: float
    longitude: float
    valid_at: datetime
    retrieved_at: datetime
    issued_at: Optional[datetime]  # model run initialisation, when the provider exposes it
    lead_time_hours: float  # valid_at minus retrieved_at
    variables: Dict[str, Optional[float]]
    units: Dict[str, str]
    source_type: SourceType = SourceType.WEATHER_FORECAST
    quality_state: QualityState = QualityState.OK
    quality_flags: List[DataQualityFlag] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def vintage_at(self) -> datetime:
        """Which edition of the forecast this is: the model run, or the retrieval hour if the run is unknown."""
        return self.issued_at or self.retrieved_at.replace(minute=0, second=0, microsecond=0)

    @property
    def unique_key(self) -> tuple:
        return (self.source, self.model, round(self.latitude, 4), round(self.longitude, 4), self.valid_at, self.vintage_at)


@dataclass
class FireDetection(_Flaggable):
    source: str
    satellite: Optional[str]
    instrument: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    acquired_at: Optional[datetime]
    retrieved_at: datetime
    confidence: Optional[str] = None
    frp_mw: Optional[float] = None  # fire radiative power, megawatts
    brightness_k: Optional[float] = None
    day_night: Optional[str] = None
    product: Optional[str] = None  # the FIRMS feed, e.g. VIIRS_NOAA20_NRT
    version: Optional[str] = None
    source_record_id: Optional[str] = None
    source_type: SourceType = SourceType.SATELLITE_FIRE_DETECTION
    quality_state: QualityState = QualityState.OK
    quality_flags: List[DataQualityFlag] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    @property
    def unique_key(self) -> tuple:
        return (self.source, self.source_record_id)


@dataclass
class RejectedRecord:
    """A record that could not be used, kept so the reason is never lost."""

    source: str
    code: str
    message: str
    raw_excerpt: Dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return record_hash(self.source, self.code, json.dumps(self.raw_excerpt, sort_keys=True, default=str))


@dataclass
class IngestionRun:
    source: str
    started_at: datetime
    dry_run: bool = False
    finished_at: Optional[datetime] = None
    status: RunStatus = RunStatus.FAILED
    retrieved: int = 0
    accepted: int = 0
    flagged: int = 0
    rejected: int = 0
    duplicates: int = 0
    written: int = 0
    error: Optional[str] = None  # always passed through settings.redact before it is set
    notes: List[str] = field(default_factory=list)
    run_id: Optional[int] = None

    def to_public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        return data
