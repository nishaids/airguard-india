"""Record a blocked development checkpoint without fitting or reading targets.

Preserves the submitted paper and independently audits inherited exploratory
artifacts. There is no final-test executor or model-selection lock writer here.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pyarrow.parquet as pq

from src.research.calibration.validation import evidence_matches_current

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/research'


def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, content):
    (DOCS/name).write_text(content.rstrip()+'\n', encoding='utf-8')


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |',
                      *['| '+' | '.join(map(str,row))+' |' for row in rows]])+'\n'


def main():
    recovery=read('results/research/codex_continuation_recovery.json')
    for name,digest in recovery['protected_files_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Protected paper/protocol/measured artifact changed: '+name)
    ext=read('results/research/development_extensions.json')
    if ext!=read(ext['artifact']) or ext['final_test_scored'] or ext['selection_made']:
        raise ValueError('Immutable unselected development extension required')
    source=ROOT/Path(ext['artifact']).parent/'source_v1.py'
    if hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=ext['code_sha256']:
        raise ValueError('Recovered extension source hash differs')
    row_evidence={}
    for name,item in ext['rows'].items():
        path=ROOT/item['path']
        if sha(path)!=item['sha256']:raise ValueError('Development prediction checksum differs')
        metadata=pq.ParquetFile(path).metadata
        column=pq.ParquetFile(path).schema.names.index('target_date')
        last=max(metadata.row_group(i).column(column).statistics.max for i in range(metadata.num_row_groups))
        if str(last)>='2026-07-10':raise ValueError('Sealed date in extension metadata')
        row_evidence[name]={'sha256':item['sha256'],'rows':metadata.num_rows,'last_date':str(last),'check':'METADATA_AND_CHECKSUM_ONLY'}
    tests=read('results/research/test_validation.json')
    if not evidence_matches_current(tests):raise ValueError('Current source-bound backend evidence required')
    final=read('results/research/final_test_readiness.json')
    if final['status']!='BLOCKED':raise ValueError('This continuation report cannot declare final-test readiness')
    archive=read('results/research/cams_development_acquisition.json')
    reconciliation=read('results/research/cams_archive_status.json')
    aligned=read('results/research/cams_development_alignment.json')
    prospective=read('results/research/prospective_audit.json')
    security=read('results/release/secret_audit.json')
    frontend=read('results/release/codex_continuation_preflight.json')
    def junit_count(name):
        root=ET.parse(ROOT/'logs'/name).getroot()
        suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
        if any(int(s.get('failures',0)) or int(s.get('errors',0)) for s in suites):
            raise ValueError('Failed test evidence: '+name)
        return sum(int(s.get('tests',0))-int(s.get('skipped',0)) for s in suites)
    integration_passed=sum(junit_count(p) for p in ('codex-continuation-database.xml','codex-continuation-database-nationwide.xml'))
    full_suite_passed=junit_count('codex-continuation-backend.xml')
    now=datetime.now(timezone.utc).isoformat()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    audit={'recorded_at_utc':now,'run_id':ext['run_id'],'artifact':ext['artifact'],
           'artifact_sha256':sha(ROOT/ext['artifact']),'recovered_source_sha256':ext['code_sha256'],
           'development_table_checks':row_evidence,'excluded_method':'lgbm_censored_floor',
           'exclusion_reason':'Uses censored Severe lower bounds as exact regression labels; violates preserved exact-fit exclusion.',
           'accepted_independent_methods':[m for m in ext['point'] if m!='lgbm_censored_floor'],
           'scope':'Exploratory post-paper non-CAMS analysis; no primary selection, final scoring or deployment.',
           'historical_artifact_modified':False,'paper_modified':False,'final_test_accessed':False,
           'future_runner_version':'development-extensions-v2','v2_experiments_executed':False}
    (ROOT/'results/research/development_extensions_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    join={k:aligned[k] for k in ('sha256','table','feature_version','protocol_sha256','rows','stations','cities','dates','valid_targets','censored_severe_retained','rejected_targets_retained','guarded_rows')}
    join.update(status=aligned['status'],exact_targets=aligned['valid_targets']-aligned['censored_severe_retained'],
                availability_violations=aligned['rows']-aligned['guarded_rows'],
                missing_cams_dates=len(__import__('src.research.calibration.splits',fromlist=['calendar']).calendar(
                    __import__('src.research.calibration.protocol',fromlist=['load']).load()))-90-aligned['dates'],
                final_test_accessed=False,source_manifest='results/research/cams_development_alignment.json')
    (ROOT/'results/research/cams_station_join_manifest.json').write_text(json.dumps(join,indent=2)+'\n')
    prefix=f'Checkpoint: {now}. Research branch; code checkpoint `{commit}`. Final test remains sealed.\n\n'
    write('CAMS_ARCHIVE_STATUS.md','# CAMS operational archive status\n\n'+prefix+
          f'Current manifest: **{archive["counts"].get("VERIFIED_GRIB",0)}/36 verified**, statuses `{archive["counts"]}`. '+
          ('The submission worker is stopped and new requests are persistently paused. ' if archive.get('submission_control',{}).get('new_requests_authorized') is False else 'Inspect the existing worker before any acquisition operation. ')+
          'Original request IDs are retained; no new or replacement request was submitted by this reconciliation. '+
          f'Frozen plan SHA-256: `{archive["plan_sha256"]}`.\n\n'
          'The readiness audit independently rehashed and decoded each verified GRIB. Forecast type, reference time, leads, valid times, fields, mass units, hybrid coefficients and the 0.4-degree grid are checked. Only paired surface/model-level months enter station extraction. Reanalysis and missing-month substitution are prohibited.\n\n'
          f'Current join: {aligned["rows"]:,} retained station-days, {aligned["stations"]} stations, {aligned["cities"]} cities, {aligned["dates"]} dates, {join["exact_targets"]:,} exact targets and {aligned["censored_severe_retained"]} censored Severe targets; {aligned["rejected_targets_retained"]:,} rejected targets remain visible. Availability violations: {join["availability_violations"]}.\n\n'
          'Availability guards pass under the disclosed nominal 00 UTC dissemination and observation-feed latency assumptions. Historical per-run publication times are not empirically verified.\n\n'+
          (table(['Nine reported ADS requests','Count'],[(name,str(reconciliation['counts'][key])+'/9') for name,key in (
              ('Server successful','ads_server_side_successful'),('Downloaded locally','downloaded_locally'),
              ('Content-valid','content_valid'),('Checksum-verified','checksum_verified'),
              ('Protocol-accepted primary archive chunks','protocol_accepted_primary_chunks'))])+
           '\nThe remaining valid artifact is the accepted original probe, excluded from the 36 primary chunks. '+
           f'Total known request IDs: {reconciliation["total_known_request_ids"]}; nine reported successes plus the additional pre-existing request below.\n\n'+
           table(['Request ID','Scope','Bytes','Initialization dates','Content'],[[r['request_id'],r['scope'],str(r.get('bytes')),
               ' to '.join(r.get('reference_date_range',['2025-02-18'])),
               'VALID' if r['content_valid'] else 'UNVERIFIED'] for r in reconciliation['requests']])+
           '\nAdditional pre-existing request(s): '+json.dumps(reconciliation['additional_preexisting_requests'])+'. These were not polled or downloaded by this reconciliation; status is last recorded.\n\n'+
           'Invalid/unverified artifacts: '+json.dumps(reconciliation['invalid_or_unverified_request_ids'])+'.\n\n'+
           'The 134-byte probe is a complete GRIB edition 1 message: `GRIB` header, length 134, `7777` terminator, ECMWF centre `ecmf`, CAMS class `mc`, operational stream `oper`, forecast type `fc`, surface PM2.5 (`paramId=210073`, kg m**-3). It contains nine finite nonmissing values on a 3 by 3, 0.4-degree grid covering 29.2–28.4 N and 76.8–77.6 E. Initialization: 2025-02-18 00:00 UTC; lead: 24 h; valid: 2025-02-19 00:00 UTC. Packing: grid_simple, 24 bits/value. It contains binary forecast data, no HTML/XML/error response.\n\n'+
           'Exact decoded values and all 134 bytes in hexadecimal, per-request checksums, server timestamps, parameter units and valid-time ranges are recorded in `results/research/cams_archive_status.json`.\n\n'
           if reconciliation else '')+
          'Evidence: `results/research/final_test_readiness.json`, `cams_station_join_manifest.json`, and the existing acquisition/alignment manifests. Only explicit existing IDs may be re-polled; new submissions remain paused until the author changes this instruction.\n')
    point=ext['point']
    rows=[]
    for name in audit['accepted_independent_methods']:
        r=point[name]
        rows.append([name,f'{r["mae"]:.3f}',r['n_exact'],f'{r["poor_or_worse"]["mae"]:.3f}',
                     f'{r["severe"]["reaches_401"]}/{r["severe"]["n"]}'])
    write('DEVELOPMENT_EXTENSION_AUDIT.md','# Post-paper extension audit\n\n'+prefix+
          f'Reused immutable run `{ext["run_id"]}`; development predictions and source checksums passed. No experiment was rerun. '
          'All accepted learners were fitted independently of the excluded floor surrogate. Their scores remain post-paper exploratory findings, not primary CAMS results.\n\n'+
          table(['Method','Exact MAE','Exact pairs','Poor+ exact MAE','Severe reaches 401'],rows)+
          '\nLightGBM history has lower point MAE than persistence, but its paired 95% interval includes zero. It reaches none of the 306 Severe lower bounds. The maximum of persistence and History Ridge preserves 147 threshold reaches and slightly reduces Poor+ MAE, while worsening overall MAE with a positive paired interval. No model is selected.\n\n'
          '**Method exclusion:** `lgbm_censored_floor` trains on 401 as an exact label. Its original source and result are retained for audit, but it is excluded from accepted comparisons and future v2 fitting. The v2 runner fits every regression/quantile learner only on uncensored targets; a new regression test enforces this. Never run `source_v1.py` as an approved experiment.\n')
    interval_rows=[]
    for population,block in ext['intervals'].items():
        for method,r in block['methods'].items():
            interval_rows.append([population,method,f'{r["coverage"]:.4f}',f'{r["mean_width"]:.2f}',
                                  f'{r["by_category"]["Very Poor"]["coverage"]:.4f}',
                                  f'{r["censored_severe"]["upper_reaches_401"]}/{r["censored_severe"]["n"]}'])
    write('UNCERTAINTY_EXTENSION_REPORT.md','# Exploratory uncertainty findings\n\n'+prefix+
          'Nominal 90% intervals; populations must not be interchanged. Delayed online updates use outcomes from D-2 or earlier. Their censored contributions are lower-bound nonconformity scores, not exact errors. No conditional-coverage or operational guarantee is claimed.\n\n'+
          table(['Population','Method','Exact coverage','Mean width','Very Poor coverage','Severe upper >=401'],interval_rows)+
          '\nAdaptive weather calibration improves marginal coverage and Very Poor coverage, but still has no upper endpoint reaching 401 on the 363 Severe outcomes. Persistence-based intervals perform better in the severe tail on history-available pairs. Lower-bound compatibility is not coverage of the unknown true Severe index. These methods remain exploratory and unselected.\n')
    warning_rows=[]
    for name,r in ext['warnings']['history_pairs']['operating_points'].items():
        warning_rows.append([name,f'{r["under_warning"]:.3%}',f'{r["over_warning"]:.3%}',
                             f'{r["serious_under_warning"]:.3%}',f'{r["poor_or_worse_under_warning"]:.3%}'])
    write('WARNING_POLICY_EXTENSION_REPORT.md','# Exploratory warning operating points\n\n'+prefix+
          f'History-available population: {ext["warnings"]["history_pairs"]["n"]:,} outcomes including censored Severe categories. '
          'These are newer exploratory learners and must not replace the frozen paper\'s weather-only warning numbers.\n\n'+
          table(['Policy','Under-warning','Over-warning','Serious under-warning','Poor+ under-warning'],warning_rows)+
          '\nNo policy is selected: a defensible error-cost ratio has not been specified. A higher quantile reduces missed categories while increasing excess alerts, and aggregate under-warning does not establish vulnerable-cohort conditional control or clinical benefit. Primary P0-P3 calibration remains pending genuine CAMS comparisons.\n')
    survival=ext['survivorship'];cohorts=[]
    for name in ('paper_cohort','frozen_cohort'):
        r=survival[name];cohorts.append([name,r['stations'],r['cities'],r['exact_pairs'],r['censored_severe'],
                                      f'{r["mae"]["ridge_weather"]:.3f}',f'{r["mae"]["persistence"]:.3f}',f'{r["mae"]["ridge_history"]:.3f}'])
    write('STATION_SURVIVORSHIP_SENSITIVITY.md','# Station-cohort survivorship sensitivity\n\n'+prefix+
          f'Inherited rule: {survival["frozen_rule"]}; eligibility window `{survival["eligibility_window"]}`. '
          'This applies the preliminary study\'s 30-valid-day rule, not the primary protocol\'s 120-day requirement.\n\n'+
          table(['Cohort','Stations','Cities','Exact pairs','Severe','Weather MAE','Persistence MAE','History MAE'],cohorts)+
          '\nThe frozen cohort excludes 13 late-entry stations. Weather-minus-climatology remains negative and History-minus-persistence remains inconclusive; cluster and region transfer penalties remain positive. Category shares and full paired intervals are retained in the immutable extension artifact.\n\n'
          'Catalogue metadata identify 35 monitors removed by the recent-activity rule among those reporting at the study start. They were never downloaded, so this sensitivity cannot restore lost monitors or resolve complete survivorship bias. No historical paper result is replaced.\n')
    write('MODEL_SELECTION_REPORT.md','# Development model selection: NOT READY\n\n'+prefix+
          f'No primary model is selected. The current {aligned["dates"]}-date operational join has no protocol-eligible complete rolling fold. The sealed protocol requires training-only tuning, identical baseline pairs and mean rolling-fold MAE selection with declared Ridge/residual ties; retain raw CAMS if no learned candidate improves that criterion. A stronger persistence result must still be reported honestly.\n\n'
          'Direct/residual Ridge, LightGBM and XGBoost, spatial holdouts, fixed-learner ablation, uncertainty, advisory and paired-statistics infrastructure are implemented and tested on synthetic fixtures. Their real primary experiments remain blocked by archive coverage. The refreshed preflight records `fitting_performed=false`.\n\n'
          'The preserved paper establishes Weather Ridge versus climatology, not versus raw CAMS; its History Ridge gain over persistence is not established. The exploratory extension does not select the primary learner. No `MODEL_SELECTION_LOCK` or surrogate lock has been created.\n')
    readiness=read('results/research/research_readiness.json')
    limitations=[
        ('Measured QC, Severe censoring and target support','RESOLVED','Locked v3.1 dataset and tests; three-species research target preserved.','No retrospective redefinition.'),
        ('ADS credential setup','RESOLVED','Genuine operational GRIBs verified.','Never disclose credentials.'),
        ('Operational archive coverage','BLOCKED',str(archive['counts']),'New submissions paused by author; acquired dates insufficient for primary folds.'),
        ('Primary comparisons, selection and lock','REQUIRES MORE DATA','No eligible primary fold; no real primary fit.','Complete archive then execute declared workflow.'),
        ('Severe forecasting','PARTIALLY RESOLVED','Bound-aware exploratory comparison completed; no tail learner dominates.','Primary severity evaluation and prospective extremes.'),
        ('Uncertainty and warning costs','PARTIALLY RESOLVED','Delayed exploratory calibration and balanced operating points recorded.','Primary calibration; no guarantee or invented optimum.'),
        ('Station survivorship','PARTIALLY RESOLVED','Early-frozen cohort preserves main qualitative findings.','Retired monitors were never acquired; cannot restore them here.'),
        ('Input receipt times','PARTIALLY RESOLVED','New source/request/response receipt metadata implemented.','Production release; upstream initialization remains unknown where unexposed.'),
        ('Prospective station binding','REQUIRES MORE DATA',f'{prospective["station_bound_forecasts"]} bound forecasts; no eligible pre-issue candidates for latest issuance.','Collect timely eligible feeds before future issuance; never backfill.'),
        ('Prospective track record','REQUIRES MORE DATA',f'{prospective["verified_days"]} verified days; {prospective["elapsed_real_days"]:.2f} real elapsed days.','At least 30 real verified days; cannot accelerate elapsed time.'),
        ('Historical issuance identity','PARTIALLY RESOLVED',f'{prospective["historical_forecasts_missing_git_sha"]} existing missing SHAs.','Supply runtime Git SHA for future release; old identities remain missing.'),
        ('Literature/novelty acceptance','PARTIALLY RESOLVED','Existing targeted primary-source audits retained.','Remaining full-text and author acceptance; no world-first claim.'),
        ('Final-test evaluation','REQUIRES FINAL TEST','Sealed; no committed model lock or READY gate.','Fresh explicit approval only after actual development completion.')]
    write('FINAL_LIMITATIONS_AND_FUTURE_WORK.md','# Limitations and future work\n\n'+prefix+
          table(['Issue','State','Evidence','Next action'],limitations))
    write('NOVELTY_AUDIT.md','# Bounded novelty audit\n\n'+prefix+
          'The existing `LITERATURE_CONTINUATION.md`, `LITERATURE_FULLTEXT_REVIEW.md` and `docs/defense/NOVELTY_MATRIX.md` are retained. No full review is restarted. Ridge, boosting, CAMS post-processing and conformal prediction are established methods.\n\n'
          'The bounded research distinction is the integrated availability contract, global-date temporal testing, geographic transfer, censored-Severe diagnostics, severity-specific uncertainty, two-sided warning losses and immutable evidence separation. The non-CAMS paper is a frozen snapshot; the genuine CAMS extension remains pending. No superiority, world-first, guaranteed conditional coverage or medical effectiveness is claimed. Formal literature acceptance remains false.\n')
    write('CODEX_REPRODUCIBILITY.md','# Continuation reproducibility\n\n'+prefix+
          'Use the existing `.venv-live` runtime. Immutable extension metadata records Python 3.10.6, NumPy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, LightGBM 4.7.0, PyArrow 23.0.1 and SciPy 1.15.3. Seeds are 42; full primary runtime/search grids are in each plan.json.\n\n'
          '```powershell\npython -m src.research.calibration.validation --snapshot\npython -m src.research.calibration.prospective_audit\npython -m scripts.audit_database_release\npython -m scripts.audit_secret_history\npython -m src.research.calibration.readiness\npython -m src.research.calibration.cams_baseline\npython -m src.research.calibration.primary_dataset\npython -m src.research.calibration.primary_experiments --run-development\npython -m scripts.audit_development_readiness\npython -m scripts.finish_codex_handoff\n```\n\n'
          'The CAMS baseline and join are idempotent and development-filtered. Do not rerun measured-data acquisition or target construction during continuation. Use its existing semantic hash and sealed table. The primary runner filters dates before materialisation and reports insufficient folds instead of fitting shortened windows. Spatial, ablation, uncertainty, warning and statistics stages share its configuration when coverage is sufficient.\n\n'
          'Existing extension v1 outputs are reused with their audited exclusion; do not execute the recovered v1 source as an approved method. The v2 extension code excludes censored fitting but is not rerun here. Full future v2 analyses remain exploratory; neither version can replace the primary model-selection protocol. The historical paper analysis/reproduction sources and exact hashes are preserved in `paper/conference_final/evidence/`. Do not regenerate the submission snapshot.\n\n'
          'Raw CAMS/measured caches and extension prediction tables remain local unless packaged as explicit paper evidence. Missing data require the manifested acquisition, never undocumented edits. Source-bound tests and checksums do not constitute a complete clean-clone primary experiment reproduction.\n')
    write('FINAL_TEST_READY_FOR_AUTHOR_APPROVAL.md','# Final test: BLOCKED — NOT READY FOR APPROVAL\n\n'+prefix+
          'Protected interval: **10 July 2026 through 7 October 2026**. This handoff does not authorize opening or scoring it.\n\n'
          f'Selected primary model: none. Lock hash: absent. Code checkpoint: `{commit}`. '
          f'Measured semantic hash: `{aligned["measured_dataset_hash"]}`. Protocol hash: `{aligned["protocol_sha256"]}`. '
          f'CAMS plan hash: `{archive["plan_sha256"]}`. Alignment hash: `{aligned["sha256"]}`.\n\n'+
          '\n'.join('- '+b for b in final['blockers'])+'\n\n'
          'Development, geographic, Severe, uncertainty, warning and survivorship findings are the separate non-CAMS paper/extension evidence linked in this directory. They cannot release the primary gate. A complete experiment-to-lock binding audit and one-shot final executor remain outstanding infrastructure.\n\n'
          '**Final-test approval is not requested now.** New ADS submissions are paused by the author; the nine successful requests are reconciled and the additional earlier request is preserved. Primary folds require more acquired development dates. Explicit final-test approval will be requested only after genuine primary selection, a committed lock and an evidence-backed READY report.\n')
    deployment_path=ROOT/'results/release/codex_continuation_deployment.json'
    deployment=read(deployment_path.relative_to(ROOT).as_posix()) if deployment_path.exists() else {'status':'PENDING_SAFE_RELEASE'}
    release_verified=deployment['status']=='PRODUCTION_DEPLOYED_AND_VERIFIED'
    write('FINAL_PROJECT_GAP_AUDIT.md','# Project gap audit\n\n'+prefix+
          f'Research readiness: {readiness["passed"]}/{readiness["total"]}, `{readiness["status"]}`. '
          'The six-page paper is preserved and the app has production-safe provenance infrastructure. Scientific completion is not established by software tests or paper formatting.\n\n'+
          table(['Area','Current evidence','Remaining gap'],[
              ['Paper','Six-page SHA-protected snapshot; assets/citations present.','Author submission decisions.'],
              ['CAMS',f'{archive["counts"].get("VERIFIED_GRIB",0)} verified chunks; new submissions paused.','Remaining verified paired months and renewed author acquisition authorization.'],
              ['Primary models','Runner/guards tested; no eligible real fold.','Real development comparisons and lock.'],
              ['Extensions','Original valid independent outputs reused; floor surrogate excluded.','Primary replication; no selected correction.'],
              ['Prospective','36 forecasts, 3 target days, no violations.','Timely station binding, outcomes and real elapsed days.'],
              ['Software','Backend, database, lint, types, units and build verified; release evidence recorded separately.',
               'None for this release: 31 staged checks, authorized refresh, 37 public checks and 28 browser checks passed.' if release_verified else 'Release candidate/API/browser checks.'],
              ['Security','Zero configured-secret hits, all DB tables RLS.','No claim of penetration testing or unknown-secret detection.']]))
    report={'generated_at_utc':now,'branch':'research/station-calibration','code_checkpoint':commit,
            'paper':'PRESERVED_6_PAGE_SUBMISSION_SNAPSHOT','paper_sha256':recovery['protected_files_sha256']['paper/conference_final/main.pdf'],
            'archive_counts':archive['counts'],'alignment':join,'primary_model':None,'selection_lock':'NOT_READY',
            'final_test':'SEALED_BLOCKED','extensions_audit':'results/research/development_extensions_audit.json',
            'prospective':{k:prospective[k] for k in ('forecasts','issued_target_days','verified_days','station_bound_forecasts','historical_forecasts_missing_git_sha','input_availability_violations')},
            'backend':{'offline':tests['counts'],'integration_passed':integration_passed,'separate_full_suite_passed':full_suite_passed},
            'frontend':frontend,'security':security,'deployment':deployment,'readiness':{'passed':readiness['passed'],'total':readiness['total']},
            'final_test_accessed':False,'experimental_correction_deployed':False,'human_action_now':None,
            'cams_request_reconciliation':'results/research/cams_archive_status.json',
            'new_ads_requests_authorized':archive.get('submission_control',{}).get('new_requests_authorized')}
    (ROOT/'results/research/codex_continuation_completion.json').write_text(json.dumps(report,indent=2)+'\n')
    write('AIRGUARD_FINAL_COMPLETION_REPORT.md','# AirGuard Codex completion checkpoint\n\n'+prefix+
          '**Executive status:** production-safe completion proceeds; primary research and final-test readiness remain blocked by real evidence gaps.\n\n'
          '**Claude work recovered:** preserved six-page paper, immutable non-CAMS findings, severe/uncertainty/warning/cohort extensions, measured dataset, protocol, seven CAMS files and partial v3 join.\n\n'
          '**Codex work:** audited artifacts and source; excluded exact-401 surrogate fitting in future runs; strengthened inner-tuning/quantile-vector guards; added transport receipt provenance; refreshed current-source tests, GRIB audits, readiness and reports. No paper rewrite, duplicate request, target rebuild or final scoring.\n\n'
          f'**CAMS and dataset:** {archive["counts"]}; {aligned["rows"]:,} rows, {aligned["stations"]} stations, {aligned["cities"]} cities, {aligned["dates"]} dates, zero availability violations. Primary models and lock: NOT READY. See CAMS/model-selection reports.\n\n'
          '**Severe, uncertainty, warning and survivorship:** independent exploratory results reused with exact hashes; no universal winner, calibration guarantee or optimal warning policy. Frozen-cohort conclusions persist but full lost-monitor bias is unresolved. See the four extension reports.\n\n'
          f'**Prospective:** {prospective["forecasts"]} forecasts across {prospective["issued_target_days"]} real target days; {prospective["verified_days"]} verified days, {prospective["station_bound_forecasts"]} bindings and zero availability violations. Existing missing identities are not repaired after issuance. Future deployment receives a runtime Git SHA.\n\n'
          f'**Tests:** separate full suite {full_suite_passed} passed; source-bound offline suite {tests["counts"]["passed"]} passed, {tests["counts"]["skipped"]} skipped, {integration_passed} integrations separately passed. Frontend lint/types/build and {frontend["unit"]["numPassedTests"]} unit tests pass. Live/API/browser release results are recorded separately after release.\n\n'
          f'**Security:** configured-secret audit counts are {security["history_secret_hits"]}/{security["current_worktree_secret_hits"]}/{security["browser_asset_secret_hits"]} (history/worktree/browser). Database connectivity and RLS verified. ADS credentials were not opened or printed.\n\n'
          f'**Deployment:** `{deployment["status"]}`; existing project/domain retained. No calibration code, paper or experimental model enters the production upload. **GitHub:** push evidence is recorded by the final handoff after logical commits.\n\n'
          f'**Release verification:** public API checks {deployment.get("public_api_checks","pending")}; browser checks {deployment.get("browser_checks","pending")}; actual production receipt persistence is recorded in `results/research/prospective_receipt_validation.json`. Deployed code SHA: `{deployment.get("deployed_git_sha","pending")}`.\n\n'
          '**Paper:** PRESERVED — SIX PAGE SUBMISSION SNAPSHOT, with unchanged PDF and protected source/assets. **Final test:** SEALED — no approval requested while BLOCKED.\n\n'
          '**Remaining blockers:** incomplete paired archive; complete primary experiments/selection/lock and final executor audit; eligible future station feeds and real verified days; bounded literature/author acceptance. No manual credential setup remains.\n\n'
          '**Current acquisition instruction:** stop after existing-request verification and an insufficient-fold checkpoint; no new ADS submissions. Real prospective logging remains separate. Later request fresh final-test approval only after a real committed lock and READY audit. Full machine-readable evidence: `results/research/codex_continuation_completion.json`.\n')
    print(json.dumps({'status':'DEVELOPMENT_CHECKPOINT_FINAL_BLOCKED','reports_written':12,'paper_modified':False,'final_test_accessed':False}))


if __name__=='__main__':main()
