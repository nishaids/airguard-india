# Phase 0 audit confirmation

Generated 2026-10-11T13:13:24.875525+00:00 by `python -m scripts.confirm_phase0`.

The supplied request refers to Part B L01–L52, but contains no enumerated Part B. The inline references establish only the provisional meanings below. Unprovided claims are **UNASSESSABLE**, rather than fabricated CONFIRMED/REFUTED findings. The complete 52-item acceptance criterion cannot honestly pass until the original wording is supplied.

This is a source audit of the existing dirty checkout, not a claim that every source change is deployed. Baseline production and UI-preview identities are in `results/research/production_acceptance.json` and `results/ui_integration/deployment.json`. Tests, generated data, deployable source, migrations and operational/research code were inventoried. Ignored credentials, dependency caches and binary datasets were not dumped.

| ID | Assessment | Finding and source evidence |
| --- | --- | --- |
| L01 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L02 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L03 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L04 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L05 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L06 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L07 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L08 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L09 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L10 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L11 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L12 | PARTLY (provisional inline meaning) | Region/season raw CAMS O3 bias is a hypothesis; no operational matched station study establishes its magnitude. `src/research/pipeline.py:70` |
| L13 | PARTLY (provisional inline meaning) | PM2.5 bias atlas is unevaluated. Legacy past-fields analyses cannot establish issued-forecast bias. `src/live/backtest.py:1` |
| L14 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L15 | CONFIRMED (provisional inline meaning) | The live provider does not expose actual model-run initialization. Retrieval timestamps are preserved and explicitly distinguished. `src/nationwide/service.py:154` |
| L16 | PARTLY (provisional inline meaning) | Original city-ordered CV leakage is audited; new whole-date split code exists. Real evaluation under the expanded protocol remains absent. `src/research/legacy_cv_audit.py:9` |
| L17 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L18 | PARTLY (provisional inline meaning) | Within-one-category remains a diagnostic legacy metric. It is not evidence of calibrated probabilities or a headline research contribution. `src/research/evaluation.py:24` |
| L19 | PARTLY (provisional inline meaning) | Legacy classifiers use SMOTE. The operational raw CAMS product does not claim SMOTE outputs are calibrated probabilities. `src/models/train_classification.py:96` |
| L20 | PARTLY (provisional inline meaning) | Legacy exported tree inference exists; no validated station correction model is registered or served. `src/research/serving.py:5` |
| L21 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L22 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L23 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L24 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L25 | CONFIRMED (provisional inline meaning) | Legacy cohort/co-exposure modifiers are heuristic; no evidence-grounded HAI v2 sensitivity result supports the divergence headline. `src/features/hai.py:135` |
| L26 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L27 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L28 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L29 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L30 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L31 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L32 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L33 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L34 | CONFIRMED (provisional inline meaning) | Historical recommendations use instantaneous exposure rather than the live rolling index. Shared semantics are not established in this baseline. `src/features/safe_window.py:186` |
| L35 | CONFIRMED (provisional inline meaning) | Historical two-hour and live three-hour windows differ; practical hours/BLH are not consistently imposed. `src/nationwide/service.py:133` |
| L36 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L37 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L38 | PARTLY (provisional inline meaning) | Schedules and fixed-cutoff capture exist. Zero records before the first actual scheduled cutoff is not proof of failure. Subsequent runs must be verified from immutable records, not cron dispatch alone. `src/nationwide/jobs.py:56` |
| L39 | PARTLY (provisional inline meaning) | Requested coordinates are uniquely keyed, while CAMS inputs are cached by grid. Shared grids can bind different stations; blindly merging immutable location records would lose meaning. `src/nationwide/store.py:87` |
| L40 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L41 | PARTLY (provisional inline meaning) | Credential redaction and secret scanning exist. All publicly exported JSON also needs an absolute-local-path scan. `scripts/audit_secret_history.py:33` |
| L42 | PARTLY (provisional inline meaning) | Live loading/error states exist. Performance and real browser freeze claims need measurements; research retry and lazy content can be improved. `webapp/app/components/ResearchDashboard.tsx:2` |
| L43 | PARTLY (provisional inline meaning) | Source files use UTF-8. No supplied reproducible mojibake example proves which generated route is affected; scan public artifacts before release. `webapp/app/layout.js:10` |
| L44 | CONFIRMED (provisional inline meaning) | MIT code licensing is not an upstream data/commercial API licence. A source-specific licence registry and capacity check are needed. `LICENSE:1` |
| L45 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L46 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L47 | CONFIRMED (provisional inline meaning) | Navigation needs a mobile collapsed view; actual 375/1280 browser checks are not established by HTTP-only tests. `webapp/app/components/NavBar.js:34` |
| L48 | CONFIRMED (provisional inline meaning) | No named native reviewers approve Tamil/Hindi health guidance. Unreviewed translations cannot count as accepted. `webapp/app/lib/i18n.ts:2` |
| L49 | CONFIRMED (provisional inline meaning) | No verified opt-in operational web-push/email/Telegram service or recipient authorization is evidenced. `webapp/app/components/OperationalProvider.tsx:9` |
| L50 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L51 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |
| L52 | UNASSESSABLE | Original numbered limitation text is absent; no claim has been invented. |

## Confirmed architecture and scientific boundaries

- Next.js/Python/Supabase application: `webapp/package.json:15`, `src/nationwide/store.py:26`.
- Public live summary, explicit source and missing correction/interval: `src/nationwide/service.py:116`.
- Historical replay stays bounded to historical data: `webapp/app/historical-replay/page.js:11`. Operational `/forecast` is preserved.
- Fixed 20:00 cutoff, no future observations/reanalysis: `src/research/protocol.py:34`.
- Immutable issue-time forecast and measured outcome projection: `src/research/storage.py:56`, `src/research/storage.py:96`.
- Active v1 uses a shorter training/final-test protocol than the newly requested study. Preserve its immutable definition; register a separately hashed v2 study before looking at a future locked test.
- Actual database counts, duplicate checks, provenance and RLS evidence are regenerated by `python -m scripts.audit_database_release`; see `results/release/database_audit.json`.
- Current and archive forecasts are distinct. ADS remains **PENDING — ADS credential/terms required**, explicitly skipped by the user.
- Reference list editing is reserved for the human authors by the request. No unverified coefficient, DOI, author or clinical effect is promoted into the paper.

## Inventory and follow-through

The hashed text-source inventory is `results/release/source_inventory.json`. This audit records the baseline; later implemented fixes and verification are recorded separately in the release report. An implementation does not turn a research gate green without empirical evidence. `PLAN.md` and `HUMAN_ACTIONS.md` define phases, external prerequisites, and the route interpretation.
