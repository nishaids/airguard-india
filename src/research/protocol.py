"""Versioned protocol and strict availability guards. No synthetic training data."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math
from src.nationwide.aqi import IST, METHOD, aggregate, parse_time
from src.nationwide.store import digest

PROTOCOL = json.loads(Path(__file__).with_name('protocol.json').read_text(encoding='utf8'))
VERSION = PROTOCOL['protocol_version']


def aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def cutoff_for(day):
    return datetime.fromisoformat(str(day) + 'T20:00:00').replace(tzinfo=IST).astimezone(timezone.utc)


def period(day):
    start = datetime.fromisoformat(str(day) + 'T00:00:00').replace(tzinfo=IST).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_inputs(inputs, cutoff):
    cutoff = aware(cutoff)
    for item in inputs:
        if aware(item['available_at']) > cutoff or aware(item['retrieved_at']) > cutoff:
            raise ValueError('Feature leakage: input not available at issuance cutoff')
        if item['source_type'] == 'measured':
            if aware(item['valid_end']) > cutoff:
                raise ValueError('Feature leakage: future observation')
        elif item['source_type'] not in ('modelled_forecast', 'weather_forecast', 'satellite_fire_detection'):
            raise ValueError('Unapproved predictor source (reanalysis is forbidden)')
        if item.get('reference_time') and aware(item['reference_time']) > cutoff:
            raise ValueError('Feature leakage: future model initialization')
        if item['source_type'] == 'satellite_fire_detection' and aware(item['valid_end']) > cutoff:
            raise ValueError('Future fire detection')
    return True


def daily_target(rows, target_date, station_pk, available_at):
    start, end = period(target_date)
    if aware(available_at) < end:
        raise ValueError('Outcome is not complete yet')
    if not station_pk or any(r.get('source_type') != 'measured' or r.get('station_pk') != station_pk for r in rows):
        raise ValueError('Target requires measured data from exactly one station')
    # Collapse duplicates deterministically; callers must supply normalized hourly mass units.
    by_time = {}
    evidence = []
    for r in sorted(rows, key=lambda r: (aware(r['valid_at']), aware(r['fetched_at']))):
        p = r['pollutant']
        if r.get('quality_state') != 'VALID' or r.get('normalized_unit') != ('mg/m3' if p == 'CO' else 'ug/m3'):
            continue
        at = aware(r['valid_at'])
        if not start-timedelta(hours=7) <= at < end:
            continue
        by_time.setdefault(at.isoformat(), {'time': at.isoformat()}).setdefault(p, r['normalized_value'])
        evidence.append(r.get('record_key'))
    calc = aggregate(list(by_time.values()), start, end)
    return {'station_pk': station_pk, 'target_date': str(target_date), 'target_start': start.isoformat(), 'target_end': end.isoformat(),
            'available_at': aware(available_at).isoformat(), 'calculation': calc, 'methodology_version': METHOD,
            'eligible_regression': calc['status'] == 'VALID', 'evidence_keys': sorted(set(x for x in evidence if x))}


def build_features(cams, weather, measured, issue_day, lat, lon, station_pk=None):
    """Input envelopes retain retrieval times; future forecast valid times are allowed."""
    cutoff = cutoff_for(issue_day)
    target_date = (cutoff.astimezone(IST)+timedelta(days=1)).date()
    start, end = period(target_date)
    inputs = [cams] + ([weather] if weather else []) + measured
    check_inputs(inputs, cutoff)
    if cams['source_type'] != 'modelled_forecast' or cams.get('model') != 'cams_global':
        raise ValueError('Baseline must be an actual CAMS forecast, never reanalysis')
    if (cutoff-aware(cams['available_at'])).total_seconds() > PROTOCOL['freshness_hours']['cams']*3600:
        raise ValueError('Stale CAMS input')
    if weather and ((cutoff-aware(weather['available_at'])).total_seconds() > PROTOCOL['freshness_hours']['weather']*3600 or weather['source_type'] != 'weather_forecast'):
        raise ValueError('Stale or non-forecast weather')
    baseline = aggregate(cams['rows'], start, end)
    if baseline['status'] not in ('VALID','LOWER_BOUND'):
        raise ValueError('Insufficient CAMS baseline')
    features = {'A_cams_aqi': baseline['aqi']}
    for p, entry in baseline['pollutants'].items():
        if entry['concentration'] is not None: features['A_'+p+'_daily'] = entry['concentration']
    for p in ('PM2.5','PM10','NO2','SO2','CO','O3'):
        values = [r[p] for r in cams['rows'] if start <= aware(r['time']) < end and finite(r.get(p))]
        if values:
            features['A_'+p+'_max'] = max(values)
            features['A_'+p+'_range'] = max(values)-min(values)
    if weather:
        for field in ('temperature_2m','relative_humidity_2m','wind_speed_10m','precipitation','surface_pressure','boundary_layer_height'):
            vals = [r[field] for r in weather['rows'] if start <= aware(r['time']) < end and finite(r.get(field))]
            if vals: features['C_'+field+'_mean'] = sum(vals)/len(vals)
        directions = [r['wind_direction_10m'] for r in weather['rows'] if start <= aware(r['time']) < end and finite(r.get('wind_direction_10m'))]
        if directions:
            features['C_wind_sin'] = sum(math.sin(math.radians(v)) for v in directions)/len(directions)
            features['C_wind_cos'] = sum(math.cos(math.radians(v)) for v in directions)/len(directions)
    measured_rows = [r for r in measured if r.get('station_pk') == station_pk and r.get('quality_state') == 'VALID'
                     and r.get('normalized_unit') == ('mg/m3' if r['pollutant'] == 'CO' else 'ug/m3') and finite(r.get('normalized_value'))]
    # Duplicate hours contribute once, using earliest retrieval.
    unique = {}
    for r in sorted(measured_rows, key=lambda r: aware(r['retrieved_at'])):
        unique.setdefault((r['pollutant'],str(r['valid_end'])), r)
    measured_rows = list(unique.values())
    observation_hours={}
    for r in measured_rows:
        at=aware(r['valid_end'])-timedelta(hours=1)
        observation_hours.setdefault(at.isoformat(),{'time':at.isoformat()})[r['pollutant']]=r['normalized_value']
    persistence=aggregate(list(observation_hours.values()),cutoff-timedelta(hours=24),cutoff,rolling=True)
    if persistence['status']=='VALID':features['B_persistence_aqi']=persistence['aqi']
    for p in ('PM2.5','PM10','NO2','SO2','CO','O3'):
        rs = sorted([r for r in measured_rows if r['pollutant']==p], key=lambda r: aware(r['valid_end']))
        for lag in (1,3,6,12,24,48):
            at = cutoff-timedelta(hours=lag)
            exact = [r['normalized_value'] for r in rs if at-timedelta(hours=1)<aware(r['valid_end'])<=at]
            if exact: features[f'B_{p}_lag{lag}'] = exact[-1]
        window = [r for r in rs if cutoff-timedelta(hours=24)<aware(r['valid_end'])<=cutoff]
        vals = [r['normalized_value'] for r in window]
        features[f'B_{p}_hours24'] = len(vals)
        if len(vals)>=16:
            import statistics
            features[f'B_{p}_mean24'] = statistics.mean(vals)
            features[f'B_{p}_median24'] = statistics.median(vals)
            features[f'B_{p}_std24'] = statistics.pstdev(vals)
            features[f'B_{p}_delta24'] = vals[-1]-vals[0]
            times = [(aware(r['valid_end'])-cutoff).total_seconds()/3600 for r in window]
            mt, mv = statistics.mean(times), statistics.mean(vals)
            denom = sum((t-mt)**2 for t in times)
            features[f'B_{p}_slope24'] = sum((t-mt)*(v-mv) for t,v in zip(times,vals))/denom if denom else 0
    local = cutoff.astimezone(IST)
    for name, angle in [('doy',2*math.pi*local.timetuple().tm_yday/365.25),('weekday',2*math.pi*local.weekday()/7)]:
        features['D_'+name+'_sin'],features['D_'+name+'_cos'] = math.sin(angle),math.cos(angle)
    features.update(E_lat=lat,E_lon=lon,E_grid_degrees=.4)
    return {'protocol_version': VERSION, 'feature_version': PROTOCOL['feature_version'], 'methodology_version': METHOD,
            'issue_time': cutoff.isoformat(), 'feature_cutoff': cutoff.isoformat(), 'target_date': str(target_date),
            'target_start': start.isoformat(), 'target_end': end.isoformat(), 'station_pk': station_pk,
            'features': features, 'cams_aqi': baseline['aqi'], 'cams_calculation': baseline,
            'input_availability': [{k:v for k,v in x.items() if k not in ('rows','raw','normalized_value')} for x in inputs],
            'snapshot_hash': digest([features,VERSION,str(target_date),station_pk])}
