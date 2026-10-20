# AirGuard India — completion report, 20 October 2026

Supersedes the 13 October checkpoint (preserved in git history). Every number below comes from a committed artefact named beside it. A working deployment does not show forecast accuracy, and the two are reported separately.

**1. Executive summary.** Production is updated and verified; the research is **not** complete. The primary CAMS experiment cannot run until the archive holds enough months: 10 of 36 files are verified and the first protocol-eligible fold needs 10 more. Acquisition was re-authorised by the author today and is running. No model was selected or locked, the sealed final test was not touched, and the paper is unchanged.

**2. Repository checkpoint.** Branch `research/station-calibration`, pushed to `github.com/nishaids/airguard-india`. Working tree clean at each commit; no force-push, no history rewrite.

**3. Earlier Claude Code and Codex work recovered.** All preserved: measured dataset (v3.1), locked protocol, six-page paper snapshot, exploratory Severe, uncertainty, warning and survivorship extensions, guarded primary runner, receipt provenance, prospective ledger, verified 13 October deployment. Nothing was redone.

**4. Data sources.** `DATA_SOURCE_REGISTER.md` (generated): ten sources classified OBSERVED / ARCHIVED_OPERATIONAL_FORECAST / LIVE_FORECAST / MODELLED_OUTPUT; no reanalysis used. Station targets are CPCB-network monitors through OpenAQ, not official CPCB data. The official data.gov.in feed has 0 successful and 187 failed recorded ingestions; today its host answered but returned HTTP 502 after about 60 s.

**5. CAMS acquisition.** `CAMS_ARCHIVE_STATUS.md`: 10/36 verified, 2 running, 24 to submit, 0 duplicates, 0 unresolved failures. The June request pending since 13 October had expired on the server (HTTP 404) and was retired with its ID kept; the worker now downloads each result at once.

**6. Station matching.** `CAMS_STATION_MATCHING_REPORT.md`: 18,540 station-days, 180 stations, 100 cities, 103 dates, 11,634 exact and 7 censored Severe targets, **0 availability violations**. Rebuilt today with identical hashes. Nearest 0.4-degree cell; coastal cells not yet audited.

**7. Development model comparison.** Not run: preflight `BLOCKED_NO_ELIGIBLE_FOLDS`. Folds 1-4 can never meet the locked 120 valid training days per station; fold_05 needs CAMS through 2025-11-16.

**8. Model selection.** NOT READY. No `MODEL_SELECTION_LOCK` (correctly). No rule was relaxed.

**9. Severe events.** Exploratory, non-CAMS only (`DEVELOPMENT_EXTENSION_AUDIT.md`): no tail learner dominates; Severe kept as lower-bound censored. Primary evaluation pending.

**10. Uncertainty.** Exploratory only; marginal coverage hides poor coverage in polluted categories (pilot: 57-75% of Severe days inside nominal 90% intervals). Production shows no interval ("not yet available").

**11. Warning policy.** Exploratory operating points only; no policy called optimal; none deployed.

**12. Geographic robustness.** Non-CAMS temporal and geographic holdouts in the paper; CAMS holdouts pending. No nationwide generalisation claim.

**13. Survivorship.** Frozen-cohort sensitivity preserves the main qualitative findings; retired monitors were never acquired (`STATION_SURVIVORSHIP_SENSITIVITY.md`).

**14. Literature and novelty.** `FINAL_NOVELTY_AND_PRIOR_ART_AUDIT.md`: 48 of 56 references verified by Crossref, arXiv or the official page; a logged Crossref search (10 queries, 190 records, 13 added); 28-study matrix; gap and claim matrices. Verdict: every method has prior art; no first-ever or state-of-the-art claim is supported; the combination is a defensible design that becomes a contribution only after the primary experiment.

**15. Public-impact functionality.** Measured/modelled labels, freshness labels, tomorrow forecast with issue time, pollutant breakdown, general exposure guidance with disclaimer, nearest-station context, forecast ledger. Today: the live track record now publishes error figures only with ≥30 checked forecasts over ≥7 days (it had shown one-day anecdotes such as a +249.5 bias), and stale data is no longer cached as current.

**16. Public-impact evaluation.** `PUBLIC_IMPACT_EVALUATION_PLAN.md`: task-based protocol with pre-registered thresholds. Not run: needs ethics approval. No data collected.

**17. Prospective verification.** 108 fixed-time forecasts over 9 target days, 2 verified days, 0 availability violations; live product: 48 forecasts checked on 3 days. No skill claim.

**18. Security.** Secret audit 0 hits across 2,327 git objects, the working tree and 50 browser assets; CSP, HSTS, nosniff, frame-deny and permissions headers live; all database tables under RLS. Credentials once pasted in chat should be rotated by the author.

**19. Backend tests.** 681 passed (full suite); source-bound offline validation 677 collected, 672 passed, 5 skipped, 0 failed.

**20. Frontend tests.** 44 unit tests pass; lint, type check and production build pass.

**21. Browser tests.** Live home page checked at desktop and 375 px; track-record section verified after release. A first visit to an uncached place takes about 20 s with an honest loading state.

**22. Performance.** Cached summary responses 0.2 s; uncached about 3 s per request with a queued 20 s first build. No new infrastructure added.

**23. GitHub.** Pushed; remote head matches local at push time.

**24. Deployment.** `docs/DEPLOYMENT_COMPLETION.md`: deployment `dpl_4YKByhjbQLA8Z7Tsi9U7PXSP44Bd`, commit `6f4da73`, 31 staged and 37 public checks. The first candidate was not promoted because staging exposed a cached-format hazard; fixed first.

**25. Paper.** PRESERVED. `paper/` unchanged this session.

**26. Final test.** SEALED. Code-level guards and tests refuse sealed rows. Approval not requested: no lock, no READY audit.

**27. Remaining blockers.** CAMS archive (ADS queue time; needs the laptop awake); ethics approval for the study; author acceptance of the literature audit; time for the prospective record; official CPCB feed (server-side 502).

**28. Next human action.** Keep the CAMS worker running until at least the November 2025 files verify (command in `CAMS_ARCHIVE_STATUS.md`); rotate the API keys and database password that were pasted into chat; decide on ethics submission for the comprehension study.

Gates (`results/research/research_readiness.json`): research 5/17, `COLLECTING_NOT_RESEARCH_READY`. Production gates for this release: all met.
