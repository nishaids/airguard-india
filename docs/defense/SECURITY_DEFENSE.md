# Security and privacy defense

Credentials live in server/private runtime configuration, not the browser. ADS acquisition suppresses client output, exception bodies and download URLs; its audit stores allowlisted request/status/checksum metadata. The private ADS credential file is never displayed or read by the audit script.

Browser persistence: selected location and advisory cohort are stored locally. Location is also included in shareable URLs and sent to the service/providers. This is not anonymous from infrastructure operators. Cohort is evaluated browser-side and not included in the current summary request; do not claim no data is stored.

Server database stores environmental observations, source snapshots, cache keys/location requests, provider events, budgets, forecasts and verification pairs. No diagnosis is required by this flow. Raw location-linked cache records could still reveal a place of interest. Retention and institutional privacy policy require product review before large-scale use.

Controls: fixed outbound provider URLs; allowlisted API operations; coordinate and label validation; bounded requests/body sizes; parameterised SQL; RLS; authenticated internal refresh; safe generic HTTP errors; immutable issuance; client response validation; security headers. Service-role privileges stay server-side. RLS is not a substitute for server authorisation when privileged credentials are used.

Evidence: `results/release/secret_audit.json`, `database_audit.json`, `src/qa/security.py`, security and request-scope tests. These are scoped audits, not penetration certification. No credential values or database connection strings belong in viva screenshots, logs or demo slides.


Evidence checkpoint: measured dataset `4761a5da60dde059b1c7bbfc5403e32d26c983f80e3fc22683eba8a13119821d`; preliminary run `287c87db04a6b29459374c4d50637f943c04dfe10d9072d7e296b74ad1d45a3f`; protocol `e24b664747029a7611efcf4fb19b8cfdf8b12762d379927698fa6e98777d67e8`. Primary CAMS development/final/prospective performance must never be inferred from this non-CAMS run. See [claim ledger](CLAIM_EVIDENCE_MATRIX.md) and [results sheet](ONE_PAGE_RESULTS.md).
