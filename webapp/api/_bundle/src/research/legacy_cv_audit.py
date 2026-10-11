"""Reproduce original city-ordered CV leakage without changing or retraining artifacts."""
import json
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from src.models.common import AUX_COLUMNS,time_series_cv
from src import config


def audit():
    columns=json.loads((config.PROCESSED_DIR/'feature_columns.json').read_text(encoding='utf8'))
    frame=pd.read_csv(config.PROCESSED_DIR/'features_full.csv',parse_dates=['Date'])
    names=list(dict.fromkeys(['City','Date',config.TARGET_REGRESSION]+columns['regression']+[c for c in AUX_COLUMNS if c in frame]))
    original=frame[names].dropna();original=original[original.Date<pd.Timestamp(columns['split_boundary'])].reset_index(drop=True)
    out=[]
    for i,(tr,va) in enumerate(TimeSeriesSplit(n_splits=config.N_SPLITS_TS_CV).split(original)):
        out.append({'fold':i+1,'train_last':str(original.iloc[tr].Date.max().date()),'validation_first':str(original.iloc[va].Date.min().date()),
            'chronological_violation':bool(original.iloc[tr].Date.max()>=original.iloc[va].Date.min())})
    corrected=[]
    for i,(tr,va) in enumerate(time_series_cv(dates=original.Date).split(original)):
        corrected.append({'fold':i+1,'train_last':str(original.iloc[tr].Date.max().date()),'validation_first':str(original.iloc[va].Date.min().date()),
            'chronological_violation':bool(original.iloc[tr].Date.max()>=original.iloc[va].Date.min())})
    return {'original_folds':out,'corrected_date_blocks':corrected,'conclusion':'Original CV is not chronological; existing scores are invalid as temporal generalisation evidence. Split code fixed for future runs; original fitted artifacts and scores preserved and labelled.',
        'remaining':'Fold-specific preprocessing, feature selection and target encoding need nested evaluation; no new unbiased legacy score is claimed.'}
