# Deployment completion

Status: **PRODUCTION_DEPLOYED_AND_VERIFIED**.

Live URL: https://webapp-phi-taupe.vercel.app. Existing project: `prj_CRhIlQYLGST3dBwUfTiFgJXa25qe`. Deployment ID: `dpl_pFFAE3FypQiA8NWaG52DHkK51tT9`. Deployed code SHA: `9ac8b5a607246ced7150bfa47591c3398d72b5d8`.

The production-configured candidate was staged without replacing the live domain, passed 31 route/API checks and an authorized refresh, then was promoted. Public verification passed 37 checks across Chennai/Avadi, Delhi, Mumbai, Kolkata, Bengaluru, Hyderabad, Kochi and a low-monitor-coverage location. All 28 browser checks passed across 14 routes at 375 and 1280 pixels, including errors and horizontal overflow.

A cold-cache request confirmed real receipt-bearing CAMS/weather snapshots in the database. Request/response times are separate from raw payloads and unavailable forecast initialization remains unknown. Future fixed-time issuance receives the runtime Git SHA; historical missing identities and station bindings are unchanged.

The upload contains only webapp and its curated runtime bundle. Offline calibration, post-paper experiments, raw research caches, credentials and the paper are excluded. No experimental correction or interval is deployed. The final test remains sealed.

Evidence: `results/release/codex_continuation_deployment.json`, `codex_continuation_preflight.json`, `codex_live_browser.json`, `results/research/staged_production_acceptance.json`, `production_acceptance.json` and `prospective_receipt_validation.json`.

The six-page conference paper is preserved on the research branch as a frozen submission snapshot; it is outside the deployment upload.
