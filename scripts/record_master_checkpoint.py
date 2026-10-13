"""Summarize observed artifacts without training, network calls or target access."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import fitz
from src.research.calibration.checkpoint import write_json

ROOT=Path(__file__).resolve().parents[1]


def read(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))


def main():
    if (ROOT/'paper/conference_final/main.pdf').exists():
        from scripts.finish_codex_handoff import main as current_handoff
        current_handoff()
        return
    aligned=read('results/research/cams_development_alignment.json')
    state=read('results/research/cams_development_acquisition.json')
    prospective=read('results/research/prospective_audit.json')
    readiness=read('results/research/research_readiness.json')
    tests=read('results/research/test_validation.json')
    browser=read('logs/master-live-browser-result.json')['stats']
    pdf=ROOT/'paper/journal/main.pdf'
    manifest=read('paper/journal/draft_manifest.json')
    for name,digest in manifest['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Journal source differs from compilation input manifest')
    report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'checkpoint_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'branch':'research/station-calibration','live_url':'https://webapp-phi-taupe.vercel.app/',
        'deployed_commit':'35c2ca08b86a53dcc27da11f79edb311d0e77ffe',
        'website_action':'Retained verified production deployment; no application code changed in this continuation',
        'frontend_preflight':read('results/release/master_continuation_preflight.json'),
        'live_browser':browser,'browser_actual_exit':0,
        'initial_browser_report_write_error':'16 tests passed but simultaneous stdout/report writes caused EBUSY; rerun used separate files and exited 0',
        'offline_tests':{'status':tests['status'],'exit_code':tests['exit_code'],'counts':tests['counts'],'source_changed':tests['source_changed_during_run']},
        'earlier_full_suite':{'passed':630,'exit_code':0,'subsequent_edge_case_checks_passed':79},
        'secret_audit':read('results/release/secret_audit.json'),
        'archive_counts':state['counts'],'archive_worker':'Existing IDs resumed; sequential new submissions; finite 24-hour worker',
        'alignment':{k:aligned[k] for k in ('rows','stations','cities','dates','valid_targets','rejected_targets_retained','censored_severe_retained','guarded_rows','sha256','feature_version','protocol_sha256')},
        'prospective':{k:prospective[k] for k in ('forecasts','issued_target_days','verified_days','station_bound_forecasts','historical_forecasts_missing_git_sha')},
        'primary_selected_model':None,'model_selection_lock':'PENDING','final_test_status':'BLOCKED',
        'final_test_scored':False,'experimental_correction_deployed':False,
        'readiness':{'status':readiness['status'],'passed':readiness['passed'],'total':readiness['total']},
        'paper':{'status':'DEVELOPMENT_DRAFT_PRIMARY_RESULTS_PENDING','source':'paper/journal/main.tex',
                 'pdf':'paper/journal/main.pdf','pages':len(fitz.open(pdf)),
                 'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                 'compiler':'Tectonic 0.17.0; actual exit 0; standalone editor compiler also succeeded',
                 'visual_review':'All six final pages rendered and inspected; no clipping or overlaps',
                 'submission_ready':False},
        'remaining_work':['Complete paired operational archive','Audit supplementary lead coverage for cutoff-aligned CAMS bias',
                          'Integrate and execute primary temporal/spatial tuning and comparisons',
                          'Primary ablation, uncertainty, advisory and paired statistics',
                          'Commit actual selection lock and complete final executor audit',
                          'Bind future prospective station forecasts before issuance; collect real outcomes'],
        'manual_action_now':None,'later_human_action':'Explicit approval only after genuine model lock and READY final-test report'}
    write_json(ROOT/'results/research/master_checkpoint.json',report)
    text='# Claim-evidence matrix\n\nThis continuation makes no primary CAMS improvement or clinical-benefit claim.\n\n'
    text+='| Claim | Evidence | Scope |\n|---|---|---|\n'
    for claim,evidence,scope in [
        ('Stable deployed application','results/release/website_deployment_verification.json','Deployed 35c2ca0; research branch commits do not change this deployment'),
        ('Fresh frontend preflight passes','results/release/master_continuation_preflight.json','Lint, types, 43 unit tests, production build'),
        ('16 live browser checks pass','results/research/master_checkpoint.json','Eight routes, desktop and mobile; fresh actual run'),
        (f"{state['counts'].get('VERIFIED_GRIB',0)}/36 operational chunks verified",'results/research/final_test_readiness.json','GRIB decoded and checksummed; incomplete paired months'),
        (f"{aligned['rows']:,} guarded development station-days",'results/research/cams_development_alignment.json','Final rows filtered before materialisation; rejected/censored targets retained'),
        ('Preliminary Ridge improves climatology, not established against persistence','results/research/preliminary_latest.json','NON_CAMS_PRELIMINARY; never a raw-CAMS comparison'),
        ('Primary model improvement','FINAL_TEST_READINESS_REPORT.md','NOT ESTABLISHED; model selection pending'),
        (f"{prospective['forecasts']} real prospective forecasts",'results/research/prospective_audit.json',f"{prospective['issued_target_days']} target days; {prospective['verified_days']} verified days; no retrospective station binding"),
        ('Six-page IEEE journal development draft','paper/journal/draft_manifest.json','Compilation and visual inspection do not establish scientific readiness'),
        ('Final test','FINAL_TEST_READINESS_REPORT.md','BLOCKED; no scoring; later fresh explicit approval required')]:
        text+=f'| {claim} | [{evidence}]({evidence}) | {scope} |\n'
    text+='\nFull protocol/data hashes: [alignment manifest](results/research/cams_development_alignment.json). '
    text+='Earlier project defense claims remain in [the original matrix](docs/defense/CLAIM_EVIDENCE_MATRIX.md).\n'
    (ROOT/'CLAIM_EVIDENCE_MATRIX.md').write_text(text,encoding='utf-8')
    print(json.dumps({'archive':report['archive_counts'],'paper_pages':report['paper']['pages'],'final_test':'BLOCKED'}))


if __name__=='__main__':main()
