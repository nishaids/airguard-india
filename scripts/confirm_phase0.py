"""Rebuild the Phase 0 audit from source anchors; absent audit claims stay absent."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# These are the ONLY identifiers whose meaning is given inline in the supplied request.
CLAIMS = {
12: ('PARTLY', 'Region/season raw CAMS O3 bias is a hypothesis; no operational matched station study establishes its magnitude.', 'src/research/pipeline.py', 'def dataset'),
13: ('PARTLY', 'PM2.5 bias atlas is unevaluated. Legacy past-fields analyses cannot establish issued-forecast bias.', 'src/live/backtest.py', 'LEGACY EXPLORATORY'),
15: ('CONFIRMED', 'The live provider does not expose actual model-run initialization. Retrieval timestamps are preserved and explicitly distinguished.', 'src/nationwide/service.py', 'issue_time_basis'),
16: ('PARTLY', 'Original city-ordered CV leakage is audited; new whole-date split code exists. Real evaluation under the expanded protocol remains absent.', 'src/research/legacy_cv_audit.py', 'def audit'),
18: ('PARTLY', 'Within-one-category remains a diagnostic legacy metric. It is not evidence of calibrated probabilities or a headline research contribution.', 'src/research/evaluation.py', 'within_one_category'),
19: ('PARTLY', 'Legacy classifiers use SMOTE. The operational raw CAMS product does not claim SMOTE outputs are calibrated probabilities.', 'src/models/train_classification.py', 'from imblearn.over_sampling import SMOTE'),
20: ('PARTLY', 'Legacy exported tree inference exists; no validated station correction model is registered or served.', 'src/research/serving.py', 'def'),
25: ('CONFIRMED', 'Legacy cohort/co-exposure modifiers are heuristic; no evidence-grounded HAI v2 sensitivity result supports the divergence headline.', 'src/features/hai.py', 'LAMBDA_COEXPOSURE: float = 0.25'),
34: ('CONFIRMED', 'Historical recommendations use instantaneous exposure rather than the live rolling index. Shared semantics are not established in this baseline.', 'src/features/safe_window.py', 'def best_window'),
35: ('CONFIRMED', 'Historical two-hour and live three-hour windows differ; practical hours/BLH are not consistently imposed.', 'src/nationwide/service.py', 'windows ='),
38: ('PARTLY', 'Schedules and fixed-cutoff capture exist. Zero records before the first actual scheduled cutoff is not proof of failure. Subsequent runs must be verified from immutable records, not cron dispatch alone.', 'src/nationwide/jobs.py', 'local.hour==20'),
39: ('PARTLY', 'Requested coordinates are uniquely keyed, while CAMS inputs are cached by grid. Shared grids can bind different stations; blindly merging immutable location records would lose meaning.', 'src/nationwide/store.py', 'on conflict(location_key)'),
41: ('PARTLY', 'Credential redaction and secret scanning exist. All publicly exported JSON also needs an absolute-local-path scan.', 'scripts/audit_secret_history.py', 'current_hits'),
42: ('PARTLY', 'Live loading/error states exist. Performance and real browser freeze claims need measurements; research retry and lazy content can be improved.', 'webapp/app/components/ResearchDashboard.tsx', 'useEffect'),
43: ('PARTLY', 'Source files use UTF-8. No supplied reproducible mojibake example proves which generated route is affected; scan public artifacts before release.', 'webapp/app/layout.js', 'export const metadata'),
44: ('CONFIRMED', 'MIT code licensing is not an upstream data/commercial API licence. A source-specific licence registry and capacity check are needed.', 'LICENSE', 'MIT'),
47: ('CONFIRMED', 'Navigation needs a mobile collapsed view; actual 375/1280 browser checks are not established by HTTP-only tests.', 'webapp/app/components/NavBar.js', 'LINKS.map'),
48: ('CONFIRMED', 'No named native reviewers approve Tamil/Hindi health guidance. Unreviewed translations cannot count as accepted.', 'webapp/app/lib/i18n.ts', 'export'),
49: ('CONFIRMED', 'No verified opt-in operational web-push/email/Telegram service or recipient authorization is evidenced.', 'webapp/app/components/OperationalProvider.tsx', 'COHORT_STORAGE'),
}


def citation(path, anchor):
    p = ROOT / path
    lines = p.read_text(encoding='utf-8').splitlines()
    line = next((i for i, text in enumerate(lines, 1) if anchor in text), 1)
    return f'`{path}:{line}`'


def main():
    now = datetime.now(timezone.utc).isoformat()
    lines = ['# Phase 0 audit confirmation', '', f'Generated {now} by `python -m scripts.confirm_phase0`.', '',
        'The supplied request refers to Part B L01–L52, but contains no enumerated Part B. The inline references establish only the provisional meanings below. Unprovided claims are **UNASSESSABLE**, rather than fabricated CONFIRMED/REFUTED findings. The complete 52-item acceptance criterion cannot honestly pass until the original wording is supplied.', '',
        'This is a source audit of the existing dirty checkout, not a claim that every source change is deployed. Baseline production and UI-preview identities are in `results/research/production_acceptance.json` and `results/ui_integration/deployment.json`. Tests, generated data, deployable source, migrations and operational/research code were inventoried. Ignored credentials, dependency caches and binary datasets were not dumped.', '',
        '| ID | Assessment | Finding and source evidence |', '| --- | --- | --- |']
    for number in range(1, 53):
        if number in CLAIMS:
            state, claim, path, anchor = CLAIMS[number]
            lines.append(f'| L{number:02} | {state} (provisional inline meaning) | {claim} {citation(path, anchor)} |')
        else:
            lines.append(f'| L{number:02} | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |')
    lines += ['', '## Confirmed architecture and scientific boundaries', '',
        f'- Next.js/Python/Supabase application: {citation("webapp/package.json", "dependencies")}, {citation("src/nationwide/store.py", "class Store")}.',
        f'- Public live summary, explicit source and missing correction/interval: {citation("src/nationwide/service.py", "NOT_VALIDATED")}.',
        f'- Historical replay stays bounded to historical data: {citation("webapp/app/historical-replay/page.js", "export default")}. Operational `/forecast` is preserved.',
        f'- Fixed 20:00 cutoff, no future observations/reanalysis: {citation("src/research/protocol.py", "def check_inputs")}.',
        f'- Immutable issue-time forecast and measured outcome projection: {citation("src/research/storage.py", "def capture")}, {citation("src/research/storage.py", "def verify")}.',
        '- Active v1 uses a shorter training/final-test protocol than the newly requested study. Preserve its immutable definition; register a separately hashed v2 study before looking at a future locked test.',
        '- Actual database counts, duplicate checks, provenance and RLS evidence are regenerated by `python -m scripts.audit_database_release`; see `results/release/database_audit.json`.',
        '- Current and archive forecasts are distinct. ADS remains **PENDING — ADS credential/terms required**, explicitly skipped by the user.',
        '- Reference list editing is reserved for the human authors by the request. No unverified coefficient, DOI, author or clinical effect is promoted into the paper.', '',
        '## Inventory and follow-through', '',
        'The hashed text-source inventory is `results/release/source_inventory.json`. This audit records the baseline; later implemented fixes and verification are recorded separately in the release report. An implementation does not turn a research gate green without empirical evidence. `PLAN.md` and `HUMAN_ACTIONS.md` define phases, external prerequisites, and the route interpretation.']
    (ROOT/'docs/AUDIT_CONFIRMATION.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    items = []
    for folder in ('src','tests','scripts','db','docs','webapp/app','webapp/tests'):
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_file() and p.suffix in ('.py','.js','.tsx','.ts','.json','.sql','.md','.css') and '__pycache__' not in p.parts:
                items.append({'path':p.relative_to(ROOT).as_posix(), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    out = ROOT/'results/release/source_inventory.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'generated_at':now,'sources':items,'limitations_supplied':len(CLAIMS),'unprovided_limitations':52-len(CLAIMS)},indent=2),encoding='utf-8')
    print(json.dumps({'audit_identifiers':52,'provisional_claims':len(CLAIMS),'unprovided_claims':52-len(CLAIMS),'text_sources_inventoried':len(items)}))


if __name__ == '__main__': main()
