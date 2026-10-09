"""Hourly modelled air quality for the target cities: CAMS global, via Open-Meteo.

MODELLED, not measured. The values describe a grid cell about 40 km across, so
they smooth over the roadside and neighbourhood peaks a monitor records.

Only the standard library is used for the request, so the deployed function
needs no HTTP dependency. No key is required.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import pandas as pd

API = "https://air-quality-api.open-meteo.com/v1/air-quality"
SOURCE = "CAMS global atmospheric model, via Open-Meteo"
SOURCE_TYPE = "modelled"
TIMEZONE = "Asia/Kolkata"

#: Open-Meteo's variable -> the column name used throughout AirGuard.
VARIABLES: Dict[str, str] = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "carbon_monoxide": "CO",
    "ozone": "O3",
}
POLLUTANTS = list(VARIABLES.values())

#: A day with fewer hourly values than this is not treated as a day.
MIN_HOURS_PER_DAY = 18

Fetcher = Callable[[str], Any]


class LiveSourceError(RuntimeError):
    """The modelled-data provider could not be used."""


def _http_get_json(url: str, timeout: float = 25.0, attempts: int = 3) -> Any:
    last: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AirGuard-India/2.0 (academic project)"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
        time.sleep(1.5 * (attempt + 1))
    reason = f"HTTP {last.code}" if isinstance(last, urllib.error.HTTPError) else last.__class__.__name__
    raise LiveSourceError(f"Open-Meteo air-quality API unavailable ({reason})")


def fetch_hourly(
    cities: Mapping[str, Tuple[float, float]],
    past_days: int = 20,
    forecast_days: int = 3,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fetcher: Optional[Fetcher] = None,
) -> pd.DataFrame:
    """Hourly concentrations for every city, in AirGuard's units, on Indian local time.

    Returns one row per city and hour: ``City``, ``time`` and one column per
    pollutant. Carbon monoxide is converted from the provider's ug/m3 to the
    mg/m3 the rest of AirGuard uses; everything else is already in ug/m3.
    """
    names = list(cities)
    params: Dict[str, Any] = {
        "latitude": ",".join(f"{cities[n][0]:.4f}" for n in names),
        "longitude": ",".join(f"{cities[n][1]:.4f}" for n in names),
        "hourly": ",".join(VARIABLES),
        "timezone": TIMEZONE,
    }
    if start_date and end_date:
        params.update(start_date=start_date, end_date=end_date)
    else:
        params.update(past_days=past_days, forecast_days=forecast_days)

    payload = (fetcher or _http_get_json)(f"{API}?{urllib.parse.urlencode(params)}")
    blocks = payload if isinstance(payload, list) else [payload]
    if len(blocks) != len(names) or not all(isinstance(b, dict) and "hourly" in b for b in blocks):
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise LiveSourceError(f"Open-Meteo air-quality API returned an unexpected body{': ' + str(reason)[:120] if reason else ''}")

    frames = []
    for name, block in zip(names, blocks):
        hourly = block["hourly"]
        frame = pd.DataFrame({"time": pd.to_datetime(hourly["time"])})
        for variable, column in VARIABLES.items():
            frame[column] = pd.to_numeric(pd.Series(hourly.get(variable, [None] * len(frame))), errors="coerce")
        frame["CO"] = frame["CO"] / 1000.0  # ug/m3 -> mg/m3
        frame.insert(0, "City", name)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def daily_means(hourly: pd.DataFrame, now_local: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Collapse hourly values into local calendar days, as the training data's daily averages are.

    ``forecast_hours`` counts the hours of each day that lie after ``now_local``:
    zero for a past day, and for today the part of the day that is still a
    forecast rather than an analysis.
    """
    frame = hourly.copy()
    frame["Date"] = frame["time"].dt.normalize()
    frame["_ahead"] = (frame["time"] > now_local).astype(int) if now_local is not None else 0
    grouped = frame.groupby(["City", "Date"], sort=True)
    daily = grouped[POLLUTANTS].mean()
    daily["hours"] = grouped["PM2.5"].count()
    daily["forecast_hours"] = grouped["_ahead"].sum()
    daily = daily.reset_index()
    return daily.loc[daily["hours"] >= MIN_HOURS_PER_DAY].reset_index(drop=True)
