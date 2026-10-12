from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest
from src.research.calibration.operational_features import history_features, neighbour_features
from src.research.calibration.availability import Cutoffs, LeakageError


def test_daily_history_is_date_keyed_and_excludes_yesterday_and_censored_bias():
    day=date(2025,3,10)
    rows=pd.DataFrame([dict(station_id=1,target_date=day,cams_aqi_static_three=70)])
    obs=pd.DataFrame([dict(station_id=1,target_date=day-timedelta(days=lag),
                          y_aqi=value,target_valid=True,censored=censored)
                      for lag,value,censored in [(1,999,False),(2,401,True),(3,80,False),(7,90,False)]])
    fc=obs[['station_id','target_date']].assign(cams_aqi_static_three=50)
    actual=history_features(rows,obs,fc).iloc[0]
    assert np.isnan(actual.history_lag2) and actual.history_lag2_censored==1
    assert actual.history_lag3==80 and actual.history_lag7==90
    assert np.isnan(actual.bias_lag2) and actual.history_roll7_n==2
    assert actual.cams_previous_day==50 and actual.cams_day_change==20


def donor_fixture():
    day=date(2025,3,10)
    rows=pd.DataFrame([dict(station_id=i,target_date=day,latitude=10,longitude=77+i*.01,
                           region='South',cluster=i,obs24_aqi=i*100,
                           latest_measured_bin_end_utc=Cutoffs.for_target(day).measurement)
                       for i in (1,2,3)])
    return rows


def test_spatial_donors_exclude_self_and_can_exclude_holdout_feeds():
    rows=donor_fixture()
    actual=neighbour_features(rows.iloc[:1], rows, donor_ids={2})
    assert actual.iloc[0].nbr50_obs24_mean==200
    assert actual.iloc[0].nbr50_count==1
    rows['y_aqi']=99999  # contemporary target never enters neighbours
    assert neighbour_features(rows.iloc[:1],rows,donor_ids={2}).equals(actual)


def test_future_neighbour_bin_is_rejected_before_aggregation():
    rows=donor_fixture()
    rows.loc[1,'latest_measured_bin_end_utc']+=timedelta(hours=1)
    with pytest.raises(LeakageError):
        neighbour_features(rows.iloc[:1],rows)
