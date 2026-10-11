# AirGuard India — progress ledger

Reconstructed 2026-10-11 by inspecting the checkout Codex left behind (branch
`codex/airguard-research-production`, HEAD `d29a411`). Nothing was redone; this file records what
already exists, with the file or artefact that proves it.

## Build and test state at reconstruction

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `./.venv-live/Scripts/python.exe -m pytest -q` | 344 passed, 54 s |
| Web unit tests | `webapp$ npm test` (vitest) | 25 passed, 5 files |
| Types | `webapp$ npm run typecheck` | clean |
| Lint | `webapp$ npm run lint` | clean |
| Production build | `webapp$ npm run build` | 17 routes prerendered, no errors |

Nothing is broken. The tree is dirty but coherent: 19 modified files and 14 untracked paths, all of
them regenerated evidence (results, screenshots, reports) or new verification scripts. No stray
TODO/FIXME, no failing import, no half-applied migration.

## Work packages

| WP | Status | Evidence |
| --- | --- | --- |
| WP0 — audit and scaffolding | **PARTIAL** | `docs/AUDIT_CONFIRMATION.md`, `PLAN.md`, `HUMAN_ACTIONS.md`, `Makefile`, `CITATION.cff` all exist and `make test` works. Fails its own acceptance criterion: the audit marks 36 of 52 limitations UNASSESSABLE because Codex never received the Part B table. That table is now in `docs/MASTER_SPEC.md`, so the audit can be completed honestly. |
| WP1 — data layer | **PARTIAL** | Done: provider adapters with retries and `ingestion_runs` health rows (`src/ingestion/`), QA/QC module `src/qa/` with `results/qa_summary.json` and `tests/test_hourly_qa.py`, `docs/DATASET_CARD.md`, `docs/DATA_SOURCES.md`, `results/data_coverage.json`, 135 station rows in Supabase. Missing: CPCB CAAQMS hourly archive (`station_daily_targets` = 0), archived CAMS from ADS (no credential), archived issued weather for training. Acceptance (≥100 stations × ≥1 year of QA'd targets paired with archived CAMS) is unmet and externally blocked. |
| WP2 — forecasting and accuracy | **NOT STARTED (blocked)** | `results/backtest_main.json`, `backtest_spatial.json`, `ablation.json`, `bias_atlas.json` are honest `PENDING` stubs: "Insufficient genuine issue-time station pairs". Protocol and split code exist (`docs/PROTOCOL.md`, `src/research/protocol.py`, `src/research/legacy_cv_audit.py`). Needs WP1 data. |
| WP3 — uncertainty and advisory | **NOT STARTED (blocked)** | `results/uncertainty.json`, `advisory_tradeoff.json` are `PENDING` stubs. Needs WP2. |
| WP4 — HAI v2 | **NOT STARTED (blocked)** | `results/hai_v2.json`, `hai_sensitivity.json` are `PENDING` stubs: verified coefficients and human evidence review required. Legacy HAI v1 remains at `/historical-replay`. |
| WP5 — historical analyses | **NOT STARTED (blocked)** | `results/clusters_v2.json`, `events_deweathered.json` are `PENDING` stubs. One exception already shipped: the clean-window method is now shared between live and historical code (`src/features/exposure.py`, `src/features/safe_window.py`, `tests/test_shared_exposure.py`). |
| WP6 — server, platform, security | **MOSTLY DONE** | Fixed-time issuance works: `airguard-research-issue` (`30 14 * * *` = 20:00 IST) succeeded 2026-10-11 14:30 UTC and wrote 12 `research_forecast_runs` (`results/release/database_audit.json`). Four Supabase cron jobs active. Performance accepted: cached p97.5 = 192 ms, uncached = 3377 ms (`results/perf.json`). RLS on every AirGuard table, 0 duplicate record keys, 0 missing provenance, 9 migrations applied. CI at `.github/workflows/quality.yml` runs tests, `scripts.check_public_exports`, typecheck, lint, build, npm audit. Async precompute and request queue documented in `docs/ASYNC_LIVE_DATA.md`. Remaining: no model registry entry (`model_versions` = 0, waits on WP2), no missed-run alert channel, CI lacks the literal absolute-path grep the spec asks for. |
| WP7 — UI/UX | **MOSTLY DONE** | MapLibre atlas exists (`webapp/app/components/AtlasMap.tsx`, `maplibre-gl` 6.13.0). Screenshots for all 15 routes at 375 px and 1280 px in `docs/screens/`. Lighthouse mobile: performance 0.95, accessibility 1.00 (`results/lighthouse/live-mobile-final.report.json`). PWA manifest route, OpenGraph and Twitter cards in `webapp/app/layout.js`. Mobile tables contained (`c52e949`). Remaining: Tamil/Hindi i18n (no `next-intl`, no named reviewer), opt-in alerts, and the forecast card's interval/band probabilities, which wait on WP3. |
| WP8 — people impact | **NOT STARTED (blocked)** | `results/population_exposure.json` is a `PENDING` stub (licensed gridded population required). No ethics approval, so no user study. |
| WP9 — paper and article | **PARTIAL** | `paper/main.tex`, `paper/README.md`, `paper/tables/evidence.tex`, `paper/figures/evidence_coverage.pdf`, `paper/medium_draft.md` exist. Missing: `paper/refs.bib`, `paper/CHECKLIST.md`, `article/medium.md` at the spec's path, author details (two literal `<NAME>` placeholders), and every empirical number. `make paper` has never produced a page-count-verified PDF. |

Readiness gates stand at **3 of 17** (`results/research/research_readiness.json`, generated
2026-10-10 18:22 UTC — stale, predates the first successful 20:00 IST issuance).

## Limitations L01–L52

Statuses: **FIXED** = evidence artefact exists; **PARTIAL** = mitigated or disclosed, acceptance
unmet; **OPEN** = confirmed and unaddressed; **BLOCKED** = open and waiting on an external
dependency recorded in `HUMAN_ACTIONS.md`.

| ID | Status | Note |
| --- | --- | --- |
| L01 | BLOCKED | 135 station rows exist, but measured data still comes only from OpenAQ (5 stations, 267 rows); `station_daily_targets` = 0. Needs licensed CPCB exports. |
| L02 | OPEN | Exact data.gov.in error preserved in `results/optional_provider_checks.json`; other providers are not relabelled CPCB. |
| L03 | PARTIAL | Freshness is now computed and labelled per provider (`FRESH`/`STALE`); staleness itself persists upstream. |
| L04 | BLOCKED | ADS credential/terms pending, explicitly skipped by the user. No substitute archive accepted. |
| L05 | BLOCKED | Legacy Kaggle dataset still ends 2020-07-01; replacement needs WP1 station data. |
| L06 | BLOCKED | Recomputation audit stands (`results/hai_divergence.json`); only station hourly data removes it. |
| L07 | PARTIAL | NH3/Pb absence disclosed in the API payload and `docs/DATA_SOURCES.md`. |
| L08 | FIXED | `src/qa/` flags without deletion; `results/qa_summary.json`; `tests/test_hourly_qa.py`. |
| L09 | PARTIAL | 7770 `weather_forecasts` rows carry `retrieved_at`; `results/issue_time_features.json` exists. Not yet a training archive. |
| L10 | PARTIAL | 2275 fire detections stored and shown; ablation F waits on WP2. |
| L11 | OPEN | `correction_status: NOT_VALIDATED` is still the honest answer; no station correction model exists. |
| L12 | BLOCKED | `results/bias_atlas.json` PENDING. |
| L13 | BLOCKED | Same artefact. |
| L14 | PARTIAL | 0.4° grid disclosed on `/methods` and marked MODELLED in the UI. |
| L15 | BLOCKED | Provider does not expose run initialisation; retrieval time is distinguished, not relabelled. ADS archive would supply it. |
| L16 | PARTIAL | Leakage audited (`src/research/legacy_cv_audit.py`); whole-date split code written but never run on real pairs. |
| L17 | PARTIAL | Legacy numbers retained and labelled legacy; restatement belongs to WP2. |
| L18 | PARTIAL | Within-one-band demoted to a diagnostic (`src/research/evaluation.py`); POD/FAR/CSI await WP2. |
| L19 | PARTIAL | SMOTE confined to legacy classifiers; the operational product claims no calibrated probability. WP3 removes it from probability paths. |
| L20 | PARTIAL | Inference moved out of the serverless function; no registered model yet (`model_versions` = 0). |
| L21 | PARTIAL | Model provenance surfaced in `webapp/app/components/OperationalResearchPanel.tsx`; it reads "unknown" until a model is registered. |
| L22 | BLOCKED | Severity-stratified skill needs WP2 pairs. |
| L23 | BLOCKED | Diebold–Mariano and bootstrap CIs need WP2 results. |
| L24 | BLOCKED | Hand-set factors unchanged; `results/hai_v2.json` PENDING pending human evidence review. |
| L25 | OPEN | The 66.9% headline is no longer promoted; the replacement sensitivity analysis does not exist. |
| L26 | OPEN | `literature_review_complete` = false; novelty is not yet re-scoped in writing. |
| L27 | PARTIAL | HAI is labelled an advisory heuristic throughout; no outcome validation claimed. |
| L28 | PARTIAL | Determinism disclosed on `/methods`. |
| L29 | BLOCKED | `results/clusters_v2.json` PENDING. |
| L30 | OPEN | Causal "policy lever" wording in the atlas text has not been verified as removed — check before release. |
| L31 | BLOCKED | Deweathering needs ERA5 retrospective weather. |
| L32 | BLOCKED | Holm correction lands with the WP5 rerun. |
| L33 | BLOCKED | Amaravati anomaly still unexplained. |
| L34 | FIXED | One exposure-window implementation shared by live and historical code; asserted in `tests/test_shared_exposure.py`. |
| L35 | FIXED | Practical-hours filter plus boundary-layer-height caveat, covered by the same test. |
| L36 | PARTIAL | Simulator kept as a demo and excluded from paper claims (`PLAN.md`). |
| L37 | OPEN | 3 of 17 gates; the artefact is stale and under-reports `prospective_logging_active`. |
| L38 | **FIXED** | 12 fixed-time forecasts issued 2026-10-11 from 20:00 IST; cron dispatch `succeeded`; idempotent ledger with RLS. Verifications = 0, which is correct one day in. |
| L39 | PARTIAL | Canonical keying plus unique constraints; `duplicate_record_keys` = 0. Historic near-duplicates are deliberately not merged on rounded-grid identity alone. |
| L40 | FIXED | `results/perf.json`: cached p97.5 192 ms (target ≤ 800 ms), uncached 3377 ms (target ≤ 4 s), 0 errors. |
| L41 | PARTIAL | Public exports are clean and guarded in CI by `scripts/check_public_exports.py`. Five internal files still embed `D:\PODS Project\...` (`results/cleaning_report.json`, `data_quality_report.json`, `feature_engineering_report.json`, `safe_windows.json`, `legacy/safe_windows_v1.json`) and CI has no literal `[A-Z]:\\` / `/Users/` grep. |
| L42 | FIXED | Deferred chart loading, skeletons and retries (`f547d4e`, `0280890`, `docs/ASYNC_LIVE_DATA.md`); Lighthouse mobile performance 0.95. |
| L43 | PARTIAL | Sources are UTF-8 and public artefacts are scanned; no reproducible mojibake case was ever captured, so this cannot be closed as verified. |
| L44 | FIXED | `docs/LICENSES.md` records terms per source; deployment treated as non-commercial. |
| L45 | PARTIAL | RLS everywhere, `request_budgets` rate limiting, input validation, `/status` from ingestion health. No uptime alerting or missed-run alert channel. |
| L46 | FIXED | `webapp/app/components/AtlasMap.tsx` with MapLibre GL and measured-vs-modelled legend. |
| L47 | FIXED | 375 px screenshots for all 15 routes in `docs/screens/`; mobile nav and card-list tables. |
| L48 | BLOCKED | English only; no `next-intl`, no named Tamil/Hindi health reviewer. |
| L49 | PARTIAL | PWA manifest, OpenGraph and Twitter cards shipped; opt-in alerts not built (no authorised channel). |
| L50 | BLOCKED | Users still see a min–max range, correctly labelled as not a confidence interval. Needs WP3. |
| L51 | BLOCKED | No population-exposure estimate, no study, no pilot. |
| L52 | OPEN | Author placeholders, no chosen CFP, no `refs.bib`, no AI-use disclosure in the manuscript yet. |

## Items left half-done, with the exact fix

1. **`docs/AUDIT_CONFIRMATION.md` is 36/52 UNASSESSABLE.** The Part B table now lives at
   `docs/MASTER_SPEC.md` lines 66–155. Rerun `python -m scripts.confirm_phase0` against that text so
   every ID gets a real CONFIRMED / REFUTED / FIXED / OPEN verdict, and drop the "missing
   attachment" caveat from `PLAN.md` and `HUMAN_ACTIONS.md`.
2. **`results/research/research_readiness.json` is stale** (2026-10-10, before the first 20:00 IST
   issuance). Regenerate it; `prospective_logging_active` should now pass on ledger evidence.
3. **Absolute paths in five internal result files**, and no CI guard for them. Sanitise the writers
   (not just the outputs) and add a grep step to `.github/workflows/quality.yml` that fails on
   `[A-Z]:\\` or `/Users/` anywhere under `results/`, `data/` and `webapp/public/`.
4. **Dirty tree with no commit.** 19 modified and 14 untracked evidence paths, including the
   async-production and pool-concurrency verification scripts, screenshots and Lighthouse reports.
   Commit them as regenerated evidence so later work has a clean baseline.
5. **`paper/medium_draft.md` sits at the wrong path** and `paper/refs.bib`, `paper/CHECKLIST.md` do
   not exist. The spec wants `article/medium.md` and a verified bibliography.
6. **Unverified claim to check before release:** the atlas's causal "policy lever" wording (L30).

## Next 5 tasks

1. Commit the current evidence tree, then complete the L01–L52 audit from the now-available Part B
   and regenerate the readiness artefact (closes WP0, corrects L37).
2. Finish WP6 hardening: absolute-path CI grep plus writer-side sanitisation (L41), and a missed-run
   heartbeat alert so the prospective record cannot silently lapse (L45). The 30-day prospective
   window is now running and cannot be backdated, so protecting it comes first.
3. WP1 data layer as far as credentials allow: CPCB station metadata completion, OpenAQ v3 archive
   backfill, static features, and a refreshed `results/data_coverage.json`. Log every blocked
   credential in `HUMAN_ACTIONS.md` rather than waiting on it.
4. WP4 HAI v2 framework with `config/hai_factors.yaml` carrying value, CI, citation and evidence
   note per factor, neutral 1.0 where evidence is absent, plus the Monte Carlo sensitivity harness.
   This is the one scientific work package not gated on archived forecasts.
5. WP7 remainder: forecast-card interval and band-probability rendering behind a feature flag, and
   the `next-intl` scaffolding with `docs/I18N_REVIEW.md` awaiting a named reviewer.
