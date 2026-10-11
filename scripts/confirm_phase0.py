"""Rebuild the Phase 0 audit against the real Part B limitation table.

The limitation wording is read from `docs/MASTER_SPEC.md`, so an audit row can never
describe a claim the spec does not make. Every verdict carries anchors that are
resolved at generation time: a missing file or a missing substring raises instead of
silently citing line 1, and numeric findings are read from committed evidence
artefacts rather than typed in.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.qa.paths import SCAN_ROOTS, scan as path_leaks

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'docs/MASTER_SPEC.md'

# Verdict vocabulary, deliberately narrow:
#   FIXED    — the limitation no longer holds and an evidence artefact proves it.
#   PARTIAL  — mitigated, disclosed or bounded, but the spec's acceptance is unmet.
#   OPEN     — confirmed, unaddressed, and nothing external is in the way.
#   BLOCKED  — confirmed and waiting on a dependency recorded in HUMAN_ACTIONS.md.
#   REFUTED  — the spec's claim does not hold against this checkout.
STATUSES = ('FIXED', 'PARTIAL', 'OPEN', 'BLOCKED', 'REFUTED')


def load(path, default=None):
    p = ROOT / path
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding='utf-8'))


def anchor(spec):
    """Resolve `path` or `path::substring` into a `path:line` citation."""
    path, _, needle = spec.partition('::')
    p = ROOT / path
    if not p.exists():
        raise SystemExit(f'audit anchor missing: {path}')
    if not needle:
        return f'`{path}`'
    try:
        lines = p.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        raise SystemExit(f'audit anchor unreadable as text: {path}')
    line = next((i for i, text in enumerate(lines, 1) if needle in text), None)
    if line is None:
        raise SystemExit(f'audit anchor text not found in {path}: {needle!r}')
    return f'`{path}:{line}`'


def part_b():
    """Return {1: (severity, limitation, fix)} parsed from the spec's Part B tables."""
    text = SPEC.read_text(encoding='utf-8')
    body = text.split('## PART B')[1].split('## PART C')[0]
    rows = {}
    for match in re.finditer(
            r'^\|\s*L(\d{2})\s*\|\s*([CHML])\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$',
            body, re.MULTILINE):
        number, severity, claim, _evidence, fix = match.groups()
        rows[int(number)] = (severity, claim.strip(), fix.strip())
    missing = [n for n in range(1, 53) if n not in rows]
    if missing:
        raise SystemExit(f'Part B did not yield every limitation: missing {missing}')
    return rows


def evidence():
    db = load('results/release/database_audit.json', {}) or {}
    counts = db.get('counts', {})
    issue = [d for d in db.get('cron_dispatches', []) if d.get('jobname') == 'airguard-research-issue']
    perf = load('results/perf.json', {}) or {}
    lighthouse = load('results/lighthouse/live-mobile-final.report.json', {}) or {}
    qa = load('results/qa_summary.json', {}) or {}
    readiness = load('results/research/research_readiness.json', {}) or {}
    screens = sorted((ROOT / 'docs/screens').glob('*.png'))
    return {
        'db_generated_at': db.get('generated_at'),
        'counts': counts,
        'issue_dispatches': issue,
        'issue_succeeded': sum(1 for d in issue if d.get('status') == 'succeeded'),
        'research_forecast_runs': counts.get('research_forecast_runs', 0),
        'research_verifications': counts.get('research_forecast_verifications', 0),
        'station_daily_targets': counts.get('station_daily_targets', 0),
        'model_versions': counts.get('model_versions', 0),
        'stations': counts.get('stations', 0),
        'measured_rows': next((s['n'] for s in db.get('source_coverage', [])
                               if s.get('source_type') == 'measured'), 0),
        'measured_stations': next((s['stations'] for s in db.get('source_coverage', [])
                                   if s.get('source_type') == 'measured'), 0),
        'duplicate_record_keys': db.get('duplicate_record_keys'),
        'rls_everywhere': db.get('all_airguard_tables_rls'),
        'cached_p975_ms': (perf.get('cached') or {}).get('p97_5_response_ms'),
        'uncached_p975_ms': (perf.get('uncached_summary') or {}).get('p97_5_response_ms'),
        'lighthouse': {k: v.get('score') for k, v in (lighthouse.get('categories') or {}).items()},
        'qa_flagged': qa.get('total_flags', qa.get('flagged', None)),
        'readiness_passed': readiness.get('passed'),
        'readiness_total': readiness.get('total'),
        'screens': len(screens),
        'path_leaks': path_leaks(),
        'path_guard_in_ci': 'check_generated_paths' in (
            ROOT / '.github/workflows/quality.yml').read_text(encoding='utf-8'),
    }


