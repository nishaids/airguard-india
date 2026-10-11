import gzip
import json
from datetime import datetime, timedelta, timezone

from src.nationwide.aqi import IST
from src.research.archive_targets import daily_targets, load_rows

DAY = datetime(2026, 6, 1, tzinfo=IST)


def row(station, at, pollutant, value):
    return {'record_key': f'{station}-{pollutant}-{at.isoformat()}', 'provider': 'openaq',
            'source_type': 'measured', 'station_pk': station, 'pollutant': pollutant,
            'normalized_value': value, 'normalized_unit': 'mg/m3' if pollutant == 'CO' else 'ug/m3',
            'valid_at': at.astimezone(timezone.utc).isoformat(),
            'fetched_at': datetime(2026, 6, 3, tzinfo=timezone.utc).isoformat(),
            'quality_state': 'VALID'}


def day_rows(station, day, pollutants, hours=24, value=40.0):
    rows = []
    for hour in range(hours):
        at = day + timedelta(hours=hour)
        for pollutant in pollutants:
            rows.append(row(station, at, pollutant, value))
    return rows


def test_a_complete_three_pollutant_day_becomes_one_target():
    rows = day_rows(1, DAY - timedelta(days=1), ('PM2.5', 'PM10', 'O3'))
    rows += day_rows(1, DAY, ('PM2.5', 'PM10', 'O3'))
    targets, excluded = daily_targets(rows)
    kept = [t for t in targets if t['date'] == DAY.date()]
    assert len(kept) == 1
    assert kept[0]['station_pk'] == 1
    assert kept[0]['aqi'] is not None
    assert kept[0]['pollutants'] == ['O3', 'PM10', 'PM2.5']


def test_a_single_pollutant_year_yields_no_daily_index_and_says_why():
    rows = []
    for offset in range(5):
        rows += day_rows(2, DAY + timedelta(days=offset), ('PM2.5',))
    targets, excluded = daily_targets(rows)
    assert targets == []
    # The official engine refuses an index built from one pollutant, so the day
    # is excluded under its own verdict rather than under a rule of ours.
    assert excluded == {'status_INSUFFICIENT_DATA': 5}


def test_a_short_day_is_excluded_rather_than_averaged_anyway():
    rows = day_rows(3, DAY, ('PM2.5', 'PM10', 'O3'), hours=10)
    targets, excluded = daily_targets(rows)
    assert targets == []
    assert excluded


def test_the_pollutant_rule_can_tighten_but_never_loosen_the_official_one():
    two = day_rows(4, DAY - timedelta(days=1), ('PM2.5', 'PM10')) + day_rows(4, DAY, ('PM2.5', 'PM10'))
    # Two pollutants is INSUFFICIENT_DATA to the CPCB engine, and passing a
    # lower threshold here cannot override that.
    assert daily_targets(two, minimum_pollutants=2)[0] == []
    three = (day_rows(5, DAY - timedelta(days=1), ('PM2.5', 'PM10', 'O3'))
             + day_rows(5, DAY, ('PM2.5', 'PM10', 'O3')))
    assert DAY.date() in [t['date'] for t in daily_targets(three)[0]]
    # Tightening does work: four qualifying pollutants required, three exist.
    strict, excluded = daily_targets(three, minimum_pollutants=4)
    assert strict == [] and 'only_3_qualifying_pollutants' in excluded


def test_load_rows_reads_the_gzipped_archive_and_tolerates_blank_lines(tmp_path):
    path = tmp_path / 'station_1_pm25.ndjson.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as handle:
        handle.write(json.dumps({'station_pk': 1}) + '\n\n')
        handle.write(json.dumps({'station_pk': 2}) + '\n')
    assert load_rows(tmp_path) == [{'station_pk': 1}, {'station_pk': 2}]
    assert load_rows(tmp_path / 'missing') == []
