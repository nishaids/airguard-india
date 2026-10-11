from datetime import datetime, timedelta, timezone
import copy
import pandas as pd
import pytest
from src.research.evaluation import folds
from src.research.protocol import PROTOCOL
from src.research.uncertainty import AdaptiveConformal, concentration_bounds, brier, quantile_score
from src.research.impact import population_exposure


def test_v2_final_window_is_90_global_dates_no_overlap():
    protocol=copy.deepcopy(PROTOCOL);protocol['splits'].update(training_days=365,final_test_days=90)
    dates=pd.date_range('2020-01-01',periods=550,tz='UTC')
    frame=pd.DataFrame({'target_date':dates.strftime('%Y-%m-%d'),
        'issue_time':dates-timedelta(hours=4),'target_available_at':dates+timedelta(hours=30)})
    splits=folds(frame,protocol=protocol)
    final=[x for x in splits if x['role']=='final_test'][0]
    assert len(final['test'])==90
    assert all(set(x['test']).isdisjoint(final['test']) for x in splits if x['role']=='validation')
    assert PROTOCOL['splits']['training_days']==90


def test_monotone_aqi_bounds_and_censored_upper():
    lo={'PM2.5':30,'PM10':50,'NO2':20};hi={'PM2.5':60,'PM10':100,'NO2':40}
    bounds=concentration_bounds(lo,hi)
    assert bounds['lower']==50 and bounds['upper']==100
    assert concentration_bounds(lo,{**hi,'PM2.5':300})['upper'] is None
    with pytest.raises(ValueError):concentration_bounds(lo,{'PM2.5':20,'PM10':100,'NO2':40})
    with pytest.raises(ValueError):concentration_bounds({'PM2.5':30},{'PM2.5':40})


def test_aci_only_updates_after_real_outcome_and_in_correct_direction():
    state=AdaptiveConformal();now=datetime(2026,1,1,tzinfo=timezone.utc)
    with pytest.raises(ValueError):state.update(True,now+timedelta(days=1),now)
    assert state.update(True,now,now)<.1
    with pytest.raises(ValueError):state.update(False,now,now)
    assert state.update(False,now+timedelta(days=1),now+timedelta(days=1))>.091
    assert brier(1,.8)==pytest.approx(.04) and quantile_score(10,8,.9)==1.8


def test_population_coverage_excludes_missing_and_rejects_duplicates():
    cells=[{'cell_id':'a','population':100,'aqi':220,'forecast_date':'2026-01-02'},
           {'cell_id':'b','population':50,'aqi':None}]
    result=population_exposure(cells,'2026-01-02','sha256')
    assert result['poor_plus_population']==100 and result['uncovered_population']==50
    with pytest.raises(ValueError):population_exposure(cells+[cells[0]],'2026-01-02','sha256')
