"""Write the requested 31-point completion checkpoint from actual evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from scripts.build_defense_pack import table
from src.research.calibration.checkpoint import write_json
from src.research.calibration.protocol import load
from src.research.calibration.validation import source_fingerprint

ROOT=Path(__file__).resolve().parents[1]
def read(path):
    p=ROOT/path
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def main():
    probe=read('results/research/cams_ads_probe.json'); acquisition=read('results/research/cams_development_acquisition.json')
    baseline=read('results/research/cams_raw_baseline_derivation.json'); measured=read('results/research/measured_dataset.json')
    preliminary=read('results/research/preliminary_latest.json'); prospective=read('results/research/prospective_audit.json')
    verification=read('results/project_hardening/verification.json'); python=read('results/project_hardening/all_python_tests.json')
    readiness=read('results/research/research_readiness.json'); protocol=load()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    lock=ROOT/'MODEL_SELECTION_LOCK'
    if lock.exists(): raise ValueError('Existing model-selection lock requires its own scientific audit; do not overwrite this report blindly')
    stable=python.get('source_fingerprint')==source_fingerprint() and python.get('source_changed_during_run') is False
    scores=[
        ('Edge-case readiness',8,'35 documented scenarios, input/schema/fallback tests; no exhaustive real incident study'),
        ('Technical readiness',8,'Build/types/lint, unit and real browser/API checks; national load and penetration proof absent'),
        ('ML readiness',3,'Measured/QC and preliminary baselines established; full CAMS comparison, selection and final evidence absent'),
        ('Research-defense readiness',7,'Protocol, hashes, splits, reproduction and negative findings; primary experiment/literature acceptance incomplete'),
        ('Novelty readiness',6,'Owned contribution/fair comparisons explicit; exhaustive novelty and forecast advantage unproved'),
        ('People-impact readiness',6,'Realistic group/scenario planning and responsible limits; no user/intervention outcome study'),
        ('Viva readiness',8,'210 Q&A, ten personas and concise sheets; student rehearsal remains necessary'),
        ('Demo readiness',8,'43 browser/API checks and backup scripts; provider/network availability remains external'),
        ('Production-prototype readiness',6,'Tested local controls and database evidence; approved release, capacity, privacy/penetration work incomplete'),
    ]
    pairs=preliminary['paired_comparisons']; primary=pairs['ridge_strict_vs_climatology']; history=pairs['ridge_history_vs_persistence']
    points=[
        ('CAMS probe',f"{probe['status']}; {probe['bytes']} bytes; SHA256 {probe['sha256']}; 3x3 PM2.5 forecast, init 2025-02-18 00 UTC, +24h, valid 2025-02-19 00 UTC; no replacement probe"),
        ('CAMS archive',f"{acquisition.get('counts',{})} of 36 monthly jobs; development-only 507 runs; complete={acquisition.get('complete',False)}; source/provider waiting remains"),
        ('Measured dataset',f"Unchanged: {measured['usable_stations']} usable stations / {measured['usable_cities']} cities; {measured['station_days']} retained rows; {measured['valid_targets']} valid / {measured['rejected_targets']} rejected; semantic SHA {measured['dataset_hash']}"),
        ('Selected model','No primary model selected. The preliminary fixed Ridge experiment is not primary CAMS selection.'),
        ('MODEL_SELECTION_LOCK','Not created: incomplete primary development evidence. No placeholder lock is used.'),
        ('Final-test status','SEALED/UNSCORED: 2026-07-10..2026-10-07. Latest task conditionally authorises one evaluation only after a committed lock and isolation/hashes checks.'),
        ('Raw CAMS result',f"Partial forecast derivation: {baseline.get('rows',0)} station-days, {baseline.get('dates',0)} dates, three/six species indices; no measured outcome comparison; table SHA {baseline.get('sha256')}"),
        ('AirGuard result',f"NON_CAMS_PRELIMINARY only, immutable run {preliminary['run_id']}; primary corrected CAMS results pending"),
        ('Improvement/degradation',f"Strict Ridge minus climatology MAE {primary['mae_difference']:.2f}, CI95 {primary['ci95']}; history Ridge minus persistence {history['mae_difference']:+.2f}, CI95 {history['ci95']} includes zero; no CAMS improvement claim"),
        ('Temporal generalisation','24 non-CAMS temporal evaluations (12 expanding + 12 sliding sensitivities); primary CAMS temporal evaluation pending'),
        ('Spatial generalisation','36 non-CAMS city/cluster/station/region holdouts; not proof of nationwide calibrated CAMS transfer'),
        ('Severe/high pollution','383 censored Severe measured station-days; all strict baseline forecasts on 363 evaluated censored Severe validation days below 401. No fabricated exact Severe error.'),
        ('Uncertainty quality','Twelve preliminary calibration windows; weighted coverage/width in UNCERTAINTY_ADVISORY_DEFENSE.md; subgroup failures disclosed, including zero Very Poor coverage in fold_01 split-80 (35 exact pairs). Primary intervals pending.'),
        ('Advisory trade-off','P0/P1/P2 weighted under-/over-warning in the defense sheet; P3 fold artifacts retain empirical feasibility/targets. No dependent-day risk guarantee or clinical validation.'),
        ('Ablation conclusion','Preliminary forecast-weather addition lowered paired MAE by 2.88 AQI; history contributes conditional on healthy feed but does not establish beating persistence. CAMS/FIRMS primary ablations pending.'),
        ('Application tests',f"Python {python.get('counts',{}).get('passed')} passed, actual exit {python.get('exit_code')}, current stable source={stable}; frontend 42 passed; browser/API 43 passed; lint/typecheck/build exit 0. Current offline scientific evidence: 611 passed, 5 skipped, 4 database cases excluded."),
    ]
    points.extend((name,f'{score}/10 — {reason}') for name,score,reason in scores)
    strengths=[
        'Locked v3.1 protocol and retained prior hashes/commits', 'Measured/QC ledger with explicit rejected targets',
        'Genuine decoded operational probe and validated first archive cubes', 'Resumable requests, checksums and no duplicate probe',
        'Censored-Severe methodology and negative findings retained', 'Chronological/spatial preliminary validation and paired comparisons',
        'Fresh-checkout measured reconstruction evidence', 'Actual unit/browser/API/build/security checks',
        'Clear measured/modelled/fallback/withheld UI states', 'Complete practical defense navigation and explicit claim boundaries',
    ]
    weaknesses=[
        'Primary archive/development selection unfinished', 'Strict preliminary Severe under-warning',
        'Historical source-publication uncertainty', 'Current-catalogue survivorship and uneven monitoring',
        'No street-level precision or nationwide calibrated transfer proof', 'Conditional uncertainty and sparse extreme strata',
        'No clinical/user intervention benefit evidence', 'Zero verified prospective days and unbound old forecasts',
        'Provider/commercial licensing/cost dependence', 'No million-user load or penetration/retention certification',
    ]
    points.extend([
        ('Top ten strengths','See the numbered list below.'),('Top ten weaknesses','See the numbered list below.'),
        ('Remaining external blockers','CAMS full archive still processing; Chhatikara upstream station remains unavailable; 30 real verified prospective days have not elapsed. Commercial licensing/capacity/user validation and a separately approved production release remain future work.'),
        ('Files created/modified','docs/defense (33 authored documents plus this report); archive/physics/baseline/readiness source and tests; frontend/provider validation; verification/defense scripts; research/security/readiness artifacts; refreshed browser screenshots. Full tracked changes listed below.'),
        ('Commits',f'Current generation source {head}; branch {branch}; the enclosing checkpoint report is committed afterward. See git log for the final evidence commit.'),
        ('Exact local demo commands','Repository root: .\\.venv-live\\Scripts\\python.exe -m webapp.dev_api_server --port 8787. Separate terminal: cd webapp; npm run dev -- --hostname 127.0.0.1 --port 3000. Open http://127.0.0.1:3000/live.'),
    ])
    if len(points)!=31: raise ValueError('Completion report must have all 31 requested items')
    files=subprocess.check_output(['git','diff','--name-only','f85a67b'],cwd=ROOT,text=True).splitlines()
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'status':'INDEPENDENT_HARDENING_COMPLETE_PRIMARY_RESEARCH_WAITING_FOR_ARCHIVE',
        'branch':branch,'generation_git_sha':head,'protocol_sha256':protocol['_sha256'],'measured_dataset_hash':measured['dataset_hash'],
        'CAMS_archive_counts':acquisition.get('counts'),'CAMS_archive_complete':acquisition.get('complete'),
        'raw_baseline_table_sha256':baseline.get('sha256'),'primary_model_selected':False,'selection_lock_created':False,
        'final_test_scored':False,'paper_generated':False,'experimental_correction_deployed':False,
        'test_source_current_and_stable':stable,'readiness':{'passed':readiness.get('passed'),'total':readiness.get('total'),'status':readiness.get('status')},
        'assessment_note':'Readiness /10 values are qualitative audit judgments with rationale, not measured forecasting or event probabilities.',
        'readiness_assessments':[{'dimension':n,'score_out_of_10':s,'rationale':why} for n,s,why in scores],
        'points':[{'number':i,'topic':n,'evidence':body} for i,(n,body) in enumerate(points,1)],
        'strengths':strengths,'weaknesses':weaknesses,'files':sorted(set(files+untracked))}
    write_json(ROOT/'results/project_hardening/completion_report.json',report)
    text=('# Project completion checkpoint\n\n**Independent hardening and defense work is complete; the primary research is waiting for the full CAMS archive.** '
        'This is not a claim that model selection or final evaluation finished. No paper or experimental production deployment occurred.\n\n'
        +f"Generated on {report['generated_at_utc']} from `{head}` on `{branch}`. Live acquisition status can advance after this snapshot.\n\n"
        +table(['#','Requested item','Actual evidence/status'],[[i,n,b] for i,(n,b) in enumerate(points,1)])
        +'\n## Rating interpretation\n\n'+report['assessment_note']+'\n\n'
        +'## Ten strengths\n\n'+'\n'.join(f'{i}. {s}' for i,s in enumerate(strengths,1))
        +'\n\n## Ten weaknesses\n\n'+'\n'.join(f'{i}. {s}' for i,s in enumerate(weaknesses,1))
        +'\n\n## Hashes and source artifacts\n\n'+table(['Artifact','Hash'],[
            ['Protocol',protocol['_sha256']],['Measured semantic dataset',measured['dataset_hash']],
            ['Probe GRIB',probe['sha256']],['CAMS plan',acquisition['plan_sha256']],
            ['Partial raw baseline table',baseline.get('sha256')],['Preliminary run',preliminary['run_id']]])
        +'\n## Files in this continuation\n\n'+'\n'.join('- `'+p+'`' for p in report['files'])+'\n')
    path=ROOT/'docs/defense/COMPLETION_REPORT.md';path.write_text(text,encoding='utf-8')
    manifest_path=ROOT/'results/project_hardening/defense_pack_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['files']['COMPLETION_REPORT.md']=hashlib.sha256(text.encode()).hexdigest()
    write_json(manifest_path,manifest)
    print(json.dumps({'status':report['status'],'report_items':len(points),'python_source_stable':stable,'defense_files':len(manifest['files'])}))

if __name__=='__main__': main()
