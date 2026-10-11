"""Indian CPCB-style AQI, versioned independently from the research HAI.

Source: CPCB National Air Quality Index Final Technical Report (2014),
Table 3.11, sections 3.5 and 3.7:
https://airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf
Continuous upper-breakpoint interpolation follows section 3.5. No gas mixing
ratio conversions, imputation or made-up severe upper breakpoints are used.
Above the last closed breakpoint, 401 is a LOWER BOUND, never an exact AQI.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

METHOD = "airguard-cpcb-2014-v1"
IST = ZoneInfo("Asia/Kolkata")
SOURCE = "https://airquality.cpcb.gov.in/ccr_docs/FINAL-REPORT_AQI_.pdf"
# The report gives closed upper concentration breakpoints through AQI 400.
BREAKPOINTS = {
    "PM2.5": (30, 60, 90, 120, 250), "PM10": (50, 100, 250, 350, 430),
    "NO2": (40, 80, 180, 280, 400), "SO2": (40, 80, 380, 800, 1600),
    "CO": (1, 2, 10, 17, 34), "O3": (50, 100, 168, 208, 748),
    "NH3": (200, 400, 800, 1200, 1800), "Pb": (.5, 1, 2, 3, 3.5),
}
CATEGORIES = [
    {"label": "Good", "upper": 50, "colour": "#008000"},
    {"label": "Satisfactory", "upper": 100, "colour": "#8db600"},
    {"label": "Moderate", "upper": 200, "colour": "#e8b500"},
    {"label": "Poor", "upper": 300, "colour": "#e67e00"},
    {"label": "Very Poor", "upper": 400, "colour": "#d32f2f"},
    {"label": "Severe", "upper": 500, "colour": "#8b1a1a"},
]


def valid(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def normalize(pollutant: str, value, unit: str):
    """Mass concentration only. CO is mg/m³, everything else µg/m³."""
    if pollutant not in BREAKPOINTS or not valid(value):
        return None
    unit = unit.lower().replace("µ", "u").replace("μ", "u").replace("³", "3").replace("^", "").replace(" ", "")
    if unit not in ("ug/m3", "mg/m3"):
        return None  # ppb/ppm require actual temperature/pressure, not a guess.
    target = "mg/m3" if pollutant == "CO" else "ug/m3"
    return float(value) if unit == target else float(value) * (.001 if target == "mg/m3" else 1000)


def subindex(pollutant: str, concentration, *, ozone_hourly=None):
    if pollutant not in BREAKPOINTS or not valid(concentration):
        return None
    # O3 >208 µg/m³ uses the report's one-hour mathematical bands.
    if pollutant == "O3":
        if valid(ozone_hourly) and ozone_hourly > 208:
            concentration = ozone_hourly
        elif concentration > 208:
            return None  # eight-hour ozone cannot be used in the one-hour bands
    low_c, low_i = 0, 0
    for high_c, high_i in zip(BREAKPOINTS[pollutant], (50, 100, 200, 300, 400)):
        if concentration <= high_c:
            value = low_i + (high_i - low_i) * (concentration - low_c) / (high_c - low_c)
            return {"value": int(math.floor(value + .5)), "qualifier": "EXACT"}
        low_c, low_i = high_c, high_i
    return {"value": 401, "qualifier": "LOWER_BOUND"}


def category(value):
    if value is None:
        return None
    return next((dict(c, index=i) for i, c in enumerate(CATEGORIES) if value <= c["upper"]), dict(CATEGORIES[-1], index=5))


def calculate(averages: dict, ozone_hourly=None):
    indices = {p: subindex(p, v, ozone_hourly=ozone_hourly) for p, v in averages.items()}
    indices = {p: v for p, v in indices.items() if v is not None}
    sufficient = len(indices) >= 3 and bool({"PM2.5", "PM10"}.intersection(indices))
    dominant = max(indices, key=lambda p: indices[p]["value"]) if sufficient else None
    aqi = indices[dominant]["value"] if dominant else None
    qualifier = indices[dominant]["qualifier"] if dominant else None
    return {"aqi": aqi, "category": category(aqi), "dominant_pollutant": dominant,
            "status": "INSUFFICIENT_DATA" if not sufficient else "LOWER_BOUND" if qualifier == "LOWER_BOUND" else "VALID",
            "qualifier": qualifier, "sub_indices": indices, "methodology_version": METHOD}


def parse_time(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def aggregate(rows: list[dict], start: datetime, end: datetime, *, rolling=False):
    """24h means; CO/O3 full 8h windows. At least 16 distinct hourly bins/day.

    For a daily forecast use the maximum trailing 8h mean ending in that IST
    day, with the preceding seven hours as support. For a rolling snapshot use
    the final full eight hours. This daily maximum is an AirGuard forecasting
    convention, explicitly distinct from an official station bulletin.
    """
    selected = [r for r in rows if start <= parse_time(r["time"]) < end]
    by_time = {parse_time(r["time"]): r for r in rows}
    averages, coverage, breakdown = {}, {}, {}
    for pollutant in BREAKPOINTS:
        # Count hourly bins, never multiple high-frequency samples as hours.
        bins = {}
        for row in sorted(selected, key=lambda r:parse_time(r["time"])):
            at = parse_time(row["time"])
            if valid(row.get(pollutant)):
                bins.setdefault(int((at-start).total_seconds()//3600),(at,row[pollutant]))
        values = dict(bins.values())
        coverage[pollutant] = len(values)
        avg = None
        ozone_hourly = max(values.values()) if pollutant == "O3" and values else None
        if len(values) >= 16:
            if pollutant in ("CO", "O3"):
                windows = []
                endings = [max(values)] if rolling else sorted(values)
                for ending in endings:
                    window = [by_time.get(ending - timedelta(hours=i), {}).get(pollutant) for i in range(8)]
                    if all(valid(v) for v in window):
                        windows.append(mean(window))
                avg = max(windows) if windows else None
            else:
                avg = mean(values.values())
        if avg is not None:
            averages[pollutant] = avg
        si = subindex(pollutant, avg, ozone_hourly=ozone_hourly) if avg is not None else None
        breakdown[pollutant] = {"concentration": round(avg, 4) if avg is not None else None,
            "unit": "mg/m³" if pollutant == "CO" else "µg/m³", "valid_hours": len(values),
            "averaging_window": "8h trailing mean" if rolling and pollutant in ("CO", "O3") else "maximum trailing 8h mean" if pollutant in ("CO", "O3") else "24h mean",
            "ozone_one_hour_max": ozone_hourly, "sub_index": si,
            "trend": "NOT_ESTIMATED", "quality": "VALID" if si else "INSUFFICIENT_DATA"}
    result = calculate(averages, max((r.get("O3") for r in selected if valid(r.get("O3"))), default=None))
    result.update(pollutants=breakdown, coverage=coverage, window_start=start.isoformat(), window_end=end.isoformat())
    return result


def tomorrow_period(now):
    start = (now.astimezone(IST) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
