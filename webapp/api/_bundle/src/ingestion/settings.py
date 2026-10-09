"""Configuration and secret handling for live ingestion.

Secrets are read from the process environment and from nowhere else. A local
``.env`` file, which Git ignores, is loaded into the environment at start-up so
that a developer does not have to export variables by hand; values already
present in the environment win, so a scheduler's secret store is never
overridden by a stray file.

No function in this module returns, logs or formats a secret value except
:func:`secret`, whose only callers are the connectors that place it in a
request. :func:`redact` exists so that anything headed for a log or a report
can be scrubbed first, including text that came back from a provider.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src import config

ENV_FILE: Path = config.PROJECT_ROOT / ".env"

#: Every variable whose value must never appear in output.
SECRET_NAMES: Tuple[str, ...] = (
    "DATA_GOV_API_KEY",
    "OPENAQ_API_KEY",
    "NASA_FIRMS_MAP_KEY",
    "DATABASE_URL",
)

_PLACEHOLDER_MARKERS = ("PROJECT_REF", "POOLER_HOST", "[PASSWORD]", "[PROJECT", "YOUR_", "<")


def load_env(path: Path = ENV_FILE) -> List[str]:
    """Load ``KEY=VALUE`` pairs from ``.env`` into the environment.

    Returns the *names* that were loaded, never the values. Existing
    environment variables are left untouched.
    """
    loaded: List[str] = []
    if not path.exists():
        return loaded
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def secret(name: str) -> Optional[str]:
    """Return a secret for use in a request, or ``None`` if it is not configured."""
    value = os.environ.get(name, "").strip()
    if not value or any(marker in value for marker in _PLACEHOLDER_MARKERS):
        return None
    return value


def secret_status() -> Dict[str, str]:
    """Describe each secret as configured, placeholder or missing. No values."""
    status: Dict[str, str] = {}
    for name in SECRET_NAMES:
        raw = os.environ.get(name, "").strip()
        if not raw:
            status[name] = "missing"
        elif any(marker in raw for marker in _PLACEHOLDER_MARKERS):
            status[name] = "placeholder"
        else:
            status[name] = "configured"
    return status


_KEY_IN_QUERY = re.compile(r"(?i)\b(api[-_]?key|map[-_]?key|key|token|password)=([^&\s\"']+)")
_URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@")
_FIRMS_PATH_KEY = re.compile(r"(?i)(/api/[a-z_]+/csv/)([0-9a-f]{16,})")


def redact(text: object) -> str:
    """Remove every configured secret, and anything shaped like one, from text."""
    out = str(text)
    for name in SECRET_NAMES:
        value = os.environ.get(name, "").strip()
        if len(value) >= 6:
            out = out.replace(value, f"<{name}>")
            # A connection string also leaks through its password component alone.
            match = _URL_CREDENTIALS.search(value)
            if match and len(match.group(3)) >= 4:
                out = out.replace(match.group(3), "<password>")
    out = _KEY_IN_QUERY.sub(lambda m: f"{m.group(1)}=<redacted>", out)
    out = _URL_CREDENTIALS.sub(lambda m: f"{m.group(1)}<user>:<password>@", out)
    out = _FIRMS_PATH_KEY.sub(lambda m: f"{m.group(1)}<redacted>", out)
    return out


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


#: Reference points for the twelve cities the 1.0 models cover. These are
#: approximate city-centre coordinates used to request gridded forecasts and to
#: search for nearby stations; they are not station locations.
TARGET_CITIES: Dict[str, Tuple[float, float]] = {
    "Amaravati": (16.5131, 80.5165),
    "Amritsar": (31.6340, 74.8723),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Delhi": (28.6139, 77.2090),
    "Gurugram": (28.4595, 77.0266),
    "Hyderabad": (17.3850, 78.4867),
    "Jaipur": (26.9124, 75.7873),
    "Kolkata": (22.5726, 88.3639),
    "Lucknow": (26.8467, 80.9462),
    "Thiruvananthapuram": (8.5241, 76.9366),
    "Visakhapatnam": (17.6868, 83.2185),
}

#: West, south, east, north. A generous box around India, used to sanity-check
#: coordinates and as the default FIRMS query area.
INDIA_BBOX: Tuple[float, float, float, float] = (68.0, 6.0, 97.5, 37.5)

INDIA_TIMEZONE = "Asia/Kolkata"


@dataclass(frozen=True)
class Settings:
    """Tunable behaviour, each value overridable through the environment.

    Staleness thresholds are product decisions, not constants of nature. The
    blueprint proposes three hours as the point at which a station's reading
    stops being usable for a "now" display; that is the default for
    ``stale_minutes`` and it is deliberately configurable.
    """

    fresh_minutes: int = field(default_factory=lambda: _int_env("AIRGUARD_FRESH_MINUTES", 90))
    stale_minutes: int = field(default_factory=lambda: _int_env("AIRGUARD_STALE_MINUTES", 180))
    unavailable_hours: int = field(default_factory=lambda: _int_env("AIRGUARD_UNAVAILABLE_HOURS", 24))
    future_tolerance_minutes: int = field(default_factory=lambda: _int_env("AIRGUARD_FUTURE_TOLERANCE_MINUTES", 30))

    http_timeout_seconds: int = field(default_factory=lambda: _int_env("AIRGUARD_HTTP_TIMEOUT", 30))
    http_max_retries: int = field(default_factory=lambda: _int_env("AIRGUARD_HTTP_RETRIES", 3))
    http_backoff_seconds: float = 1.5
    http_max_backoff_seconds: float = 30.0

    data_gov_resource_id: str = field(
        default_factory=lambda: os.environ.get("DATA_GOV_AQI_RESOURCE_ID", "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69")
    )
    weather_model: str = field(default_factory=lambda: os.environ.get("AIRGUARD_WEATHER_MODEL", "gfs_seamless"))
    weather_forecast_days: int = field(default_factory=lambda: _int_env("AIRGUARD_WEATHER_DAYS", 3))
    firms_day_range: int = field(default_factory=lambda: _int_env("AIRGUARD_FIRMS_DAY_RANGE", 1))
    firms_sources: Tuple[str, ...] = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
    openaq_search_radius_m: int = field(default_factory=lambda: _int_env("AIRGUARD_OPENAQ_RADIUS_M", 25000))
    openaq_active_within_days: int = field(default_factory=lambda: _int_env("AIRGUARD_OPENAQ_ACTIVE_DAYS", 7))
    station_match_metres: int = field(default_factory=lambda: _int_env("AIRGUARD_STATION_MATCH_M", 300))


def get_settings() -> Settings:
    return Settings()
