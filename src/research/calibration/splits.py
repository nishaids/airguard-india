"""Chronological folds and spatial holdouts, exactly as the protocol fixes them.

A fold is a set of whole calendar dates. Every station's row for a date moves
together, training always precedes calibration, calibration precedes test, and
an embargo day separates them. Nothing here shuffles.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np


def calendar(protocol):
    first = date.fromisoformat(str(protocol['study_window']['first_date']))
    last = date.fromisoformat(str(protocol['study_window']['last_date']))
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def rolling_folds(dates, protocol):
    """Expanding-window folds plus the locked final test, over a continuous calendar."""
    cfg = protocol['splits']
    train, calib, test = int(cfg['minimum_training_days']), int(cfg['calibration_days']), int(cfg['test_days'])
    step, gap, final = int(cfg['step_days']), int(cfg['embargo_days']), int(cfg['final_test_days'])
    dates = sorted(dates)
    final_start = len(dates) - final
    folds = []

    def fold(name, role, train_end, test_start, test_end):
        calibration_start, calibration_end = train_end + gap, test_start - gap
        return {
            'name': name, 'role': role,
            'train': dates[:train_end], 'calibration': dates[calibration_start:calibration_end],
            'test': dates[test_start:test_end],
            'train_range': [str(dates[0]), str(dates[train_end - 1])],
            'calibration_range': [str(dates[calibration_start]), str(dates[calibration_end - 1])],
            'test_range': [str(dates[test_start]), str(dates[test_end - 1])],
        }

    number = 1
    for test_start in range(train + calib + 2 * gap, final_start, step):
        if test_start + test > final_start:
            break
        folds.append(fold(f'fold_{number:02d}', 'rolling', test_start - calib - 2 * gap, test_start, test_start + test))
        number += 1
    if final_start >= train + calib + 2 * gap:
        folds.append(fold('final_test', 'final_test', final_start - calib - 2 * gap, final_start, len(dates)))
    return folds


def check(folds):
    """Raise if any fold lets training or calibration touch or follow its test."""
    for fold in folds:
        if not fold['train'] or not fold['calibration'] or not fold['test']:
            raise ValueError(f"{fold['name']} has an empty partition.")
        if not max(fold['train']) < min(fold['calibration']) <= max(fold['calibration']) < min(fold['test']):
            raise ValueError(f"{fold['name']} is not strictly chronological.")
        if set(fold['train']) & set(fold['calibration']) or set(fold['calibration']) & set(fold['test']):
            raise ValueError(f"{fold['name']} has overlapping partitions.")
    rolling = [f for f in folds if f['role'] == 'rolling']
    final = [f for f in folds if f['role'] == 'final_test']
    if final and rolling and max(max(f['test']) for f in rolling) >= min(final[0]['test']):
        raise ValueError('A rolling test window reaches into the locked final test.')
    return True


def inner_validation(train_dates, days=30):
    """Split a training window for tuning: the last `days` are validation."""
    train_dates = sorted(train_dates)
    return train_dates[:-days], train_dates[-days:]


def spatial_frame(dates, protocol):
    """The single temporal frame inside which spatial holdouts are run."""
    final = int(protocol['splits']['final_test_days'])
    dates = sorted(dates)
    train_end = date(2025, 10, 31)
    test_start = date(2025, 11, 2)
    test_end = dates[len(dates) - final - 1]
    return {
        'train': [d for d in dates if d <= train_end],
        'test': [d for d in dates if test_start <= d <= test_end],
        'train_range': [str(dates[0]), str(train_end)],
        'test_range': [str(test_start), str(test_end)],
    }


def grouped_folds(groups, k=10, seed=42):
    """Assign each distinct group to one of k folds, reproducibly."""
    unique = sorted(set(groups))
    order = np.random.default_rng(seed).permutation(len(unique))
    assignment = {unique[index]: position % k for position, index in enumerate(order)}
    return assignment
