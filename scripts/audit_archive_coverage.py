"""Measure what the collected archive can actually support as research targets.

WP1 accepts at ">= 100 stations with >= 1 year of QA'd daily targets". This
counts that, from the rows in data/archive, using the same CPCB aggregation the
product uses: at least 16 distinct hourly bins per pollutant per IST day, CO and
O3 from full eight-hour windows, and a daily AQI only where enough pollutants
qualify. The point is to report the ceiling honestly - a station-year of PM2.5
alone is not a CPCB daily AQI, however many rows it contains.

    python -m scripts.audit_archive_coverage
"""
import gzip
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from src import config
from src.nationwide.aqi import IST
from src.qa.hourly import audit as qa_audit
from src.research.protocol import daily_target

ARCHIVE = config.PROJECT_ROOT / 'data/archive'
MINIMUM_POLLUTANTS = 3
QA_SAMPLE_ROWS = 120000


def load_rows(directory=ARCHIVE):
    rows = []
    for path in sorted(directory.glob('*.ndjson.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def ist_date(value):
    return datetime.fromisoformat(value).astimezone(IST).date()


def main():
    if not ARCHIVE.exists():
        print('No archive directory; run python -m scripts.backfill_openaq_archive --sink files first.')
        return 1
    rows = load_rows()
    if not rows:
        print('Archive is empty.')
        return 1

    by_station = defaultdict(list)
    for row in rows:
        by_station[row['station_pk']].append(row)

    # QA flags are reported over a bounded sample: the flag pass is quadratic in
    # neighbours within a station-day and the point here is coverage, not a
    # per-row verdict on every hour ever collected.
    sample = rows[:QA_SAMPLE_ROWS]
    qa = qa_audit(sample)

    stations, per_pollutant_days, valid_days_total = [], defaultdict(int), 0
    for station_pk, station_rows in sorted(by_station.items()):
        dates = sorted({ist_date(row['valid_at']) for row in station_rows})
        by_date = defaultdict(list)
        for row in station_rows:
            by_date[ist_date(row['valid_at'])].append(row)
        valid_days, pollutant_days, aqi_days = 0, defaultdict(int), []
        for day in dates:
            # The eight-hour windows need the preceding hours, which the target
            # builder expects to be supplied with the day.
            window = by_date[day] + by_date.get(day - timedelta(days=1), [])
            try:
                target = daily_target(window, day, station_pk,
                                      datetime.now(timezone.utc))
            except ValueError:
                continue
            calculation = target.get('calculation') or {}
            qualifying = [p for p, value in (calculation.get('pollutants') or {}).items()
                          if (value or {}).get('concentration') is not None]
            for pollutant in qualifying:
                pollutant_days[pollutant] += 1
                per_pollutant_days[pollutant] += 1
            if (calculation.get('aqi') is not None and calculation.get('status') == 'VALID'
                    and len(qualifying) >= MINIMUM_POLLUTANTS):
                valid_days += 1
                aqi_days.append(str(day))
        valid_days_total += valid_days
        stations.append({
            'station_pk': station_pk,
            'name': next((r.get('provenance', {}).get('source_station_id') for r in station_rows), None),
            'rows': len(station_rows),
            'first_day': str(dates[0]), 'last_day': str(dates[-1]), 'calendar_days_spanned': (dates[-1] - dates[0]).days + 1,
            'days_with_any_data': len(dates),
            'pollutant_days': dict(sorted(pollutant_days.items())),
            'days_with_valid_daily_aqi': valid_days,
            'meets_one_year': valid_days >= 365,
        })

    qualifying_stations = [s for s in stations if s['meets_one_year']]
    summary = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'data/archive (OpenAQ v3 hourly backfill)',
        'rows': len(rows), 'stations': len(stations),
        'rule': 'CPCB daily aggregation: >=16 distinct hourly bins per pollutant per IST day; CO and O3 '
                'from full 8-hour windows; a daily AQI needs at least '
                f'{MINIMUM_POLLUTANTS} qualifying pollutants.',
        'station_days_with_valid_daily_aqi': valid_days_total,
        'pollutant_days': dict(sorted(per_pollutant_days.items())),
        'stations_with_one_year_of_valid_targets': len(qualifying_stations),
        'wp1_acceptance': {
            'required_stations': 100, 'required_days_each': 365,
            'met': len(qualifying_stations) >= 100,
            'blocker': 'Upstream pollutant coverage and OpenAQ request limits; the licensed CPCB CCR '
                       'export remains the first-choice source and is not held.',
        },
        'qa_sample': {
            'rows_audited': qa.get('rows_audited', len(sample)),
            'flags_by_code': qa.get('flags_by_code'),
            'flagged_row_count': len(qa.get('flagged_rows') or []),
            'rows_deleted': qa.get('rows_deleted'),
            'note': 'QA flags are advisory and no row is deleted. Sampled, not exhaustive.',
        },
        'stations_detail': stations,
        'notice': 'Rows per station are not the same as usable daily targets. A station-year of one '
                  'pollutant cannot produce a CPCB daily AQI.',
    }
    out = config.PROJECT_ROOT / 'results/archive_coverage.json'
    out.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in (
        'rows', 'stations', 'station_days_with_valid_daily_aqi', 'pollutant_days',
        'stations_with_one_year_of_valid_targets', 'wp1_acceptance')}, indent=1, default=str))
    print(f'artefact: {config.portable(out)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