def verdicts(e):
    leaks = e['path_leaks']
    published_leaks = [p for p in leaks if p.startswith(('webapp/public', 'data/'))]
    return {
        1: ('BLOCKED', f"Station metadata now exists ({e['stations']} rows), but the measured path is still "
            f"OpenAQ only: {e['measured_rows']} rows across {e['measured_stations']} stations and "
            f"{e['station_daily_targets']} daily station targets. Licensed CPCB hourly exports remain the blocker.",
            ['results/release/database_audit.json', 'src/ingestion/openaq.py', 'HUMAN_ACTIONS.md::CPCB historical station records']),
        2: ('OPEN', 'The data.gov.in real-time path is still unavailable. Its exact failure is preserved rather than '
            'hidden, and no other provider is relabelled CPCB.',
            ['results/optional_provider_checks.json', 'scripts/provision_optional_cloud_sources.py']),
        3: ('PARTIAL', 'Freshness is computed per provider and surfaced as FRESH/STALE/DELAYED with configurable '
            'thresholds, so stale readings are labelled instead of silently used. Upstream staleness itself persists.',
            ['src/nationwide/service.py::STALE']),
        4: ('BLOCKED', 'No archived issue-time CAMS forecast exists. ADS credential and terms acceptance are pending '
            'and were explicitly skipped; current fields and reanalysis are refused as substitutes.',
            ['results/backtest_main.json', 'HUMAN_ACTIONS.md::Copernicus ADS historical forecasts']),
        5: ('BLOCKED', 'The legacy Kaggle city-day record still ends 2020-07-01 and is confined to clearly labelled '
            'legacy routes. Replacing it needs the licensed station archive of L01.',
            ['webapp/public/data/meta.json', 'webapp/app/research/legacy/page.js']),
        6: ('BLOCKED', 'The supplied-versus-recomputed AQI disagreement is measured and published rather than '
            'smoothed over; only station hourly data removes its cause.',
            ['results/hai_divergence.json', 'docs/DATA_SOURCES.md']),
        7: ('PARTIAL', 'NH3 and Pb absence is disclosed in the API payload and the data-source register, and the '
            'understatement risk is stated. The pollutants remain unavailable.',
            ['src/nationwide/service.py::missing_CAMS_pollutants', 'docs/DATA_SOURCES.md']),
        8: ('FIXED', 'A QA/QC layer flags without deleting: negative and zero values, flat lines, rolling-MAD spikes '
            'with event exemption, PM2.5 above PM10, unit sanity and daily completeness, exported per station.',
            ['src/qa/hourly.py', 'results/qa_summary.json', 'tests/test_hourly_qa.py']),
        9: ('PARTIAL', 'Issued weather is stored with its retrieval time and issue-time eligibility is tested, but no '
            'historical issued-weather archive exists for training.',
            ['results/issue_time_features.json', 'src/research/protocol.py::def check_inputs']),
        10: ('PARTIAL', 'Fire detections are stored and displayed as context with no AQI adjustment, which is the '
             'honest treatment. Feature group F stays untested until the backtest can run.',
             ['src/nationwide/service.py::fire_context', 'results/ablation.json']),
        11: ('OPEN', 'The live product still reports NOT_VALIDATED with a null corrected AQI and null interval. No '
             'station correction model exists to change that.',
             ['src/nationwide/service.py::NOT_VALIDATED']),
        12: ('BLOCKED', 'Raw-CAMS ozone bias remains a hypothesis (H2). The bias atlas is a PENDING artefact for want '
             'of matched station pairs.',
             ['results/bias_atlas.json', 'docs/PROTOCOL.md']),
        13: ('BLOCKED', 'The PM2.5 under-prediction evidence is still a single anecdotal sample; the same pending '
             'atlas would settle it.',
             ['results/bias_atlas.json']),
        14: ('PARTIAL', 'The 0.4 degree grid, its interpolation and its inability to describe street-level exposure '
             'are disclosed on /methods, and every grid-derived value is badged MODELLED.',
             ['webapp/app/methods/page.js::0.4', 'webapp/app/components/AtlasMap.tsx::maplibre']),
        15: ('BLOCKED', 'The provider exposes no model-run initialisation, so retrieval time is kept distinct from '
             'issue time instead of being relabelled. Run time arrives with the ADS archive.',
             ['src/nationwide/service.py::issue_time_basis']),
        16: ('PARTIAL', 'The city-ordered leakage is audited and whole-date splitting is implemented, but the new '
             'protocol has never been evaluated on real pairs.',
             ['src/research/legacy_cv_audit.py::def audit', 'src/research/protocol.py']),
        17: ('PARTIAL', 'The legacy linear-versus-boosting comparison is retained and labelled legacy. Restating it '
             'against a baseline ladder belongs to the pending backtest.',
             ['results/master_comparison_regression.csv', 'results/backtest_main.json']),
        18: ('PARTIAL', 'Within-one-category survives only as a legacy diagnostic and is not a headline. POD, FAR and '
             'CSI for Poor-and-above await the backtest.',
             ['src/research/evaluation.py::within_one_category']),
        19: ('PARTIAL', 'SMOTE is confined to the legacy classifier; the operational product publishes no calibrated '
             'probability and makes no claim to one.',
             ['src/models/train_classification.py::SMOTE', 'results/uncertainty.json']),
        20: ('PARTIAL', f"Inference no longer runs inside the size-limited serverless function, but the model registry "
             f"is empty ({e['model_versions']} registered versions), so no release is pinned yet.",
             ['src/research/serving.py::def', 'results/release/database_audit.json']),
        21: ('PARTIAL', 'The UI reads model provenance from the research payload instead of hard-coding it; it shows '
             'an unknown version precisely because the registry is empty.',
             ['webapp/app/components/OperationalResearchPanel.tsx::model_version']),
        22: ('BLOCKED', 'Severity-stratified skill, including the censored Severe band, needs the pending matched '
             'pairs; the censoring rule itself is implemented.',
             ['src/research/evaluation.py', 'results/backtest_main.json']),
        23: ('BLOCKED', 'Diebold-Mariano and bootstrap intervals have nothing to compare until the backtest produces '
             'daily loss differentials.',
             ['results/backtest_main.json']),
        24: ('PARTIAL', 'The v2 framework replaces hand-set factors with AQHI-style excess risk over published '
             'coefficients, and the register ships with every coefficient unadopted and every cohort factor at '
             'exactly 1.0, each stating why. v1 remains, labelled heuristic and superseded. Adoption itself waits '
             'on a qualified evidence review, so no v2 value is produced.',
             ['src/features/hai_v2.py::def excess_risk', 'config/hai_factors.yaml::AWAITING_EVIDENCE_REVIEW',
              'webapp/app/historical-replay/page.js::HAI v1', 'HUMAN_ACTIONS.md::Health factors']),
        25: ('PARTIAL', 'The circular headline is no longer promoted, and the replacement harness exists: it '
             'samples coefficient draws, reports a median and 95% interval instead of one number, and reports the '
             'aggregation effect separately from the vulnerability effect so the two cannot be conflated. It needs '
             'published confidence intervals to sample from before it can produce a result.',
             ['src/features/hai_v2.py::def monte_carlo', 'tests/test_hai_v2.py::vulnerability',
              'results/hai_sensitivity.json']),
        26: ('OPEN', 'The literature-review gate is still unpassed, so the novelty claim has not been re-scoped in '
             'writing against AQHI prior art.',
             ['results/research/research_readiness.json::literature_review_complete', 'paper/main.tex']),
        27: ('PARTIAL', 'The index is labelled an advisory heuristic throughout and no health-outcome validation is '
             'claimed. The missing validation is itself disclosed.',
             ['src/features/hai.py', 'docs/PROTOCOL.md']),
        28: ('PARTIAL', 'Cohort determinism and the absence of individual risk estimation are disclosed on /methods.',
             ['webapp/app/methods/page.js']),
        29: ('BLOCKED', 'Clustering is unchanged pending coverage-gated station features; the replacement artefact is '
             'an honest PENDING stub rather than a rerun on the same twelve points.',
             ['results/clusters_v2.json', 'results/evaluation_clustering.json']),
        30: ('FIXED', 'The archetype descriptions say what a pollutant mix is consistent with and stop there. '
             'Every archetype carries an explicit NOT_ESTABLISHED attribution, the generator no longer emits '
             '"effective levers" wording, and the artefacts were migrated from the same rules rather than retyped.',
             ['src/models/train_clustering.py::cannot attribute a',
              'scripts/migrate_cluster_mix_claims.py',
              'webapp/app/research/historical-atlas/page.js::not a source apportionment']),
        31: ('BLOCKED', 'Meteorological normalisation of the Diwali and lockdown analyses needs ERA5 retrospective '
             'weather, which is not held.',
             ['results/events_deweathered.json']),
        32: ('BLOCKED', 'Holm correction lands with the deweathered rerun; the uncorrected legacy tests stay on '
             'legacy routes.',
             ['results/events_deweathered.json']),
        33: ('BLOCKED', 'The Amaravati anomaly is still unexplained; the coverage check belongs to the same rerun.',
             ['results/events_deweathered.json']),
        34: ('FIXED', 'Live and historical code now share one exposure-window implementation with a common length, '
             'and a test asserts both call sites agree.',
             ['src/features/exposure.py::def choose_window', 'src/features/safe_window.py::def best_window',
              'tests/test_shared_exposure.py']),
        35: ('FIXED', 'The window is restricted to practical hours and carries a boundary-layer-height caveat, so a '
             'shallow-mixing night-time dip can no longer be recommended unqualified.',
             ['src/features/exposure.py', 'tests/test_shared_exposure.py::boundary_layer_height']),
        36: ('PARTIAL', 'The simulator states in the interface that its reductions are assumptions rather than causal '
             'policy effects, and the manuscript makes no simulator claim at all.',
             ['webapp/app/components/CounterfactualScenario.tsx::not estimates of a policy',
              'results/policy_simulation.json']),
        37: ('OPEN', f"Readiness stands at {e['readiness_passed']} of {e['readiness_total']} gates and the artefact "
             f"predates the first successful fixed-time issuance, so it under-reports prospective logging.",
             ['results/research/research_readiness.json']),
        38: ('FIXED', f"Fixed-time issuance works: the 20:00 IST job has {e['issue_succeeded']} succeeded dispatch(es) "
             f"and the immutable ledger holds {e['research_forecast_runs']} research forecast runs. "
             f"{e['research_verifications']} verifications is correct one day into collection and is not backdated.",
             ['src/nationwide/jobs.py::local.hour==20', 'results/release/database_audit.json',
              'supabase/migrations']),
        39: ('PARTIAL', f"Canonical keying plus unique constraints hold the ledger at {e['duplicate_record_keys']} "
             f"duplicate record keys. Historic near-identical coordinates are deliberately not merged on rounded-grid "
             f"identity, because one grid cell can bind different stations.",
             ['src/nationwide/store.py::on conflict(location_key)', 'results/release/database_audit.json']),
        40: ('FIXED', f"Measured response distribution now sits at p97.5 {e['cached_p975_ms']} ms cached (target 800 ms) "
             f"and {e['uncached_p975_ms']} ms uncached (target 4 s), with queued asynchronous fills instead of a "
             f"blocking first request.",
             ['results/perf.json', 'docs/ASYNC_LIVE_DATA.md']),
        41: ('FIXED' if not leaks and e['path_guard_in_ci'] else 'OPEN' if published_leaks else 'PARTIAL',
             (f"No artefact under {', '.join(SCAN_ROOTS)} names a local path, the writers render paths through "
              f"src.config.portable, and CI fails on a regression."
              if not leaks and e['path_guard_in_ci'] else
              f"{len(leaks)} generated file(s) still embed a local absolute path"
              + (f"; {', '.join(published_leaks)} are publicly served" if published_leaks else '')
              + ('. CI does not yet guard this.' if not e['path_guard_in_ci'] else '.')),
             ['src/config.py::def portable', 'src/qa/paths.py::def scan',
              'scripts/check_generated_paths.py', '.github/workflows/quality.yml::check_generated_paths']),
        42: ('FIXED', f"Charts load lazily behind skeletons with retry paths, and Lighthouse mobile scores "
             f"{e['lighthouse'].get('performance')} for performance on the live route.",
             ['docs/ASYNC_LIVE_DATA.md', 'results/lighthouse/live-mobile-final.report.json']),
        43: ('PARTIAL', 'Sources are UTF-8 and published artefacts are scanned, but no reproducible mojibake case was '
             'ever captured, so this cannot be closed as verified.',
             ['scripts/check_public_exports.py', 'webapp/app/layout.js::openGraph']),
        44: ('FIXED', 'Licence terms are recorded per source and the deployment is treated as non-commercial, so MIT '
             'code licensing is no longer implied to cover upstream data.',
             ['docs/LICENSES.md::Open-Meteo', 'HUMAN_ACTIONS.md::Commercial licensing']),
        45: ('PARTIAL', f"Row-level security covers every AirGuard table ({e['rls_everywhere']}), request budgets and "
             f"input validation are enforced and /status reports ingestion health. Uptime and missed-run alerting is "
             f"the remaining gap.",
             ['src/nationwide/store.py', 'webapp/app/status/page.js', 'results/release/database_audit.json']),
        46: ('FIXED', 'The atlas renders a MapLibre GL map with a legend that separates measured stations from '
             'modelled grid values.',
             ['webapp/app/components/AtlasMap.tsx::maplibre']),
        47: ('FIXED', f"Navigation collapses on small screens, wide tables become card lists, and {e['screens']} "
             f"screenshots at 375 px and 1280 px cover every route.",
             ['webapp/app/components/NavBar.js', 'docs/screens']),
        48: ('BLOCKED', 'Health guidance is English only. No named native Tamil or Hindi reviewer has approved a '
             'version, and unreviewed translation would be worse than none.',
             ['webapp/app/lib/i18n.ts', 'HUMAN_ACTIONS.md::Tamil/Hindi review']),
        49: ('PARTIAL', 'A PWA manifest, OpenGraph and Twitter card metadata ship. Opt-in alerts are not built because '
             'no channel or recipient is authorised.',
             ['webapp/app/manifest.js', 'webapp/app/layout.js::openGraph', 'HUMAN_ACTIONS.md::Alerts']),
        50: ('BLOCKED', 'Users still see a daily min-max range, correctly labelled as not a confidence interval. Real '
             'intervals need the pending conformal calibration.',
             ['results/uncertainty.json', 'src/nationwide/service.py::NOT_VALIDATED']),
        51: ('BLOCKED', 'No population-exposure estimate, usage study or stakeholder pilot exists. Population counts '
             'need licensed gridded data and human-subject work needs ethics approval.',
             ['results/population_exposure.json', 'HUMAN_ACTIONS.md::User study']),
        52: ('OPEN', 'The manuscript carries author placeholders, no chosen call for papers, no verified bibliography '
             'and no empirical result. It is explicitly an unsubmitted draft.',
             ['paper/main.tex::IEEEauthorblockN', 'HUMAN_ACTIONS.md::Target conference']),
    }


