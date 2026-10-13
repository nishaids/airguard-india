"""Camera-ready tables with restrained header and group shading.

Every value is read from evidence/verified_numbers.json, the file the manuscript
macros (tables/numbers.tex) are generated from. Styling only: no number is typed here.
Requires in the preamble: booktabs, tabularx, xcolor with the table option, and the
colours TableHeader and TableGroup.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
N = json.loads((BASE / 'evidence' / 'verified_numbers.json').read_text())
TABLES = BASE / 'tables'
SETUP = (r'\setlength{\aboverulesep}{0pt}\setlength{\belowrulesep}{0pt}'
         r'\renewcommand{\arraystretch}{1.14}')


def integer(value):
    return f'{value:,}'.replace(',', '{,}')


def signed(value, digits=2):
    return f'{value:+.{digits}f}'.replace('-', '$-$').replace('+', '$+$')


def pct(value):
    return f'{value * 100:.1f}'


def head(*cells):
    return r'\rowcolor{TableHeader}' + ' & '.join(rf'\textbf{{{c}}}' for c in cells) + r'\\'


def group(columns, text):
    return rf'\rowcolor{{TableGroup}}\multicolumn{{{columns}}}{{l}}{{{text}}}\\'


def note(text):
    return [r'\\[3pt]', rf'\parbox{{\columnwidth}}{{\footnotesize {text}}}']


def table_point():
    p, h, pop, hist = N['point'], N['point_history'], N['population'], N['history_population']
    rows = [r'\begin{table}[!t]', r'\caption{Point Forecast Errors on Exact Development Targets}', r'\label{tab:point}',
            r'\centering', r'\footnotesize', SETUP + r'\setlength{\tabcolsep}{6pt}',
            r'\begin{tabularx}{\columnwidth}{X r r r}', r'\toprule', head('Model', 'MAE', 'RMSE', 'Bias'), r'\midrule',
            group(4, rf"\textit{{All exact pairs}}: $n={integer(pop['exact'])}$, {pop['stations']} stations, {pop['dates']} dates")]
    for label, key in (('Climatology', 'climatology'), ('Calendar Ridge', 'ridge_calendar_spatial'), ('Weather Ridge', 'ridge_strict')):
        rows.append(rf"{label} & {p[key]['mae']:.2f} & {p[key]['rmse']:.2f} & {signed(p[key]['bias'])}\\")
    rows += [r'\midrule',
             group(4, rf"\textit{{History-available pairs}}: $n={integer(hist['exact'])}$, {hist['stations']} stations, {hist['dates']} dates")]
    for label, key in (('Weather Ridge, refitted on these rows', 'ridge_strict_same_training'), ('Persistence', 'persistence'),
                       ('History Ridge', 'ridge_history')):
        rows.append(rf"{label} & {h[key]['mae']:.2f} & {h[key]['rmse']:.2f} & {signed(h[key]['bias'])}\\")
    rows += [r'\bottomrule', r'\end{tabularx}']
    rows += note('AQI units. Bias: forecast minus observed. The two groups are different populations; censored Severe outcomes are excluded.')
    rows.append(r'\end{table}')
    (TABLES / 'table1_point.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def table_intervals():
    u = N['uncertainty_rows']
    cats = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor']
    rows = [r'\begin{table}[!t]', r'\caption{Interval Coverage (\%) of Exact Targets, Overall and by Observed Category}', r'\label{tab:intervals}',
            r'\centering', r'\footnotesize', SETUP + r'\setlength{\tabcolsep}{2.5pt}',
            r'\begin{tabularx}{\columnwidth}{X c r r r r r r r}', r'\toprule',
            head('Method', 'Level', 'Overall', 'Good', 'Sat.', 'Mod.', 'Poor', 'V.~Poor', 'Width'), r'\midrule']
    for label, key in (('Split', 'split_0.8'), ('Split', 'split_0.9'), ('Mondrian', 'mondrian_0.9'), ('CQR', 'cqr_0.9')):
        e = u[key]
        cells = [pct(e['by_category'][c]['coverage']) for c in cats]
        cells[-1] = rf'\textbf{{{cells[-1]}}}'
        rows.append(rf"{label} & {int(e['nominal'] * 100)} & {pct(e['coverage'])} & " + ' & '.join(cells) + rf" & {e['mean_width']:.0f}\\")
    e = u['split_0.9']
    rows += [r'\midrule', r'\rowcolor{TableGroup}Pairs & & ' + integer(e['n_exact']) + ' & ' +
             ' & '.join(integer(e['by_category'][c]['n']) for c in cats) + r' & \\', r'\bottomrule', r'\end{tabularx}']
    rows += note('Nominal level is 80\\% or 90\\%; subgroup entries are empirical coverage on exact targets, pooled over 12 folds. '
                 'Sat.: Satisfactory. Mod.: Moderate. Width: mean width (AQI units). '
                 rf"No upper bound reaches 401 on the {e['censored_upper_reaches_401']['n']} censored Severe days.")
    rows.append(r'\end{table}')
    (TABLES / 'table2_intervals.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def table_warnings():
    w = N['warnings_rows']
    rows = [r'\begin{table}[!t]', r'\caption{Category Warning Losses (\%) on Development Outcomes, Censored Severe Days Included}',
            r'\label{tab:warnings}', r'\centering', r'\footnotesize', SETUP + r'\setlength{\tabcolsep}{3.6pt}',
            r'\begin{tabularx}{\columnwidth}{X r r r r r r}', r'\toprule',
            head('Policy', 'Folds', '$n$', 'Under', 'Over', 'Serious', 'Poor$+$'), r'\midrule']
    for label, key in (('P0: point forecast', 'P0'), ('P1: calibrated median', 'P1'), ('P2: 0.75 quantile', 'P2')):
        e = w[key]
        rows.append(rf"{label} & 12 & {integer(e['n'])} & {pct(e['under'])} & {pct(e['over'])} & {pct(e['serious_under'])} & "
                    rf"{pct(e['high_pollution_under'])}\\")
    rows += [r'\midrule']
    for label, key in (('P3: 10\\% target', 'P3_0.1'), ('P3: 5\\% target', 'P3_0.05')):
        e = w[key]
        rows.append(rf"{label} & {e['folds']} & {integer(e['n'])} & {pct(e['under'])} & {pct(e['over'])} & {pct(e['serious_under'])} & "
                    rf"{pct(e['high_pollution_under'])}\\")
    rows += [r'\bottomrule', r'\end{tabularx}']
    rows += note('Under: issued category below observed. Over: above observed. Serious: at least two bands below. '
                 'Poor$+$: under-warning among Poor-or-worse outcomes. P3 uses feasible folds only.')
    rows.append(r'\end{table}')
    (TABLES / 'table3_warnings.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


if __name__ == '__main__':
    table_point(), table_intervals(), table_warnings()
    print('tables written')
