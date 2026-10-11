"""Reconstruct sampled station frames from raw caches, bypassing derived caches."""
import json
import hashlib
from pathlib import Path
import pandas as pd
from src import config
from src.research.calibration import data
from src.research.calibration.measured import station_frames
from src.research.calibration.protocol import load
from src.research.calibration.checkpoint import OUT, verify, write_json


def audit():
    report=json.loads((OUT/'measured_dataset.json').read_text())
    root=(config.PROJECT_ROOT/report['table']).parent.parent
    snapshot=json.loads((root/'inputs.json').read_text())
    table=pd.read_parquet(config.PROJECT_ROOT/report['table'])
    actual=hashlib.sha256(table.to_json(orient='records',date_format='iso').encode()).hexdigest()
    if actual!=report['dataset_hash']:
        raise ValueError('Stored dataset semantic checksum mismatch')
    checks=[]
    dates=data.study_dates(load())
    for key in sorted(snapshot['stations'],key=int)[::max(1,len(snapshot['stations'])//5)]:
        entry=snapshot['stations'][key]
        for sensor in entry['sensors'].values():
            if sensor.get('file'):
                verify(sensor)
        rebuilt,_,_=station_frames(key,entry,dates)
        saved=table[table.station_id==int(key)]
        left=rebuilt.to_json(orient='records',date_format='iso')
        right=saved[rebuilt.columns].reset_index(drop=True).to_json(orient='records',date_format='iso')
        if left!=right:
            raise ValueError(f'Station {key} target/feature reproduction mismatch')
        checks.append({'station_id':int(key),'rows':len(rebuilt),'passed':True})
    result={'status':'PASS','dataset_hash':actual,'sampled_station_rebuilds':checks,
            'rebuild_bypassed_derived_cache':True,'clean_clone_reproduction_complete':False,
            'limitation':'Raw-cache reconstruction verified locally; clean-clone acquisition and complete primary results remain pending'}
    write_json(OUT/'dataset_reproducibility.json',result)
    return result


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
