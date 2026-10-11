# AirGuard India — progress ledger

## Research continuation — 2026-10-12 (IST)

Recovered `research/station-calibration` at `5790c3a`, including Claude's
uncommitted metrics/splits and live OpenAQ/weather download processes. No reset,
branch switch, protocol rewrite, production merge, push or deployment occurred.
The historical entries below remain a record of their earlier checkpoints.

- v3.1 lock verified: `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`.
- FIRMS completed all 123 windows. OpenAQ and weather remain live; see
  `results/research/recovery_checkpoint.json` for the exact audited snapshot.
- Cache/file and decompressed-content checksums verified without API calls.
- Added incremental measured targets and rejection ledgers. Every selected
  completed station retains all 596 study days, including insufficient targets.
  Existing exact-zero and six-hour stuck rules are preserved. Missing coverage
  and timezone information are refused as implementation of the existing rules.
- Feature stuck-run detection uses only the prefix available before its cutoff.
  Full-window QC is used for later measured outcomes only.
- Non-CAMS plan frozen before fitting in `results/research/non_cams_plan.json`.
  No CAMS proxy, reanalysis, target support or target quality flag is a predictor.
  Historical measured-history features remain a labelled latency sensitivity.
- 421 Python tests passed, including 30 new checkpoint/leakage/QC tests.
- Production audit found 12 immutable forecasts, zero verified days, no bound
  station and no recorded Git SHA. Future metadata recording is fixed in source;
  production was not deployed. Station-free records cannot be retroactively paired.

Next: execute preliminary rolling/spatial/calibration diagnostics, add research
readiness evidence and paper assets, then continue acquisitions idempotently.
The full primary comparison remains `PENDING_MANUAL_ADS_CREDENTIAL`.

Updated 2026-10-11. Branch `codex/airguard-research-production`. Every entry
names the artefact or file that proves it; regenerate the audit with
`python -m scripts.confirm_phase0`, which fails if any cited anchor no longer
says what the row claims.

## Build and test state

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `./.venv-live/Scripts/python.exe -m pytest -q` | 391 passed |
| Web unit tests | `webapp$ npm test` | 30 passed, 6 files |
| Types | `webapp$ npm run typecheck` | clean |
| Lint | `webapp$ npm run lint` | clean |
| Production build | `webapp$ npm run build` | 17 routes, no errors |
| Generated-path guard | `make checks` | clean under results, data, webapp/public, docs, reports, paper |
| Paper format rules | `make rules` | one failure: unresolved author placeholders (human action) |
| Article originality | `make article` | 1,619 words, 0 shared eight-word runs with the paper |

## Limitations L01–L52

11 FIXED · 26 PARTIAL · 3 OPEN · 12 BLOCKED · 0 REFUTED
(`docs/AUDIT_CONFIRMATION.md`, `results/audit_confirmation.json`)

Codex could assess only 16 of the 52 identifiers because the Part B table was
never supplied; it is now in `docs/MASTER_SPEC.md` and every row carries a
verdict quoted against the claim the spec actually makes.

The three still OPEN with nothing external in the way: L02 (data.gov.in path
remains unavailable upstream), L25 (the sensitivity harness exists but needs
published confidence intervals), L37 (3 of 17 readiness gates, now 5).

## Work packages

