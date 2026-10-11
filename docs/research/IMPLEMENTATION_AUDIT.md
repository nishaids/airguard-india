# Implementation audit, 12 October 2026 (IST)

The v3.1 protocol, its lock history and preliminary plan remain unchanged. These
are implementation repairs, not choices based on final-test performance. The
final test has not been scored.

The initial immutable preliminary run
`29e43a4d61965d039d42587a272512a34610f5b1e0ed09c25e29cf662980649a`
is retained for audit. Its spatial results and history-feature ablation are
superseded by the audited implementation:

- Spatial fold assignments previously used the universe of stations with valid
  targets. They now use the complete, frozen metadata-only station catalogue;
  target availability cannot reshuffle groups.
- The history ablation compared models trained on different populations.
  Both feature variants now train on identical conditional-history rows.
- The row-level rejection ledger now shares the actual filter validator;
  unknown coverage or timezone cannot be mislabelled as a stuck sensor.
- Derived cache identity includes the AQI engine and availability rules, with
  normalized source text for checkout portability.
- The experiment runner independently checks actual feature values and their
  provenance, including conditional measured-bin timestamps, before fitting.
- Advisory selection refuses nonfinite, misaligned or invalid-category pairs.
  NaN forecasts cannot appear to satisfy the under-warning target.

The initial run's temporal point comparisons are retained as partial-data
history, not final conclusions. Corrected runs use new immutable directories,
new source/data hashes and the same predeclared model settings. No old result
artifact is edited. Subsequent raw acquisition enlarges the dataset; reports
must identify which exact acquisition snapshot each result used.

Five inherited OpenAQ windows flagged `page_limit_reached` were checked with
only page 2 of their original requests. Each extra page was empty; no additional
bins existed and no raw file was replaced. Checksummed request checkpoints and
terminal `no_missing_rows` records prevent repeated calls. Future acquisitions
paginate full windows automatically and retain per-page checkpoints.

The production source audit also repaired dated operational sensor selection,
actual response receipt timestamps and nearby-candidate filtering before its
limit. These changes are tested locally and **not deployed**. The existing 12
station-free forecasts and their missing issuance SHAs remain immutable.
