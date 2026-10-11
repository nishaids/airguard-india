"""Write a checkpoint from actual acquisition, evaluation and ledger artifacts."""
import json
import hashlib
import subprocess
from datetime import datetime, timezone, date
from src import config
from src.research.calibration.checkpoint import OUT, write_json
from src.research.calibration.protocol import load
from src.research.calibration.validation import evidence_matches_current


def read(name):
    path=OUT/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def generate():
    protocol=load(); recovery=read('recovery_checkpoint.json'); q=read('measured_dataset.json')
    result=read('preliminary_latest.json'); prospective=read('prospective_audit.json')
    readiness=read('research_readiness.json'); paper=read('paper_skeleton.json')
    tests=read('test_validation.json'); continuation=read('continuation_status.json')
    reproduction=read('dataset_reproducibility.json')
    reproduction_current=(reproduction.get('status')=='PASS' and reproduction.get('dataset_hash')==q.get('dataset_hash'))
    tests_current=evidence_matches_current(tests)
    active_schedules=sum(s.get('active') is True for s in prospective.get('health',{}).get('schedules',[]))
    study_days=(date.fromisoformat(protocol['study_window']['last_date'])-date.fromisoformat(protocol['study_window']['first_date'])).days+1
    full_station_calendar=q.get('station_days')==q.get('raw_stations',0)*study_days
    thirty_day_gate=readiness.get('checks',{}).get('30_day_track_record_complete',False)
    compile_result=read('paper_compile.json')
    if result.get('final_test_scored') is not False:
        raise ValueError('Checkpoint requires explicit locked-final-test isolation')
    if json.loads((config.PROJECT_ROOT/result['artifact']).read_text())!=result:
        raise ValueError('Checkpoint experiment pointer differs from its immutable artifact')
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    temporal=[f for f in result.get('folds',[]) if f.get('strict')]
    spatial=[f for f in result.get('spatial',[]) if f.get('ridge_strict')]
    source_path=config.PROJECT_ROOT/paper.get('source','paper/station_calibration_skeleton.tex')
    compilation_current=(source_path.exists() and compile_result.get('status')=='SUCCESS' and
        compile_result.get('source_sha256')==hashlib.sha256(source_path.read_bytes()).hexdigest())
    value={'generated_at':datetime.now(timezone.utc).isoformat(),'branch':branch,'checkpoint_commit':commit,
        'protocol_sha256':protocol['_sha256'],'download':recovery,
        'measured':{k:q.get(k) for k in ('status','dataset_hash','data_version','code_sha256','feature_version','protocol_version',
            'raw_stations','usable_stations','usable_cities','eligible_stations_full_window_descriptive_only','station_days',
            'valid_targets','rejected_targets','severe_days','date_count','date_coverage','target_rejection_reason_counts',
            'hourly_exclusion_reason_counts','pollutant_target_coverage','strict_snapshot_rows_passed','table')},
        'preliminary':{'run_id':result['run_id'],'dataset_hash':result['dataset_hash'],'artifact':result['artifact'],
            'acquisition_and_experiment_hash_match':q.get('dataset_hash')==result['dataset_hash'],
            'temporal_evaluations_completed':len(temporal),'spatial_evaluations_completed':len(spatial),
            'spatial_insufficient_entries':len(result.get('spatial',[]))-len(spatial),
            'uncertainty_folds':len(result.get('uncertainty',{})),'advisory_folds':len(result.get('advisory',{})),
            'final_test_scored':False,'paired_comparisons':result.get('paired_comparisons',{})},
        'prospective':{k:prospective.get(k) for k in ('forecasts','issued_target_days','verified_days','elapsed_real_days',
            'station_bound_forecasts','historical_forecasts_missing_git_sha','input_availability_violations','outcomes_due',
            'verification_pairing_mismatches','immutability_triggers')},
        'readiness':readiness,'paper':{**paper,'compilation_current':compilation_current},
        'test_status':tests.get('status'),'test_counts':tests.get('counts'),'test_evidence_current':tests_current,
        'local_reproduction_current':reproduction_current,
        'continuation':{k:continuation.get(k) for k in ('state','collection_finished','measured_completed','experiment_completed','worker_pids')},
        'CAMS_ARCHIVE_STATUS':'PENDING_MANUAL_ADS_CREDENTIAL','production_deployed':False}
    write_json(OUT/'continuation_checkpoint.json',value)
    completed=', '.join(k for k,v in readiness.get('checks',{}).items() if v)
    pending=', '.join(k for k,v in readiness.get('checks',{}).items() if not v)
    lines=[
        '# AirGuard India research continuation checkpoint','',f"Generated {value['generated_at']}; values describe identified snapshots, not future completed downloads.",'',
        f"1. **Branch and checkpoint commit:** `{branch}` at `{commit}`. No branch switch, reset, production merge, push or deployment.",
        '2. **Inherited from Claude:** checkpoint 5790c3a, locked v3.1 protocol/history, metadata station catalogue/selection, sensor QC, availability guards, target/metric/split infrastructure and running OpenAQ/weather/FIRMS acquisition. Preserved.',
        '3. **Completed by Codex:** checksum recovery, bounded pagination checks, complete-row measured QC/rejection ledgers, causal feature QC, separate frozen non-CAMS plan, audited temporal/spatial/ablation/calibration/statistical/advisory implementation, local reproduction, prospective audit, source-only operational fixes, literature matrix and generated IEEE skeleton.',
        f"4. **Downloads:** OpenAQ {recovery.get('openaq_complete')}/{recovery.get('openaq_selected')} selected stations ({recovery.get('openaq_rows'):,} raw rows); weather {recovery.get('weather_points_complete')}/{recovery.get('weather_points_expected')}; FIRMS {recovery.get('firms_windows_complete')}/{recovery.get('firms_windows_expected')}. Checksum audit {recovery.get('checksum_audit')}, {recovery.get('checksummed_files')} recorded files. Proxy CAMS preserved and unused. Finite helper state: `{continuation.get('state','NOT_STARTED')}`.",
        f"5. **Usable measured snapshot:** {q.get('usable_stations')} stations/{q.get('usable_cities')} cities; {q.get('eligible_stations_full_window_descriptive_only')} stations meet the descriptive full-window 120-day count. {q.get('date_count')} dates with valid targets across {q.get('date_coverage')}; {study_days} study days; complete station calendars={full_station_calendar}. {q.get('station_days'):,} station-days, {q.get('valid_targets'):,} valid targets. Dataset `{q.get('dataset_hash')}`; feature `{q.get('feature_version')}`. The experiment uses dataset `{result['dataset_hash']}`; identities match={value['preliminary']['acquisition_and_experiment_hash_match']}.",
        f"6. **Quality exclusions:** {q.get('rejected_targets'):,} retained rejected targets; {q.get('severe_days')} censored Severe days. Hourly exclusion counts: `{json.dumps(q.get('hourly_exclusion_reason_counts',{}),sort_keys=True)}`. PM2.5>PM10/spikes flagged and retained. Raw exclusions remain addressable; reasons may overlap across pollutants.",
        f"7. **Leakage audit:** {q.get('strict_snapshot_rows_passed'):,} rows passed the strict builder guard; runner independently checks values/provenance. Final 2026-07-10..2026-10-07 remains unscored. Strict inputs: 48-hour-offset weather, calendar, coordinates. Measured history/persistence are latency-conditional; fires withheld. Protocol hash `{protocol['_sha256']}` unchanged.",
        '8. **Baselines:** non-CAMS training-only climatology and fixed Ridge variants; conditional persistence/history Ridge on paired available rows. Legacy city model is not comparable to this station dataset. Required raw operational CAMS baseline remains incomplete.',
        f"9. **Experiments:** {len(temporal)} expanding/sliding temporal evaluations; {len(spatial)} metadata-assigned city/cluster/station/region holdouts ({len(result.get('spatial',[]))-len(spatial)} insufficient entries); category/extreme/season/region diagnostics; weather/history ablation; paired date-block/Holm analysis; {len(result.get('uncertainty',{}))} uncertainty and advisory calibration folds. These are preliminary empirical results. Local raw-cache reconstruction current/pass={reproduction_current}; clean-clone primary reproduction pending. Tests: status={tests.get('status')}, current={tests_current}, counts={tests.get('counts')}.",
        '10. **CAMS-blocked experiments:** raw CAMS versus Direct ML/Residual Ridge/Residual LightGBM/Residual XGBoost, CAMS ablation, primary uncertainty/advisory comparisons and definitive final-test evaluation. Operational-file/unit/run/availability evidence and pre-issue support policy must be validated before primary fitting.',
        f"11. **Prospective forecasts:** {prospective.get('forecasts')} immutable forecasts/{prospective.get('issued_target_days')} target days; {prospective.get('station_bound_forecasts')} bound stations. {active_schedules} production schedules audited active; source fixes are undeployed. {prospective.get('historical_forecasts_missing_git_sha')} old issuance SHAs absent and not reconstructed.",
        f"12. **Prospective verification:** {prospective.get('verified_days')} verified days; {prospective.get('outcomes_due')} outcomes due at audit; {prospective.get('input_availability_violations')} availability violations; {prospective.get('verification_pairing_mismatches')} pairing mismatches. Thirty-day gate={thirty_day_gate}; unbound records cannot be paired retrospectively.",
        f"13. **Readiness:** `{readiness.get('status')}`, {readiness.get('passed')}/{readiness.get('total')} primary gates. Passing: {completed}. Pending: {pending}. Preliminary results never satisfy primary CAMS gates.",
        f"14. **IEEE draft:** `{paper.get('source')}`, six intended pages; current-source compiler success={compilation_current}, page-count verified={paper.get('page_count_verified',False)}. Generated from exact result artifacts; acquisition/experiment identities explicit. CAMS result placeholders and author/venue acceptance remain. No submission readiness claim.",
        '15. **Manual action:** sign into Copernicus ADS, accept CAMS global forecast dataset terms, and configure its personal token privately in user-home `.cdsapirc` with ADS API URL. See [ADS_MANUAL_SETUP.md](ADS_MANUAL_SETUP.md). Do not paste the token into chat. Genuine forecast import and unit/availability checks follow before any primary fitting. A later production release needs separate user approval.',
        '', 'Evidence: `results/research/continuation_checkpoint.json`, `measured_dataset.json`, `preliminary_latest.json`, `prospective_audit.json`, `test_validation.json`, `literature_fulltext_review.json` and `paper_skeleton.json`.',
        '', 'Downloads can continue after this snapshot; the finite helper regenerates artifacts after the observed workers finish. Status and completion flags are derived from stage outcomes. It does not mutate Git or deploy models.']
    text='\n\n'.join(lines)
    (config.PROJECT_ROOT/'docs/research/CONTINUATION_CHECKPOINT.md').write_text(text+'\n',encoding='utf-8')
    return value


if __name__=='__main__':
    value=generate()
    print(json.dumps({'branch':value['branch'],'checkpoint_commit':value['checkpoint_commit'],
        'dataset_hash':value['measured']['dataset_hash'],'primary_status':value['readiness'].get('status')}))
