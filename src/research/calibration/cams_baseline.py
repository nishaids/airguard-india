"""Derive partial raw CAMS indices from verified forecast cubes, never targets.

No observations, model selection or final-test labels are read. This forecast
table is NOT a completed guarded model dataset; joins/availability evidence
remain separate. Fixed three-species and six-species indices are both retained.
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from src.research.calibration import cams_acquisition as archive
from src.research.calibration import cams_physics as physics
from src.research.calibration.checkpoint import canonical_hash, write_json
from src.research.calibration.catalogue import SELECTION
from src.nationwide.aqi import aggregate, IST
from src.nationwide import aqi
from src.research.calibration.validation import normalized_text_sha256


def extract(path, job, stations):
    import eccodes as ec
    cube={}; indices=None
    with Path(path).open('rb') as f:
        while (g:=ec.codes_grib_new_from_file(f)) is not None:
            try:
                if indices is None:
                    lat=ec.codes_get_array(g,'latitudes'); lon=ec.codes_get_array(g,'longitudes')
                    indices=[]
                    for station in stations:
                        cell=(round(round(station['latitude']/.4)*.4,1),round(round(station['longitude']/.4)*.4,1))
                        found=np.where(np.isclose(lat,cell[0],atol=1e-6)&np.isclose(lon,cell[1],atol=1e-6))[0]
                        if len(found)!=1: raise ValueError('Station cell does not uniquely exist in acquired grid')
                        indices.append(int(found[0]))
                key=(ec.codes_get(g,'dataDate'),int(ec.codes_get(g,'step')),ec.codes_get(g,'paramId'))
                if key in cube: raise ValueError('Duplicate raw operational field')
                cube[key]=ec.codes_get_values(g)[indices]
            finally: ec.codes_release(g)
    return cube


def derive_day(reference_date, surface, level, pv, stations):
    reference=datetime.strptime(str(reference_date),'%Y%m%d').replace(tzinfo=timezone.utc)
    target=(reference+timedelta(days=1)).date()
    start=datetime.combine(target,datetime.min.time(),tzinfo=IST).astimezone(timezone.utc)
    # Seven preceding bins support the first trailing eight-hour O3/CO window.
    hours=np.array([11.5+i for i in range(31)])
    def field(cube,param):
        leads=sorted(k[1] for k in cube if k[0]==reference_date and k[2]==param)
        return physics.interpolate(leads,np.stack([cube[(reference_date,x,param)] for x in leads]),hours)
    pressure=physics.lowest_level_pressure(field(surface,134),pv)
    temperature,humidity=field(level,130),field(level,133)
    concentrations={'PM2.5':field(surface,210073)*1e9,'PM10':field(surface,210074)*1e9}
    for pollutant,param in (('O3',210203),('NO2',210121),('SO2',210122),('CO',210123)):
        concentrations[pollutant]=physics.mass_concentration(field(level,param),temperature,humidity,pressure,co=pollutant=='CO')
    if not all(np.isfinite(a).all() and (a>=0).all() for a in concentrations.values()):
        raise ValueError('Invalid converted operational concentration')
    results=[]
    for column,station in enumerate(stations):
        series=[{'time':(reference+timedelta(hours=float(h))).isoformat(),
                 **{p:float(values[i,column]) for p,values in concentrations.items()}} for i,h in enumerate(hours)]
        three=[{k:v for k,v in row.items() if k in ('time','PM2.5','PM10','O3')} for row in series]
        primary=aggregate(three,start,start+timedelta(days=1))
        six=aggregate(series,start,start+timedelta(days=1))
        record={'station_id':int(station['location_id']),'target_date':target,'latitude':station['latitude'],
                'longitude':station['longitude'],'cell_latitude':round(round(station['latitude']/.4)*.4,1),
                'cell_longitude':round(round(station['longitude']/.4)*.4,1),
                'reference_time_utc':reference.isoformat(),'issue_time_utc':(start-timedelta(hours=4)).isoformat(),
                'cams_aqi_static_three':primary['aqi'],'cams_three_qualifier':primary['qualifier'],
                'cams_six':six['aqi'],'cams_six_qualifier':six['qualifier'],
                'cams_dominant_static_three':primary['dominant_pollutant'],
                'support_policy':'STATIC_PM25_PM10_O3_NO_OUTCOME_MISSINGNESS',
                'availability_basis':'documented nominal dissemination; no per-run historical delivery log',
                'methodology_version':primary['methodology_version']}
        for p,details in six['pollutants'].items():
            if p not in concentrations: continue
            record['cams_conc_'+p]=details['concentration']
            record['cams_sub_'+p]=details['sub_index']['value'] if details['sub_index'] else None
            daily = concentrations[p][7:, column]
            record['cams_hourly_max_'+p] = float(daily.max())
            record['cams_hourly_range_'+p] = float(np.ptp(daily))
            record['cams_hourly_std_'+p] = float(daily.std())
            record['cams_hourly_day_minus_night_'+p] = float(daily[6:18].mean()-np.r_[daily[:6],daily[18:]].mean())
        results.append(record)
    return results


def build():
    plan=archive.freeze()
    state=json.loads(archive.STATE.read_text(encoding='utf-8'))
    if state['plan_sha256']!=plan['sha256']: raise ValueError('Plan and raw manifest differ')
    stations=json.loads(SELECTION.read_text(encoding='utf-8'))['stations']
    rows=[]; files={}
    for i in range(0,len(plan['jobs']),2):
        jobs=plan['jobs'][i:i+2]; entries=[state['jobs'].get(j['id'],{}) for j in jobs]
        if not all(e.get('status')=='VERIFIED_GRIB' for e in entries): continue
        for j,e in zip(jobs,entries):
            path=archive.ROOT/e['file']
            if archive.sha(path)!=e['sha256']: raise ValueError('Raw operational checksum differs')
            archive.validate_file(path,j)
            files[e['file']]=e['sha256']
        surface=extract(archive.ROOT/entries[0]['file'],jobs[0],stations)
        level=extract(archive.ROOT/entries[1]['file'],jobs[1],stations)
        for value in jobs[0]['request']['date']:
            target=date.fromisoformat(value)+timedelta(days=1)
            if not date.fromisoformat(plan['target_range'][0])<=target<=date.fromisoformat(plan['target_range'][1]): continue
            rows.extend(derive_day(int(value.replace('-','')),surface,level,entries[1]['hybrid_coefficients'],stations))
    if not rows: raise ValueError('No paired verified forecast chunks yet')
    frame=pd.DataFrame(rows).sort_values(['station_id','target_date']).reset_index(drop=True)
    if frame.duplicated(['station_id','target_date']).any(): raise ValueError('Duplicate forecast station-day')
    code={name:normalized_text_sha256(path) for name,path in (
        ('baseline',Path(__file__)),('physics',Path(physics.__file__)),('aqi',Path(aqi.__file__)))}
    identity=canonical_hash({'plan':plan['sha256'],'files':files,'code':code})
    folder=archive.ROOT/'data/research/cams_operational/derived'/identity
    folder.mkdir(parents=True,exist_ok=True); path=folder/'raw_cams_indices.parquet'
    manifest=folder/'manifest.json'
    if manifest.exists():
        existing=json.loads(manifest.read_text(encoding='utf-8'))
        if not path.is_file() or archive.sha(path)!=existing['sha256']:
            raise ValueError('Existing derived CAMS table checksum differs; never overwrite it')
    if not path.exists(): frame.to_parquet(path,index=False)
    value={'status':'COMPLETE_FORECAST_DERIVATION' if state['complete'] else 'PARTIAL_FORECAST_DERIVATION',
        'dataset_identity':identity,'plan_sha256':plan['sha256'],'raw_file_sha256':files,'code_sha256':code,
        'table':path.relative_to(archive.ROOT).as_posix(),'sha256':archive.sha(path),
        'rows':len(frame),'stations':frame.station_id.nunique(),'dates':frame.target_date.nunique(),
        'date_range':[str(frame.target_date.min()),str(frame.target_date.max())],
        'valid_three_species_indices':int(frame.cams_aqi_static_three.notna().sum()),
        'valid_six_species_indices':int(frame.cams_six.notna().sum()),
        'measured_targets_read':False,'final_test_accessed':False,'primary_model_dataset_complete':False,
        'evaluation_performed':False,'future_work':'complete acquisition, issue-time guarded joins, development validation and selection before final access'}
    if not manifest.exists(): write_json(manifest,value)
    write_json(archive.ROOT/'results/research/cams_raw_baseline_derivation.json',value)
    return value


if __name__=='__main__':
    value=build(); print(json.dumps({k:value[k] for k in ('status','rows','stations','dates','date_range')}))
