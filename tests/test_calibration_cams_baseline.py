from datetime import date
import numpy as np
from src.research.calibration import cams_baseline as baseline


def test_same_run_ist_target_support_and_mass_conversion():
    reference=20250218
    surface={}; level={}
    for lead in range(11,43):
        for param,value in ((210073,60e-9),(210074,100e-9),(134,100000)):
            surface[(reference,lead,param)]=np.array([value])
    for lead in range(9,43,3):
        for param,value in ((210203,50e-9),(210121,10e-9),(210122,10e-9),(210123,1e-6),(130,300),(133,.01)):
            level[(reference,lead,param)]=np.array([value])
    pv=np.zeros(276);pv[138+136]=.98;pv[138+137]=1
    row=baseline.derive_day(reference,surface,level,pv,[{'location_id':1,'latitude':28.6,'longitude':77.2}])[0]
    assert row['target_date']==date(2025,2,19)
    assert row['reference_time_utc']=='2025-02-18T00:00:00+00:00'
    assert row['issue_time_utc']=='2025-02-18T14:30:00+00:00'
    assert row['cams_aqi_static_three']==100
    assert row['cams_six']==100
    assert row['cams_conc_PM2.5']==60
    assert row['cams_conc_CO']<2
    assert not any(k.startswith('y_') for k in row)
