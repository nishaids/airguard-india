# Content for ten presentation slides

Content only; no PPT file or research paper is generated. Keep each slide to these four bullets.

## 1. Problem

- Outdoor decisions need forward information
- Monitoring and forecasts have different meanings
- Missing/stale data create false confidence
- Practical action is constrained

Best visual: Person planning tomorrow + source labels

30-second explanation: Start with a concrete planning need and acknowledge that benefit requires measurement.

Likely cross-question: Why another AQI app?

## 2. Existing gap

- Existing services remain valuable
- A dashboard is not forecasting validation
- Coarse forecasts need local testing
- Advisory benefits are unproved

Best visual: Fair competitor matrix

30-second explanation: Do not downgrade competitors; describe the auditable workflow you want to test.

Likely cross-question: Has this already been done?

## 3. Solution

- Source-labelled nationwide estimate
- Central CPCB-style AQI engine
- Exposure guidance and missing states
- Research correction kept separate

Best visual: Live current/tomorrow cards

30-second explanation: Explain the user flow while naming current validation limits.

Likely cross-question: What is live versus experimental?

## 4. Architecture

- Validated location input
- Bounded provider/cache orchestration
- Shared index and provenance
- API contract to frontend

Best visual: ARCHITECTURE_DEFENSE mermaid

30-second explanation: Trace one location from request to display and point out withholding boundaries.

Likely cross-question: What if APIs fail?

## 5. Data

- OpenAQ-hosted upstream measurements
- Genuine dated CAMS runs
- Forecast weather and optional fire
- Locked QC and rejection ledger

Best visual: MEASURED/MODELLED/DERIVED classification

30-second explanation: Read counts from the measured artifact; never call model output ground truth.

Likely cross-question: Is this synthetic?

## 6. AI/ML

- Raw CAMS plus simple baselines
- Direct versus residual ladder
- Train-only tuning/preprocessing
- Censored Severe excluded from exact error

Best visual: Residual equation + fold diagram

30-second explanation: The hypothesis is that correction helps; raw CAMS wins if evidence says so.

Likely cross-question: Why no deep learning?

## 7. Validation/results

- Chronological and spatial tests
- Preliminary non-CAMS results only
- Severe under-warning disclosed
- Primary/final results pending

Best visual: Verified preliminary diagnostics figure

30-second explanation: Quote the results sheet with its scope, sample counts and intervals.

Likely cross-question: Are you cherry-picking?

## 8. Novelty

- Auditable India-specific integration
- Provenance/QC/validation infrastructure
- Uncertainty/advisory trade-off study
- No world-first assertion

Best visual: NOVELTY_MATRIX

30-second explanation: Separate owned engineering from CAMS physics and established ML methods.

Likely cross-question: Is it CAMS with a UI?

## 9. People impact and failures

- Plausible exposure-aware planning
- No clinical benefit established
- Manual/fallback/unavailable states
- Coverage and access inequities

Best visual: Scenario + failure matrix

30-second explanation: Describe feasible use, not guaranteed health improvement.

Likely cross-question: Who benefits if shifts cannot change?

## 10. Conclusion

- Prototype flow is tested
- Evidence gates remain explicit
- Archive → selection lock → one final test
- Production correction needs separate approval

Best visual: Claim-evidence checklist

30-second explanation: Finish with the current blocker and the next evidence gate instead of a marketing claim.

Likely cross-question: What is your biggest weakness?


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
