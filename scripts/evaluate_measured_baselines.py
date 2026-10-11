"""Score the two baselines that need no forecast at all.

Persistence (yesterday's measured value) and climatology (this station's usual
value for this month) are the references every forecast must beat. Neither needs
an archived model forecast, so both can be scored today on the real station-days
in the archive, while the forecast comparison itself stays blocked on archived
issue-time CAMS runs.

What this is not: forecast skill. No model is evaluated here. These numbers
cannot enter the preregistered study, which requires matched issue-time
forecasts, a locked final test and the full baseline ladder in
docs/research/BASELINES.md. They are a floor, published so that any later claim
of improvement has something real to be measured against.

    python -m scripts.evaluate_measured_baselines
"""
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from src import config
from src.research.archive_targets import daily_targets, load_rows

MINIMUM_SCORED_DAYS = 30


def metrics(pairs):
    """MAE, RMSE, bias and R-squared for (predicted, observed) pairs."""
    if not pairs:
        return None
    errors = [predicted - observed for predicted, observed in pairs]
    observed = [value for _predicted, value in pairs]
    mean_observed = sum(observed) / len(observed)
    total = sum((value - mean_observed) ** 2 for value in observed)
    residual = sum(error ** 2 for error in errors)
    return {
        'n': len(pairs),
        'mae': round(sum(abs(error) for error in errors) / len(errors), 3),
        'rmse': round(math.sqrt(residual / len(errors)), 3),
        'mean_bias': round(sum(errors) / len(errors), 3),
        'r2': round(1 - residual / total, 4) if total else None,
        'observed_mean': round(mean_observed, 2),
    }


def category_agreement(pairs_with_bands):
    """Share of days where the predicted band equals the observed band."""
    if not pairs_with_bands:
        return None
    exact = sum(1 for predicted, observed in pairs_with_bands if predicted == observed)
    return round(exact / len(pairs_with_bands), 4)


def band_of(value):
    for limit, label in ((50, 'Good'), (100, 'Satisfactory'), (200, 'Moderate'),
                         (300, 'Poor'), (400, 'Very Poor')):
        if value <= limit:
            return label
    return 'Severe'


def main():
    rows = load_rows()
    if not rows:
        print('No archive rows; run python -m scripts.backfill_openaq_archive --sink files first.')
        return 1
    targets, excluded = daily_targets(rows)
    if not targets:
        print('No station-day produced a valid daily AQI.')
        return 1

    by_station = defaultdict(dict)
    for target in targets:
        by_station[target['station_pk']][target['date']] = target

    persistence, climatology, lower_bound_days = [], [], 0
    persistence_bands, climatology_bands = [], []
    per_station = []
    for station_pk, days in sorted(by_station.items()):
        ordered = sorted(days)
        station_persistence, station_climatology = [], []
        # Climatology is built from earlier days only. A mean that includes the
        # day being predicted is not a baseline, it is a peek.
        history = defaultdict(list)
        for day in ordered:
            observed = days[day]['aqi']
            if days[day].get('qualifier') == 'LOWER_BOUND':
                lower_bound_days += 1
            previous = days.get(day - timedelta(days=1))
            if previous:
                station_persistence.append((previous['aqi'], observed))
                persistence_bands.append((band_of(previous['aqi']), band_of(observed)))
            prior = history[day.month]
            if len(prior) >= 5:
                predicted = sum(prior) / len(prior)
                station_climatology.append((predicted, observed))
                climatology_bands.append((band_of(predicted), band_of(observed)))
            history[day.month].append(observed)
        persistence.extend(station_persistence)
        climatology.extend(station_climatology)
        per_station.append({
            'station_pk': station_pk, 'days': len(ordered),
            'first': str(ordered[0]), 'last': str(ordered[-1]),
            'persistence': metrics(station_persistence),
            'climatology': metrics(station_climatology),
        })

    summary = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source': 'data/archive via src/research/archive_targets.py',
        'status': 'MEASURED_BASELINES_ONLY_NOT_FORECAST_SKILL',
        'accepted_as_research_result': False,
        'station_days_available': len(targets),
        'stations': len(by_station),
        'excluded_station_days': excluded,
        'severe_lower_bound_days': lower_bound_days,
        'baselines': {
            'persistence': {
                'definition': 'yesterday\'s measured daily AQI at the same station (B1 in '
                              'docs/research/BASELINES.md, scored here on measured days only)',
                **(metrics(persistence) or {}),
                'band_agreement': category_agreement(persistence_bands),
            },
            'climatology': {
                'definition': 'mean of this station\'s earlier days in the same calendar month, '
                              'computed from prior days only, minimum five (B0)',
                **(metrics(climatology) or {}),
                'band_agreement': category_agreement(climatology_bands),
            },
        },
        'per_station': per_station,
        'sufficient_days': len(persistence) >= MINIMUM_SCORED_DAYS,
        'limits': [
            'No model forecast is evaluated here, so nothing in this file is forecast skill.',
            'Days are consecutive calendar days at one station, so the errors are serially '
            'correlated; no confidence interval is reported because an independence assumption '
            'would be wrong and a block bootstrap belongs with the preregistered study.',
            'Severe days are censored at the open band and enter as lower bounds, which flatters '
            'any method on those days.',
            'Station coverage is a handful of sites reached through OpenAQ, not a national sample.',
        ],
    }
    out = config.PROJECT_ROOT / 'results/baselines_measured.json'
    out.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print(json.dumps({
        'station_days_available': summary['station_days_available'],
        'stations': summary['stations'],
        'persistence': summary['baselines']['persistence'],
        'climatology': summary['baselines']['climatology'],
    }, indent=1, default=str))
    print(f'artefact: {config.portable(out)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
