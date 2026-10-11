"""Retrospective QA flags; rows are retained and flags require review.

Expected input is a normalized measured environmental record, not a modelled
grid estimate. Zero is a suspect reading, not automatically an invalid one.
No spike is silently removed, including within an evidenced event window.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import math
from statistics import median
from src.nationwide.aqi import IST, BREAKPOINTS

VERSION = 'station-hourly-qa-v1'


def stamp(value):
    at = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if at.tzinfo is None: raise ValueError('Timezone-aware measurement time required')
    return at.astimezone(timezone.utc)


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def audit(rows, event_windows=()):
    """Return per-row flags and per-station daily unique-hour completeness.

    MAD uses the previous 24 hours (at least 12 unique readings). An event
    exemption requires an explicit reference and inclusive-start/exclusive-end
    interval. A flatline needs six consecutive unique hourly timestamps.
    """
    flags = defaultdict(set); groups = defaultdict(list); bins = defaultdict(dict)
    pm = defaultdict(dict); counts = Counter(); by_station = defaultdict(Counter)
    records = list(rows)
    for i, row in enumerate(records):
        if row.get('source_type') != 'measured' or not row.get('station_pk'):
            flags[i].add('NOT_STATION_MEASUREMENT'); continue
        p = row.get('pollutant'); value = row.get('normalized_value')
        if p not in BREAKPOINTS: flags[i].add('UNKNOWN_POLLUTANT'); continue
        try: at = stamp(row.get('valid_at'))
        except (TypeError, ValueError): flags[i].add('INVALID_TIME'); continue
        if not finite(value): flags[i].add('NON_FINITE'); continue
        if value < 0: flags[i].add('NEGATIVE')
        if value == 0: flags[i].add('ZERO_SUSPECT')
        expected = 'mg/m3' if p == 'CO' else 'ug/m3'
        if row.get('normalized_unit') != expected: flags[i].add('UNIT_MISMATCH'); continue
        if value < 0: continue
        station = row['station_pk']; hour = at.replace(minute=0, second=0, microsecond=0)
        day = at.astimezone(IST).date().isoformat()
        key = (station, p, day)
        if hour in bins[key]: flags[i].add('DUPLICATE_HOUR')
        else:
            bins[key][hour] = i
            groups[station, p].append((hour, value, i))
            if p in ('PM2.5', 'PM10'): pm[station, hour][p] = (value, i)
    for values in groups.values():
        values.sort(); run = []
        for j, (at, value, i) in enumerate(values):
            if run and (at - run[-1][0] != timedelta(hours=1) or value != run[-1][1]): run = []
            run.append((at, value, i))
            if len(run) >= 6:
                for _, _, index in run: flags[index].add('FLATLINE_6H')
            previous = [v for t, v, _ in values[max(0,j-24):j] if at-t <= timedelta(hours=24)]
            if len(previous) >= 12:
                centre = median(previous); mad = median(abs(v-centre) for v in previous)
                spike = abs(value-centre)/(1.4826*mad) > 6 if mad > 0 else value != centre
                if spike:
                    flags[i].add('MAD_SPIKE' if mad > 0 else 'ZERO_MAD_CHANGE')
                    observed_at = stamp(records[i]['valid_at'])
                    if any(w.get('reference') and stamp(w['start']) <= observed_at < stamp(w['end']) for w in event_windows):
                        flags[i].add('SPIKE_EVENT_REVIEW')
    for readings in pm.values():
        if 'PM2.5' in readings and 'PM10' in readings and readings['PM2.5'][0] > readings['PM10'][0]:
            for _, index in readings.values(): flags[index].add('PM25_GT_PM10')
    completeness = []
    for (station,p,day), hours in sorted(bins.items(), key=lambda x: str(x[0])):
        adequate = len(hours) >= 16
        completeness.append({'station_pk':station,'pollutant':p,'date':day,'unique_hours':len(hours),'minimum_hours':16,'complete':adequate})
        if not adequate:
            for index in hours.values(): flags[index].add('INCOMPLETE_DAY')
    flagged = []
    for i, codes in sorted(flags.items()):
        station = str(records[i].get('station_pk', 'unknown'))
        counts.update(codes); by_station[station].update(codes)
        flagged.append({'input_index':i,'record_key':records[i].get('record_key'),'station_pk':records[i].get('station_pk'),'flags':sorted(codes)})
    return {'qa_version':VERSION,'rows_audited':len(records),'rows_deleted':0,
            'flags_by_code':dict(sorted(counts.items())), 'flags_by_station':{k:dict(v) for k,v in sorted(by_station.items())},
            'flagged_rows':flagged,'daily_completeness':completeness,
            'interpretation':'Flags require review. No silent deletion or automatic event exemption; source rows remain immutable.'}
