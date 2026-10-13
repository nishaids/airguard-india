"""Emit LaTeX tables and number macros from evidence/verified_numbers.json.

The manuscript never types a result by hand: main.tex reads tables/numbers.tex
and the three table files written here, so every printed value is bound to the
evidence file that the claim-evidence matrix cites.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
N = json.loads((BASE / 'evidence' / 'verified_numbers.json').read_text())
CAMS = json.loads((BASE / 'evidence' / 'cams_status.json').read_text())
TABLES = BASE / 'tables'
TABLES.mkdir(exist_ok=True)
MACROS = {}


def macro(name, value):
    assert name.isalpha(), name
    assert name not in MACROS, name
    MACROS[name] = str(value)


def num(value, digits=2):
    return f'{value:.{digits}f}'


def signed(value, digits=2):
    return f'{value:+.{digits}f}'.replace('-', '$-$').replace('+', '$+$')


def minus(value, digits=2):
    return f'{value:.{digits}f}'.replace('-', '$-$')


def integer(value):
    return f'{value:,}'.replace(',', '{,}')


def pct(value, digits=1):
    return f'{value * 100:.{digits}f}'


def point_table():
    p, h = N['point'], N['point_history']
    pop, hist = N['population'], N['history_population']
    rows = [r'\begin{table}[!t]', r'\caption{Point Forecast Errors on Exact Development Targets (AQI)}', r'\label{tab:point}',
            r'\centering', r'\footnotesize', r'\begin{tabular}{@{}lrrr@{}}', r'\toprule', r'Model & MAE & RMSE & Bias\\', r'\midrule',
            rf"\multicolumn{{4}}{{@{{}}l}}{{\textit{{All exact pairs}}: $n={integer(pop['exact'])}$, {pop['stations']} stations, {pop['dates']} dates}}\\"]
    for label, key in (('Climatology', 'climatology'), ('Calendar Ridge', 'ridge_calendar_spatial'), ('Weather Ridge', 'ridge_strict')):
        rows.append(rf"{label} & {num(p[key]['mae'])} & {num(p[key]['rmse'])} & {signed(p[key]['bias'])}\\")
    rows += [r'\midrule',
             rf"\multicolumn{{4}}{{@{{}}l}}{{\textit{{History-available pairs}}: $n={integer(hist['exact'])}$, {hist['stations']} stations, {hist['dates']} dates}}\\"]
    for label, key in (('Weather Ridge, refitted on these rows', 'ridge_strict_same_training'), ('Persistence', 'persistence'),
                       ('History Ridge', 'ridge_history')):
        rows.append(rf"{label} & {num(h[key]['mae'])} & {num(h[key]['rmse'])} & {signed(h[key]['bias'])}\\")
    rows += [r'\bottomrule', r'\end{tabular}', r'\\[2pt]', r'\parbox{\columnwidth}{\footnotesize Bias is forecast minus observed; '
             r'censored Severe outcomes are excluded.}', r'\end{table}']
    (TABLES / 'table1_point.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def interval_table():
    u = N['uncertainty_rows']
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    rows = [r'\begin{table}[!t]', r'\caption{Interval Coverage (\%) of Exact Targets Pooled Over 12 Folds, Overall and by Observed Category}',
            r'\label{tab:intervals}', r'\centering', r'\footnotesize', r'\setlength{\tabcolsep}{2.9pt}',
            r'\begin{tabular}{@{}lrrrrrrrr@{}}', r'\toprule',
            r'Method & Level & All & Good & Satis. & Moder. & Poor & V.~poor & Width\\', r'\midrule']
    for label, key in (('Split', 'split_0.8'), ('Split', 'split_0.9'), ('Mondrian', 'mondrian_0.9'), ('CQR', 'cqr_0.9')):
        e = u[key]
        cells = ' & '.join(pct(e['by_category'][c]['coverage']) for c in cats)
        rows.append(rf"{label} & {int(e['nominal'] * 100)} & {pct(e['coverage'])} & {cells} & {e['mean_width']:.0f}\\")
    e = u['split_0.9']
    rows += [r'\midrule', rf"Exact pairs & & {integer(e['n_exact'])} & " +
             ' & '.join(integer(e['by_category'][c]['n']) for c in cats) + r' & \\', r'\bottomrule', r'\end{tabular}', r'\\[2pt]',
             r'\parbox{\columnwidth}{\footnotesize Width: mean interval width (AQI units). Mondrian withholds '
             rf"{u['mondrian_0.9']['withheld']} intervals. "
             rf"On the {u['split_0.9']['censored_upper_reaches_401']['n']} censored Severe days no upper bound reaches 401.}}",
             r'\end{table}']
    (TABLES / 'table2_intervals.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def warning_table():
    w = N['warnings_rows']
    rows = [r'\begin{table}[!t]', r'\caption{Category Warning Losses (\%) on Development Outcomes, Censored Severe Days Included}',
            r'\label{tab:warnings}', r'\centering', r'\footnotesize', r'\setlength{\tabcolsep}{3.2pt}',
            r'\begin{tabular}{@{}lrrrrrr@{}}', r'\toprule',
            r'Policy & Folds & $n$ & Under & Over & Serious & Poor$+$\\', r'\midrule']
    for label, key in (('P0: point forecast', 'P0'), ('P1: calibrated median', 'P1'), ('P2: calibrated 0.75 quantile', 'P2')):
        e = w[key]
        rows.append(rf"{label} & 12 & {integer(e['n'])} & {pct(e['under'])} & {pct(e['over'])} & {pct(e['serious_under'])} & "
                    rf"{pct(e['high_pollution_under'])}\\")
    rows.append(r'\midrule')
    for label, key in (('P3: 10\\% target', 'P3_0.1'), ('P3: 5\\% target', 'P3_0.05')):
        e = w[key]
        rows.append(rf"{label} & {e['folds']} & {integer(e['n'])} & {pct(e['under'])} & {pct(e['over'])} & {pct(e['serious_under'])} & "
                    rf"{pct(e['high_pollution_under'])}\\")
    rows += [r'\bottomrule', r'\end{tabular}', r'\\[2pt]',
             r'\parbox{\columnwidth}{\footnotesize Under/Over: issued category below/above observed. Serious: two or more categories '
             r'below. Poor$+$: under-warning among Poor-or-worse outcomes.}', r'\end{table}']
    (TABLES / 'table3_warnings.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def macros():
    pop, hist, led = N['population'], N['history_population'], N['reproduction']['ledger']
    macro('nExact', integer(pop['exact'])), macro('nSevere', pop['censored_severe']), macro('nOutcomes', integer(pop['rows']))
    macro('nStations', pop['stations']), macro('nCities', pop['cities']), macro('nDates', pop['dates'])
    macro('nHist', integer(hist['exact'])), macro('nHistSevere', hist['censored_severe'])
    macro('devStationDays', integer(led['development_station_days'])), macro('devValid', integer(led['development_valid_targets']))
    macro('devRejected', integer(led['development_rejected_targets'])), macro('devStations', led['development_valid_stations'])
    macro('devCities', led['development_valid_cities'])
    macro('devRejectedShare', f"{led['development_rejected_targets'] / led['development_station_days'] * 100:.0f}")
    p, h = N['point'], N['point_history']
    macro('maeClim', num(p['climatology']['mae'])), macro('maeCal', num(p['ridge_calendar_spatial']['mae']))
    macro('maeWx', num(p['ridge_strict']['mae'])), macro('maePers', num(h['persistence']['mae']))
    macro('maeHist', num(h['ridge_history']['mae'])), macro('rmsePers', num(h['persistence']['rmse'])), macro('rmseHist', num(h['ridge_history']['rmse']))
    for name, key in (('WxClim', 'ridge_strict_vs_climatology'), ('WxCal', 'weather_ablation'),
                      ('HistPers', 'ridge_history_vs_persistence'), ('HistWx', 'history_ablation_conditional')):
        e = N['paired'][key]
        macro('d' + name, minus(e['mae_difference'])), macro('d' + name + 'Abs', num(abs(e['mae_difference'])))
        macro('d' + name + 'Lo', minus(e['ci95'][0])), macro('d' + name + 'Hi', minus(e['ci95'][1]))
        macro('d' + name + 'LoAbs', num(abs(e['ci95'][0]))), macro('d' + name + 'HiAbs', num(abs(e['ci95'][1])))
        macro('d' + name + 'Rel', f"{abs(e['relative_mae_change']) * 100:.1f}")
    macro('pHistPers', f"{N['paired']['ridge_history_vs_persistence']['holm_pvalue']:.3f}")
    folds = N['folds']
    macro('foldMaeMin', num(min(f['mae_ridge_strict'] for f in folds))), macro('foldMaeMax', num(max(f['mae_ridge_strict'] for f in folds)))
    macro('nFoldsClimBetter', len(N['folds_ridge_worse_than_climatology'])), macro('nFoldsPersBetter', len(N['folds_history_worse_than_persistence']))
    tw = N['training_window_sensitivity']['sliding_90d']
    macro('slidingWx', num(tw['ridge_strict'])), macro('slidingClim', num(tw['climatology']))
    s = N['spatial_rows']
    macro('nSpatial', integer(s['city']['n_exact'])), macro('nSpatialHigh', integer(s['city']['poor_or_worse_n']))
    macro('spatialStations', s['city']['stations']), macro('spatialDates', s['city']['dates'])
    macro('maeSpatialRef', num(s['city']['mae_reference']))
    for name, key in (('Station', 'station_id'), ('City', 'city'), ('Cluster', 'cluster'), ('Region', 'region')):
        e = s[key]
        macro('sp' + name, num(e['difference'])), macro('sp' + name + 'Lo', num(e['ci95'][0])), macro('sp' + name + 'Hi', num(e['ci95'][1]))
        macro('sp' + name + 'Rel', f"{e['relative'] * 100:.1f}"), macro('sp' + name + 'High', num(e['poor_or_worse_difference']))
        macro('sp' + name + 'HighLo', num(e['poor_or_worse_ci95'][0])), macro('sp' + name + 'HighHi', num(e['poor_or_worse_ci95'][1]))
    macro('spEast', num(s['region']['by_region']['East']['difference'])), macro('spNorth', num(s['region']['by_region']['North']['difference']))
    c = N['by_observed_category']
    macro('biasWxGood', signed(c['Good']['ridge_strict']['bias'], 1)), macro('biasWxPoor', minus(c['Poor']['ridge_strict']['bias'], 1))
    macro('biasWxVeryPoor', minus(c['Very Poor']['ridge_strict']['bias'], 1))
    macro('biasPersVeryPoor', minus(c['Very Poor']['persistence']['bias'], 1)), macro('biasHistVeryPoor', minus(c['Very Poor']['ridge_history']['bias'], 1))
    macro('nPoorPlus', integer(N['poor_or_worse']['events'])), macro('nVeryPoorPlus', integer(N['very_poor_or_worse']['events']))
    macro('poorPlusShare', f"{N['poor_or_worse']['events'] / pop['rows'] * 100:.0f}")
    assert N['poor_or_worse']['lower_category_issued'] == N['poor_or_worse']['events'] and N['very_poor_or_worse']['forecast_reaches_very_poor'] == 0
    sv = N['severe']
    assert sv['ridge_strict']['below_401'] == sv['ridge_strict']['n']
    macro('sevMaxWx', num(sv['ridge_strict']['max_forecast'], 1)), macro('sevShortWx', num(sv['ridge_strict']['mean_shortfall'], 1))
    macro('sevPersReach', sv['persistence']['n'] - sv['persistence']['below_401']), macro('sevHistReach', sv['ridge_history']['n'] - sv['ridge_history']['below_401'])
    macro('sevShortPers', num(sv['persistence']['mean_shortfall'], 1)), macro('sevShortHist', num(sv['ridge_history']['mean_shortfall'], 1))
    macro('sevStations', sv['stations']), macro('sevCities', sv['cities']), macro('sevFolds', sv['folds_represented'])
    u = N['uncertainty_rows']
    macro('covEighty', pct(u['split_0.8']['coverage'])), macro('covNinety', pct(u['split_0.9']['coverage']))
    macro('covNinetyLo', pct(u['split_0.9']['coverage_ci95'][0])), macro('covNinetyHi', pct(u['split_0.9']['coverage_ci95'][1]))
    macro('covEightyLo', pct(u['split_0.8']['coverage_ci95'][0])), macro('covEightyHi', pct(u['split_0.8']['coverage_ci95'][1]))
    fold_cov = [v['coverage'] for v in u['split_0.9']['by_fold'].values()]
    macro('covFoldMin', pct(min(fold_cov))), macro('covFoldMax', pct(max(fold_cov)))
    for name, cat in (('Good', 'Good'), ('Sat', 'Satisfactory'), ('Mod', 'Moderate'), ('Poor', 'Poor'), ('VeryPoor', 'Very Poor')):
        macro('covSplit' + name, pct(u['split_0.9']['by_category'][cat]['coverage']))
    macro('covMondVeryPoor', pct(u['mondrian_0.9']['by_category']['Very Poor']['coverage']))
    macro('covCqrVeryPoor', pct(u['cqr_0.9']['by_category']['Very Poor']['coverage']))
    macro('covCqrGood', pct(u['cqr_0.9']['by_category']['Good']['coverage']))
    macro('covSplitPoorPlus', pct(u['split_0.9']['poor_or_worse']['coverage']))
    macro('covSplitLow', pct(u['split_0.9']['good_or_satisfactory']['coverage']))
    for key in ('split_0.8', 'split_0.9', 'mondrian_0.9', 'cqr_0.9'):
        assert u[key]['censored_upper_reaches_401']['count'] == 0
        for cat in ('Poor', 'Very Poor'):
            assert u[key]['by_category'][cat]['below_lower'] == 0
    macro('shiftCorr', num(N['calibration_shift_correlation'], 2))
    macro('covPostMonsoon', pct(u['split_0.9']['by_season']['post_monsoon']['coverage']))
    w = N['warnings_rows']
    macro('underPzero', pct(w['P0']['under'])), macro('overPzero', pct(w['P0']['over']))
    macro('underPtwo', pct(w['P2']['under'])), macro('overPtwo', pct(w['P2']['over']))
    d = w['P2_minus_P0']
    macro('dUnder', pct(abs(d['under']))), macro('dUnderLo', pct(abs(d['under_ci95'][1]))), macro('dUnderHi', pct(abs(d['under_ci95'][0])))
    macro('dOver', pct(d['over'])), macro('dOverLo', pct(d['over_ci95'][0])), macro('dOverHi', pct(d['over_ci95'][1]))
    top = w['raw_quantiles']['0.975']
    macro('topUnder', pct(top['under'])), macro('topOver', pct(top['over'])), macro('topHighUnder', pct(top['high_pollution_under']))
    macro('highUnderPtwo', pct(w['P2']['high_pollution_under']))
    assert all(v['severe_issued_severe'] == 0 for v in w['raw_quantiles'].values()) and w['P2']['severe_issued_severe'] == 0
    for name, key in (('Ten', 'P3_0.1'), ('Five', 'P3_0.05')):
        e = w[key]
        macro('pThree' + name + 'Folds', e['folds']), macro('pThree' + name + 'Met', e['folds_meeting_target'])
        macro('pThree' + name + 'Under', pct(e['under'])), macro('pThree' + name + 'Over', pct(e['over']))
        macro('pThree' + name + 'Infeasible', len(e['infeasible_folds']))
    macro('camsVerified', CAMS['verified_chunks']), macro('camsPlanned', CAMS['planned_chunks'])
    macro('camsDates', CAMS['alignment']['dates']), macro('camsFailed', CAMS['failed_jobs'])
    assert CAMS['verified_chunks_rehashed_and_matching'] == CAMS['verified_chunks'] and CAMS['eligible_rolling_folds'] == 0
    macro('checksCompared', N['reproduction']['checks_compared'])
    assert N['reproduction']['max_abs_difference_from_frozen'] == 0.0
    lines = ['% Generated by scripts/make_tables.py from evidence/verified_numbers.json. Do not edit by hand.']
    lines += [rf'\newcommand{{\{name}}}{{{value}}}' for name, value in MACROS.items()]
    (TABLES / 'numbers.tex').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (BASE / 'evidence' / 'number_macros.json').write_text(json.dumps(MACROS, indent=1), encoding='utf-8')
    print(len(MACROS), 'macros')


if __name__ == '__main__':
    point_table(), interval_table(), warning_table(), macros()
