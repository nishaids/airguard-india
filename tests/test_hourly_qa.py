from datetime import datetime, timedelta, timezone
from src.qa.hourly import audit


def readings(n=24, pollutant='PM2.5', value=10):
    start = datetime(2026,1,1,18,30,tzinfo=timezone.utc)
    return [{'station_pk':1,'source_type':'measured','pollutant':pollutant,
        'normalized_unit':'mg/m3' if pollutant=='CO' else 'ug/m3','normalized_value':value,
        'valid_at':(start+timedelta(hours=i)).isoformat(),'record_key':str(i)} for i in range(n)]


def test_flatline_retained_and_unique_hours():
    rows = readings(); result = audit(rows + [rows[0]])
    assert result['rows_deleted']==0 and len(rows)==24
    assert result['flags_by_code']['FLATLINE_6H']==24
    assert result['flags_by_code']['DUPLICATE_HOUR']==1
    assert result['daily_completeness'][0]['unique_hours']==24


def test_gaps_do_not_count_as_contiguous_flatline():
    rows = readings(6); rows[-1]['valid_at']=readings(8)[-1]['valid_at']
    assert 'FLATLINE_6H' not in audit(rows)['flags_by_code']


def test_station_pm_consistency_and_units():
    rows = readings(1,value=30)+readings(1,'PM10',20)
    rows += [dict(readings(1,'CO')[0], normalized_unit='ug/m3')]
    report=audit(rows)
    assert report['flags_by_code']['PM25_GT_PM10']==2
    assert report['flags_by_code']['UNIT_MISMATCH']==1
    assert len(report['daily_completeness'])==2


def test_negative_nonfinite_and_model_grid_not_targets():
    rows=readings(3); rows[0]['normalized_value']=-1; rows[1]['normalized_value']=float('nan');rows[2]['source_type']='modelled_forecast'
    assert set(audit(rows)['flags_by_code'])=={'NEGATIVE','NON_FINITE','NOT_STATION_MEASUREMENT'}


def test_event_flags_keep_spikes_visible():
    rows=readings(24)
    for i,row in enumerate(rows): row['normalized_value']=10+i%3
    rows[-1]['normalized_value']=500
    window={'start':rows[-1]['valid_at'],'end':'2026-01-02T19:00:00+00:00','reference':'official event export'}
    result=audit(rows,[window])
    assert result['flags_by_code']['MAD_SPIKE']==1
    assert result['flags_by_code']['SPIKE_EVENT_REVIEW']==1
    assert result['rows_deleted']==0


def test_completeness_is_by_ist_day_and_station():
    assert audit(readings(15))['daily_completeness'][0]['complete'] is False
    assert audit(readings(16))['daily_completeness'][0]['complete'] is True
    rows=readings(24);rows[-1]['station_pk']=2
    assert audit(rows)['daily_completeness'][1]['unique_hours']==1
