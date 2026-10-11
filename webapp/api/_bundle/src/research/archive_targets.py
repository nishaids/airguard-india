"""Daily CPCB-style targets built from the file-based hourly archive.

Both the coverage audit and the measured-baseline reference need the same thing:
the archive's hourly rows collapsed into one validated daily value per station
and IST day, under the official averaging rules. Doing it in one place keeps the
two from drifting apart, which is how a coverage count and a metric end up
describing different sets of days.
"""
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import config
from src.nationwide.aqi import IST
from src.research.protocol import daily_target

ARCHIVE = config.PROJECT_ROOT / 'data/archive'
MINIMUM_POLLUTANTS = 3


def load_rows(directory=None):
    """Every archive row, from the gzipped NDJSON files."""
    directory = Path(directory or ARCHIVE)
    rows = []
    if not directory.exists():
        return rows
    for path in sorted(directory.glob('*.ndjson.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def ist_date(value):
    return datetime.fromisoformat(value).astimezone(IST).date()


def daily_targets(rows, minimum_pollutants=MINIMUM_POLLUTANTS, available_at=None):
    """One record per station-day that produces a valid daily AQI.

    A day is kept only when the official calculation returns VALID and at least
    `minimum_pollutants` pollutants qualified. The CPCB engine already refuses to
    produce an index from fewer than three pollutants, so this parameter can
    tighten that rule but never loosen it: a day the official method calls
    INSUFFICIENT_DATA is excluded under that name whatever is passed here. Days
    that fall short are counted, not silently dropped, so the caller can report
    what was excluded and why.
    """
    available_at = available_at or datetime.now(timezone.utc)
    by_station_day = defaultdict(list)
    for row in rows:
        by_station_day[(row['station_pk'], ist_date(row['valid_at']))].append(row)

    targets, excluded = [], defaultdict(int)
    for (station_pk, day), day_rows in sorted(by_station_day.items()):
        # The eight-hour windows for CO and O3 need the preceding hours.
        window = day_rows + by_station_day.get((station_pk, day - timedelta(days=1)), [])
        try:
            target = daily_target(window, day, station_pk, available_at)
        except ValueError as exc:
            excluded[f'target_rejected: {exc}'] += 1
            continue
        calculation = target.get('calculation') or {}
        qualifying = sorted(p for p, value in (calculation.get('pollutants') or {}).items()
                            if (value or {}).get('concentration') is not None)
        if calculation.get('status') != 'VALID':
            excluded[f"status_{calculation.get('status', 'UNKNOWN')}"] += 1
            continue
        if len(qualifying) < minimum_pollutants:
            excluded[f'only_{len(qualifying)}_qualifying_pollutants'] += 1
            continue
        targets.append({
            'station_pk': station_pk, 'date': day, 'aqi': calculation['aqi'],
            'qualifier': calculation.get('qualifier'),
            'dominant_pollutant': calculation.get('dominant_pollutant'),
            'pollutants': qualifying,
            'category': (calculation.get('category') or {}).get('label'),
        })
    return targets, dict(excluded)