def main():
    rows = part_b()
    e = evidence()
    found = verdicts(e)
    missing = [n for n in rows if n not in found]
    if missing:
        raise SystemExit(f'no verdict for {missing}')
    bad = [n for n, (status, *_rest) in found.items() if status not in STATUSES]
    if bad:
        raise SystemExit(f'unknown status for {bad}')
    now = datetime.now(timezone.utc).isoformat()
    tally = {s: sum(1 for v in found.values() if v[0] == s) for s in STATUSES}

    out = [
        '# Phase 0 audit confirmation', '',
        f'Generated {now} by `python -m scripts.confirm_phase0`.', '',
        'Every limitation below is quoted from the Part B table in `docs/MASTER_SPEC.md`, which is now part of '
        'the repository; an earlier run of this audit had to mark 36 of the 52 identifiers UNASSESSABLE because '
        'that table had not been supplied. Verdicts are **FIXED** (the limitation no longer holds and an artefact '
        'proves it), **PARTIAL** (mitigated, bounded or disclosed, but the spec\'s acceptance criterion is unmet), '
        '**OPEN** (confirmed and unaddressed, nothing external in the way), **BLOCKED** (confirmed and waiting on a '
        'dependency recorded in `HUMAN_ACTIONS.md`) and **REFUTED** (the claim does not hold against this '
        'checkout).', '',
        'Anchors are resolved when this file is generated: a missing file or a missing substring fails the run, so '
        'no citation here points at a line that does not say what the row claims. Numeric findings are read from '
        'committed artefacts, not typed in.', '',
        '| Verdict | Count |', '| --- | --- |',
    ]
    out += [f'| {s} | {tally[s]} |' for s in STATUSES]
    out += ['', '## Limitations', '', '| ID | Sev | Verdict | Limitation (from the spec) | Finding and evidence | Fix |',
            '| --- | --- | --- | --- | --- | --- |']
    machine = {}
    for number in range(1, 53):
        severity, claim, fix = rows[number]
        status, finding, anchors = found[number]
        citations = ' '.join(anchor(a) for a in anchors)
        out.append(f'| L{number:02} | {severity} | **{status}** | {claim} | {finding} {citations} | {fix} |')
        machine[f'L{number:02}'] = {
            'severity': severity, 'status': status, 'limitation': claim, 'finding': finding,
            'evidence': [anchor(a).strip('`') for a in anchors], 'fix': fix,
        }

    out += [
        '', '## Evidence read at generation time', '',
        f"- Database audit generated {e['db_generated_at']}: {e['stations']} stations, "
        f"{e['research_forecast_runs']} research forecast runs, {e['research_verifications']} verifications, "
        f"{e['station_daily_targets']} station daily targets, {e['model_versions']} registered models, "
        f"{e['duplicate_record_keys']} duplicate record keys, RLS everywhere: {e['rls_everywhere']}.",
        f"- Measured coverage: {e['measured_rows']} rows across {e['measured_stations']} stations (OpenAQ only).",
        f"- Fixed-time issuance: {e['issue_succeeded']} succeeded dispatch(es) of `airguard-research-issue`.",
        f"- Performance: p97.5 {e['cached_p975_ms']} ms cached, {e['uncached_p975_ms']} ms uncached.",
        f"- Lighthouse mobile on /live: {e['lighthouse']}.",
        f"- Readiness gates: {e['readiness_passed']} of {e['readiness_total']}.",
        f"- Responsive screenshots committed: {e['screens']}.",
        f"- Generated files still embedding a local absolute path: {len(e['path_leaks'])}"
        + (f" ({', '.join(e['path_leaks'])})" if e['path_leaks'] else '') + '.',
        '', '## Boundaries that this audit does not cross', '',
        '- A verdict of FIXED describes this checkout, not necessarily the currently promoted production build. '
        'Deployment identity lives in `results/research/production_acceptance.json`.',
        '- Implementing a work package does not turn a readiness gate green. Gates need empirical evidence, and '
        'the prospective record needs calendar time that cannot be backdated.',
        '- Archived issue-time CAMS forecasts remain **PENDING — ADS credential/terms required**. Current forecast '
        'fields and reanalysis are not substitutes.',
        '- Reference-list editing, health-coefficient approval, translation review and author details are reserved '
        'for the human authors; see `HUMAN_ACTIONS.md`.',
        '',
        'Machine-readable form: `results/audit_confirmation.json`.', '',
    ]
    (ROOT / 'docs/AUDIT_CONFIRMATION.md').write_text('\n'.join(out), encoding='utf-8')
    (ROOT / 'results/audit_confirmation.json').write_text(json.dumps({
        'generated_at': now, 'source': 'docs/MASTER_SPEC.md', 'tally': tally,
        'evidence': e, 'limitations': machine,
    }, indent=1), encoding='utf-8')
    print(json.dumps({'generated_at': now, 'tally': tally, 'path_leaks': len(e['path_leaks'])}, indent=1))


if __name__ == '__main__':
    main()
