"""Shared two-hour relative exposure windows, distinct from official AQI."""
from datetime import timedelta
from statistics import mean
from src.nationwide.aqi import IST, subindex, valid, parse_time

VERSION='hourly-relative-practical-window-v2'
WINDOW_HOURS=2
POLLUTANTS=('PM2.5','PM10','NO2','SO2','CO','O3')


def instantaneous(values):
    indices={p:subindex(p,v,ozone_hourly=v if p=='O3' else None) for p,v in values.items() if p in POLLUTANTS}
    indices={p:v for p,v in indices.items() if v is not None}
    if len(indices)<3 or not {'PM2.5','PM10'} & indices.keys():return {'value':None,'dominant':None,'qualifier':'INSUFFICIENT_SUPPORT'}
    dominant=max(indices,key=lambda p:indices[p]['value'])
    return {'value':indices[dominant]['value'],'dominant':dominant,'qualifier':indices[dominant]['qualifier'],
            'sub_indices':indices,'notice':'Hourly relative exposure indicator, not official AQI or a safety threshold.'}


def choose_window(values, length=WINDOW_HOURS, start_hour=6, end_hour=21, highest=False):
    if len(values)!=24 or isinstance(length,bool) or not isinstance(length,int) or not 1<=length<=6 or not 0<=start_hour<end_hour<=24:
        raise ValueError('24 hourly values and valid practical hours/window length required')
    candidates=[]
    for start in range(start_hour,end_hour-length+1):
        selected=values[start:start+length]
        if all(valid(v) and v<=400 for v in selected): candidates.append((mean(selected),start))
    if not candidates:return None
    score,start=(max if highest else min)(candidates,key=lambda x:x[0])
    return {'start_hour':start,'end_hour':start+length,'mean':score,'length':length,'method':VERSION,
            'practical_hours':[start_hour,end_hour],'notice':'Relative exposure comparison. Missing/censored windows excluded; no claim of safe exposure.'}


def forecast_windows(rows, target_start, target_end, weather=(), start_hour=6, end_hour=21):
    daily=[r for r in rows if target_start<=parse_time(r['time'])<target_end]
    practical=[r for r in daily if start_hour<=parse_time(r['time']).astimezone(IST).hour<end_hour]
    common={p for p in POLLUTANTS if practical and all(valid(r.get(p)) for r in practical)}
    values=[None]*24;indexed={}
    for row in daily:
        at=parse_time(row['time']);hour=at.astimezone(IST).hour
        entry=instantaneous({p:row[p] for p in common})
        if entry['qualifier']=='EXACT':values[hour]=entry['value'];indexed[hour]=at
    blh={parse_time(r['time']):r.get('boundary_layer_height') for r in weather if valid(r.get('boundary_layer_height')) and target_start<=parse_time(r['time'])<target_end}
    outputs={}
    for field,highest in [('lower_exposure_window',False),('highest_exposure_window',True)]:
        window=choose_window(values,start_hour=start_hour,end_hour=end_hour,highest=highest)
        if not window:outputs[field]=None;continue
        hours=range(window['start_hour'],window['end_hour']);at=indexed[window['start_hour']]
        shallow=bool(blh) and any(blh.get(indexed[h])==min(blh.values()) for h in hours)
        outputs[field]={'start':at.isoformat(),'end':(at+timedelta(hours=WINDOW_HOURS)).isoformat(),
            'min_exposure_index':min(values[h] for h in hours),'max_exposure_index':max(values[h] for h in hours),
            'window_hours':WINDOW_HOURS,'practical_hours':[start_hour,end_hour],'common_pollutants':sorted(common),
            'methodology_version':VERSION,'meaning':'Instantaneous relative hourly exposure, not official AQI or zero health risk.',
            'boundary_layer_caveat':'This window includes the shallowest forecast boundary layer; local emissions may accumulate.' if shallow else 'Boundary-layer mixing and street-level emissions can change local exposure; modelled windows are approximate.'}
    return outputs