| WP | Status | Evidence |
| --- | --- | --- |
| WP0 — audit and scaffolding | **DONE** | All 52 limitations assessed from the real Part B table, anchors resolved at generation time, `tests/test_phase0_audit.py` holds it. `PLAN.md` and `HUMAN_ACTIONS.md` corrected where they described a missing attachment. |
| WP1 — data layer | **PARTIAL** | Station history is reachable after all: `src/ingestion/archive.py` walks OpenAQ's hourly archive, and 72,339 rows across 6 stations yield **861 station-days with a valid CPCB-style daily AQI** (`results/archive_coverage.json`) — the project's first real daily targets. QA ran over all of them: 25,075 flagged rows, 0 deleted. Static features: elevation for all 135 stations and the CAMS cell id, which shows 135 stations falling into 22 cells with 126 sharing one (`results/static_features.json`). Still missing: the licensed CPCB CCR export, archived CAMS from ADS, and scale — acceptance needs 100 stations with a year each. |
| WP2 — forecasting and accuracy | **PARTIAL** | The two baselines that need no forecast are scored on real days: persistence MAE 13.7 (n=643, 81.8% band agreement), prior-only monthly climatology MAE 18.0 (`results/baselines_measured.json`). Everything requiring a matched issue-time forecast stays PENDING with its reason. |
| WP3 — uncertainty and advisory | **NOT STARTED (blocked)** | `results/uncertainty.json`, `advisory_tradeoff.json` PENDING. Needs WP2. |
| WP4 — HAI v2 | **PARTIAL** | AQHI-style excess-risk framework, CPCB-anchored scale, Monte Carlo harness separating the aggregation effect from vulnerability (`src/features/hai_v2.py`, 14 tests). `config/hai_factors.yaml` adopts no coefficient and every cohort factor is 1.0 with a stated reason; the generated `paper/tables/hai_factors.tex` cannot show what the register has not adopted. v1 is labelled heuristic and superseded in the UI. |
| WP5 — historical analyses | **PARTIAL** | Shared exposure-window code with a boundary-layer caveat (L34, L35 FIXED). Causal "policy lever" claims removed from the generator, the UI and the committed artefacts; each archetype now carries an explicit NOT_ESTABLISHED attribution (L30 FIXED). Clustering rework and deweathering still need ERA5 and coverage-gated features. |
| WP6 — server, platform, security | **DONE for what is reachable** | Fixed-time issuance works (12 ledger rows, cron succeeded 2026-10-11 14:30 UTC). Three readiness gates now compute from facts instead of being hard-coded False. Security gate passes on eight checkable controls, with unknown treated as not-passing (`results/research/security_gate.json`). Path leaks fixed at the writers and guarded in CI. Missed-run alerting renders, records and surfaces without sending, since no channel is authorised. Remaining: no model registry entry (waits on WP2), no uptime monitor. |
| WP7 — UI/UX | **MOSTLY DONE** | MapLibre atlas, 29 screenshots at 375 px and 1280 px, Lighthouse mobile 0.95 performance and 1.00 accessibility, PWA manifest and social cards. Translation review is now per string with a gate that refuses any unreviewed string and falls back to English; the footer computes its language claim from that ledger (`docs/I18N_REVIEW.md`). The uncalibrated confidence percentage is withheld with its reason. Intervals and band probabilities wait on WP3; alerts wait on an authorised channel. |
| WP8 — people impact | **PARTIAL** | `docs/USER_STUDY.md` and `docs/PILOT_LOG.md` written in advance, both explicitly unauthorised to run, with measures, consent terms, what will not be collected and the analysis fixed beforehand. Population exposure still needs licensed gridded data. |
| WP9 — paper and article | **PARTIAL** | `paper/refs.bib` generated from Crossref, the arXiv API and official pages: 21 of 21 candidates verified against expected titles, de Bont 2024's volume and pages resolved from the record. Tables generated, each row naming its artefact and key. Manuscript gains Related Work (stating it claims no first health-weighted index), the HAI v2 section, an ethics statement and an AI-use disclosure. `paper/CHECKLIST.md` separates what the script checks, what needs LaTeX, and what needs a human. `article/medium.md` is fresh prose with a CI-enforced originality check. |

Readiness gates: **5 of 17** (`results/research/research_readiness.json`), up
from 3, both additions evidence-backed rather than asserted.

## What is blocked, and on what

| Blocker | Blocks | Who |
| --- | --- | --- |
| Copernicus ADS credential and licence acceptance | WP2, WP3, the bias atlas, every forecast-skill claim | human action 2 |
| Licensed CPCB CCR hourly export | WP1 acceptance at national scale | human action 3 |
| OpenAQ request allowance (200/hour in its own pool here) | the time a full archive walk takes — tens of hours at this cap | confirm the key's tier |
| Database storage | a full backfill into Supabase; the bulk archive goes to files instead | storage decision |
| Qualified health-evidence review | every HAI v2 coefficient and cohort factor | human action |
| Named Tamil and Hindi reviewers | any non-English health string | human action 7 |
| Licensed gridded population | population exposure | human action |
| Ethics approval | the comprehension study | human action 6 |
| Author details and a chosen conference | paper submission | human actions 4 and 5 |
| Calendar time | the 30-day prospective record, which began 2026-10-11 | nobody — it takes 30 days |

## Next tasks

1. Keep walking the OpenAQ archive. `python -m scripts.backfill_openaq_archive
   --days 365 --stations N --offset M --sink files`, then
   `python -m scripts.audit_archive_coverage` and
   `python -m scripts.evaluate_measured_baselines`. Each walk stops cleanly on
   the request budget and leaves its summary.
2. Protect the prospective record: run
   `python -m scripts.check_issuance_heartbeat` after each 20:00 IST cutoff. It
   exits 2 on a missed run, and a missed day cannot be recovered.
3. When ADS access exists, build the archived-forecast pairing, then WP2's
   baseline ladder against the floor already measured.
4. Install a TeX toolchain (or use Overleaf) to close the page-count and
   embedded-font checks in `paper/CHECKLIST.md`.
5. Decide the storage question before any large backfill into Supabase.
