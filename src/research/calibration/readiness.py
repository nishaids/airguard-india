"""Compute primary readiness from evidence; preliminary results cannot pass it."""
import json
import hashlib
from datetime import datetime, timezone
from src import config
from src.qa.security import gate
from src.research.calibration.checkpoint import OUT, write_json, CAMS_ARCHIVE_STATUS
from src.research.calibration.protocol import load
from src.research.calibration.validation import evidence_matches_current


def artifact(name):
    path=OUT/name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def current_archive_status():
    """Collection status from the verified smoke file; no primary gate release."""
    probe=artifact('cams_ads_probe.json')
    if probe.get('status')!='VERIFIED_OPERATIONAL_FORECAST':
        return CAMS_ARCHIVE_STATUS
    try:
        path=(config.PROJECT_ROOT/probe['file']).resolve()
        if not path.is_relative_to((config.PROJECT_ROOT/'data/research').resolve()):
            return 'ADS_PROBE_EVIDENCE_INVALID'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=probe['sha256']:
            return 'ADS_PROBE_EVIDENCE_INVALID'
        from src.research.calibration.ads_probe import verify_fields
        verify_fields(probe['decoded_fields'])
    except (KeyError,ValueError,OSError,TypeError):
        return 'ADS_PROBE_EVIDENCE_INVALID'
    acquisition=artifact('cams_development_acquisition.json')
    if acquisition.get('complete') is True:
        return 'ADS_ARCHIVE_COLLECTED_PRIMARY_AUDIT_PENDING'
    if acquisition.get('submission_control',{}).get('new_requests_authorized') is False:
        return 'ADS_OPERATIONAL_ARCHIVE_PAUSED_AUTHOR_REQUEST'
    if acquisition.get('jobs'):
        return 'ADS_OPERATIONAL_ARCHIVE_ACQUIRING'
    return 'ADS_SMOKE_VERIFIED_ARCHIVE_INCOMPLETE'


def generate():
    protocol=load()
    cams_status=current_archive_status()
    measured=artifact('measured_dataset.json')
    preliminary=artifact('preliminary_latest.json')
    prospective=artifact('prospective_audit.json')
    primary=artifact('primary_results.json')
    tests=artifact('test_validation.json')
    tests_current=evidence_matches_current(tests)
    security=gate()
    primary_valid=(primary.get('experiment')=='GENUINE_CAMS_PRIMARY'
                   and primary.get('protocol_sha256')==protocol['_sha256']
                   and primary.get('archive_source')=='COPERNICUS_ADS_OPERATIONAL_FORECAST'
                   and primary.get('availability_audit')=='PASS')
    checks={
        'literature_review_complete':artifact('literature_review_acceptance.json').get('accepted') is True,
        'research_question_locked':bool(protocol.get('research_questions')),
        'protocol_locked':bool(protocol.get('_locked_at')),
        'issue_time_dataset_validated':primary_valid and primary.get('dataset_audit')=='PASS',
        'cpcb_method_verified':tests_current and tests.get('cpcb_method_passed') is True,
        'baseline_complete':primary_valid and all(name in primary.get('methods',[]) for name in
                              ('raw_cams','direct_ml','residual_ridge','residual_lightgbm','residual_xgboost')),
        'rolling_origin_complete':primary_valid and bool(primary.get('rolling_folds')),
        'spatial_validation_complete':primary_valid and bool(primary.get('spatial')),
        'ablation_complete':primary_valid and bool(primary.get('ablation')),
        'uncertainty_complete':primary_valid and bool(primary.get('uncertainty')),
        'extreme_event_analysis_complete':primary_valid and bool(primary.get('severity')),
        'advisory_evaluation_complete':primary_valid and bool(primary.get('advisory')),
        'statistical_comparison_complete':primary_valid and bool(primary.get('paired_comparisons')),
        'reproducibility_passed':artifact('clean_clone_reproduction.json').get('accepted') is True,
        'prospective_logging_active':bool(prospective.get('forecasts')) and
            prospective.get('health',{}).get('issuance',{}).get('state') in ('ISSUED','ISSUANCE_WINDOW_OPEN'),
        '30_day_track_record_complete':prospective.get('verified_days',0)>=30 and prospective.get('elapsed_real_days',0)>=30,
        'security_passed':security['passed']}
    value={'generated_at':datetime.now(timezone.utc).isoformat(),
           'status':'RESEARCH_READY' if all(checks.values()) else 'COLLECTING_NOT_RESEARCH_READY',
           'checks':checks,'passed':sum(checks.values()),'total':len(checks),
           'CAMS_ARCHIVE_STATUS':cams_status,
           'evidence':{'protocol_version':protocol['protocol_version'],'protocol_hash':protocol['_sha256'],
                       'dataset_hash':measured.get('dataset_hash'),'preliminary_run_id':preliminary.get('run_id'),
                       'fixed_time_issuance':{k:prospective.get(k) for k in ('forecasts','issued_target_days','verified_days','elapsed_real_days','station_bound_forecasts')},
                       'issuance_state':prospective.get('health',{}).get('issuance',{}).get('state'),
                       'test_validation_current':tests_current,'test_counts':tests.get('counts'),
                       'security_gate':security},
           'preliminary':{'experiment':'NON_CAMS_PRELIMINARY','baseline_complete':any(
                          all(name in f.get('strict',{}) for name in ('climatology','ridge_strict','ridge_calendar_spatial'))
                          for f in preliminary.get('folds',[])),
                          'final_test_scored':preliminary.get('final_test_scored',False),
                          'does_not_satisfy_primary_gates':True},
           'prospective_evaluable':prospective.get('station_bound_forecasts',0)>0,
           'claims_supported':['Measured CPCB-style target construction with v3.1 QC',
                               'Non-CAMS preliminary validation with a sealed final test',
                               'Real immutable prospective forecast logging'],
           'claims_not_supported':['AirGuard improves CAMS','Calibrated operational station corrections',
                                   'Controlled vulnerable-cohort under-warning','Station correction generalises nationwide'],
           'pending_archive':cams_status}
    write_json(OUT/'research_readiness.json',value)
    write_json(OUT/'security_gate.json',security)
    # Local source/status mirrors only; no vendoring, build or deployment.
    write_json(config.PROJECT_ROOT/'src/research/readiness.json',value)
    write_json(config.PROJECT_ROOT/'webapp/public/data/research_readiness.json',value)
    return value


if __name__=='__main__':
    value=generate()
    print(json.dumps({'status':value['status'],'passed':value['passed'],'total':value['total']}))
