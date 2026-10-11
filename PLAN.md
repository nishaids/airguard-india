# AirGuard India — delivery and research plan

Created 2026-10-11 for the existing repository. The user's latest instruction authorizes proceeding through all phases, testing and production deployment without asking for approval at each phase. Credential-dependent research and elapsed prospective time remain evidence requirements; authorization cannot manufacture those results.

## Phase 0 prerequisite and scope

`docs/AUDIT_CONFIRMATION.md`, this plan and `HUMAN_ACTIONS.md` are the audit prerequisites. The supplied attachment references a Part B list of L01–L52 but omits that list. The audit records all 52 identifiers, assesses only claims whose IDs are explicitly supplied, and labels the others unassessable. Missing wording is not a reason to stop independent implementation.

Keep the existing Next.js/Python/Supabase application, source provenance, measured/modelled labels, immutable ledgers, historical models and readiness gates. `/forecast` is the operational forecast; the legacy HAI/replay remains `/historical-replay`. A request in the attachment to leave HAI v1 at `/forecast` predates this implemented route separation and is interpreted as preserving access to the legacy feature, not undoing current-air navigation.

## Phases and acceptance evidence

| Phase | Deliverable | Gate and evidence | External dependency |
| --- | --- | --- | --- |
| 0 | Source audit, plan, human-action register, reproducible commands, citation metadata | Audit covers every requested identifier without inventing missing claims; test entry point works | Original Part B wording remains absent |
| 1 | Station/hourly import contracts, provenance, non-destructive QA flags, dataset card and coverage manifest | Actual qualifying station/year counts and matched issue-time archive rows; no placeholder success | ADS terms/key; licensed CPCB historical exports and station metadata |
| 2 | Preregistered cutoff/target/split protocol, baseline ladder, temporal/spatial experiments and bias/ablation outputs | Results regenerate from real paired rows; final holdout locked before evaluation; no empty gate passes | At least one year of eligible station/archive pairs |
| 3 | Pollutant uncertainty, calibrated warning evaluation and proper metrics | Coverage/width/calibration/under-warning measured on independent real outcomes | Phase 2 data and sufficient severe-event support |
| 4 | Evidence registry and HAI v2 framework; neutral factors for unsupported modifiers | Verified coefficients and their units/exposure definitions, sensitivity and generated tables; explicitly experimental until evaluated | Primary-source evidence and human bibliography review |
| 5 | Exploratory clustering, retrospective event analysis and common exposure-window semantics | Stability and event results from versioned inputs; no causal claim from association | ERA5 retrospective weather and event coverage |
| 6 | Production caching, secured schedules/heartbeats, storage integrity, status, CI, performance and security evidence | Real API/DB smoke checks and measured performance; fixed-time run only after actual cutoff; reversible rollout | Platform limits and calendar time; alert channel authorization if used |
| 7 | Usable current/tomorrow UI, truthful map/context, responsive navigation, accessibility and translation review workflow | Route/component/API checks and any executable browser/Lighthouse evidence; no unreviewed health translation | Named Tamil/Hindi reviewers for publication-quality health text |
| 8 | Population exposure analysis contract, study/pilot protocols | Population totals only from licensed gridded data and coverage; study data only after ethics/consent | Population raster/version/licence; ethics approval; authorized participants/outreach |
| 9 | IEEE manuscript source, generated evidence tables/figures, submission checklist and separate article draft | No invented metrics/authors/references; submission readiness explicitly blocked until research/CFP gates pass | Authors/emails/order, conference CFP, bibliography approval, real research results |

The deployable operational app and the station-validated research claim are separate acceptance decisions. A production release may display raw CAMS forecasts with honest limitations while research gates remain pending. A draft paper is not a submission-ready paper when required data are absent.

## Small reviewable changes

1. `audit-and-reproducibility`: Phase 0 documents, repeatable command surface, source manifest and tests.
2. `station-data-qa`: import schemas, provenance and QA flags; additive migration only if needed.
3. `research-protocol-evidence`: immutable protocol, data prerequisites, experiment summaries and evidence indexing.
4. `uncertainty-advisory-framework`: offline uncertainty/calibration code with synthetic software tests clearly excluded from scientific results.
5. `hai-evidence-and-exploration`: coefficient provenance, neutral defaults, exploratory analysis contracts.
6. `production-status-and-caching`: schedule health, freshness, canonical location semantics and production API behavior.
7. `operational-experience`: current/tomorrow navigation, map/accessibility/mobile improvements and testing.
8. `impact-and-publication`: dataset/impact/study documentation, generated paper assets and article draft.
9. `release-verification`: final full tests/build, preview smoke checks, production deployment and post-release verification.

Use an isolated feature branch where practical. The checkout already contains substantial pre-existing uncommitted work; preserve it and do not reset, bulk-stage or falsely attribute it to a new change. Inspect any proposed PR diff before pushing. PR entries above are a plan, not a claim that PRs have been opened.

## Release sequence

1. Implement safe independent work after the Phase 0 prerequisites exist.
2. Run targeted tests as changes land, then the full Python/frontend checks and production build.
3. Build/deploy a preview in the existing Vercel project and verify the route → API → database → provenance flow.
4. Deploy/promote production under the user's explicit final-app authorization, then verify the public domain, current target date, source labels, schedule authorization and status. Record deployment identity and rollback target.
5. Record every incomplete external gate in the shipped status/evidence package. Do not silently hide CPCB failure, fabricate archived runs, label synthetic tests as research, or backdate prospective forecasts.

## Main risks and controls

- **Absent archives:** ADS historical experiments stay `PENDING — ADS credential/terms required`; current CAMS and reanalysis are not substitutes for archived issue-time forecasts.
- **Station targets:** sparse hourly pollutant coverage may prevent a valid daily AQI. Preserve missingness; never manufacture targets from a single pollutant or a different station.
- **Clock and schedule:** before the first real 20:00 IST issue time, zero fixed-time forecasts does not establish scheduler failure. Keep on-demand and fixed-time ledgers distinct.
- **AQI bounds:** monotonic concentration bounds map to AQI bounds only under consistent averaging/eligibility and a simultaneous pollutant coverage argument. Severe open bands are censored; marginal interval coverage is not automatically joint AQI coverage.
- **Canonical locations:** different requested coordinates can share a model grid while binding different stations. Do not destructively merge immutable forecasts on rounded-grid identity alone.
- **Source licences:** code MIT does not grant rights to upstream data or commercial API use; document terms by source.
- **Health claims:** HAI modifiers, effect estimates and advisory thresholds require evidence. Neutral defaults and explicit experimental labels are safer than invented coefficients.
- **Performance evidence:** record observed distributions and environment; do not mark p95/visual/accessibility targets passed from unit tests or HTTP-only checks.
- **Reproducibility:** local raw data are ignored and large model artifacts may be separately distributed. A clean clone must report missing inputs instead of emitting fabricated outputs.
- **Publication:** a finished software deployment does not meet empirical paper acceptance without matched archives, outcomes, author details and conference requirements.
