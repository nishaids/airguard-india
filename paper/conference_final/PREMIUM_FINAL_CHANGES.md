# Premium final pass

Editorial, visual and consistency pass on the existing six-page manuscript. No experiment was rerun, no new number was created, the sealed interval (10 July to 7 October 2026) was not read, and the CAMS status is unchanged.

| Item | Status |
|---|---|
| Severe contradiction | **Corrected.** The conclusion no longer says that no forecast reaches the Severe bound. It now states that Weather Ridge never reaches the lower bound and that, among the 306 Severe cases with history, persistence reaches it on 147 and History Ridge on 1. Abstract ("no interval reaches the Severe lower bound"), RQ3, RQ4 ("no weather-based rule ever issues Severe") and Insights say the same thing. |
| Three-pollutant AQI | **Clarified** in the abstract ("three-pollutant CPCB-style AQI reconstructed from PM2.5, PM10 and ozone"), at the start of Section III-B ("not the officially issued index") and in the conclusion. The existing note that the index can fall below the official one when an unmeasured gas dominates is kept. |
| Novelty paragraph | **Strengthened.** "No estimator here is new" is kept and followed by what is distinctive: an availability-constrained evaluation framework linking temporal skill, station, city, urban-cluster and regional holdouts, lower-bound Severe outcomes, severity-conditioned uncertainty and two-sided warning losses on one station-day population, with completed evidence kept apart from the CAMS extension and the deployment. The claim is scoped to the studies cited; no "first" or "state of the art" wording. |
| Fig. 1 | **Simplified.** Three lanes on one eight-column grid, two-line labels at most, no sentences in boxes. Lane B: tinted dashed stages are partially complete, grey dashed stages have not started, with the label "operational calibration pending". |
| Fig. 2 | **Simplified.** (a) pre-issue information on the left of the 20:00 issue line, prohibited target information on the right. (b) one fold as training, embargo, calibration, embargo, evaluation, 30-day advance, then "FINAL 90 DAYS SEALED". |
| Figs. 3-5 | **Redesigned** in one design language: three tones, 8 pt minimum text, direct labels in place of legend boxes where possible. Fig. 3 uses two classes only (interval excludes zero, or no established difference). Fig. 4(b) labels curves directly and marks "Severe lower bound = AQI 401". Fig. 5(b) labels only the ends of the raw-quantile curve. |
| Tables I-III | **Restyled** with a light grey header, very light group rows, no vertical rules and short definition notes. Table I groups the two populations and states that they are not ranked against each other. Table II sets the Very Poor column in bold. Values are unchanged and still generated from `evidence/verified_numbers.json`. |
| Screenshots | **Enlarged and re-cropped.** The supplied 1,353-pixel desktop captures cannot be read at half the text width, so the two panels were re-captured from the production site on 13 October 2026 at a compact viewport and three-times pixel density (`scripts/capture_application.cjs`, read-only page views). Each panel is 0.455 of the text width, equal height, with a thin grey rule. (a) current and next-day AQI, category, dominant pollutant, source, issue time and correction status; (b) forecast mode, CAMS baseline, correction status, issue time and target, data source and freshness, prediction interval and prospective verification. Crops are by measured element boxes with no retouching; hashes are in `evidence/application_figure_manifest.json`. |
| Future CAMS work | **Retained accurately**: 6 of 36 archive chunks verified, no correction fitted; completion of the archive is described in future tense. |
| Station survivorship | **Added to future work**: a sensitivity analysis that freezes station eligibility before the development interval. |
| Acknowledgment | **Not removed.** One sentence remains. IEEE submission policy requires AI-generated content to be disclosed in the acknowledgments, and no target venue with a different rule has been named (see `AI_DISCLOSURE_AUDIT.md`). |
| References | 24 printed. Conformal risk control is cited again where the P3 rule is defined. |
| Page count | **6** (A4, IEEEtran conference, unchanged margins and font sizes); last column 99% full; no overfull boxes; all fonts embedded. |

## Rebuild order

```
python scripts/make_tables.py            # number macros (tables/numbers.tex)
python scripts/make_tables_premium.py    # styled tables; must run after make_tables.py
python scripts/make_figures_premium.py   # Figs. 1-6
tectonic --keep-logs main.tex
```

`scripts/make_figures.py`, `scripts/make_figures_simplified.py` and `scripts/make_application_figure.py` are superseded by `make_figures_premium.py` and should not be run; they would overwrite Figs. 1-5 with the earlier layouts.
