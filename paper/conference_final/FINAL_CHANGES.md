# Final camera-ready changes

Base: the compiled manuscript in this folder. No experiment was rerun, no data re-downloaded, no literature search repeated. Figs. 1 and 2 were kept; Figs. 3-5 were redrawn from the existing `evidence/verified_numbers.json` and `evidence/rows_temporal.parquet` by `scripts/make_figures_simplified.py`.

## Structure

- Standalone **Limitations** section: removed. The scientifically necessary boundaries are now two sentences at the end of the Insights subsection (development-stage evidence under the fixed previous-evening contract; conditional on the assumed three-hour receipt latency; protected interval remains the confirmatory step).
- Standalone **Acknowledgment**: kept only as a mandatory two-sentence AI disclosure (see below).
- Results renamed **Results and Discussion**, with subsections A-D (RQ1-RQ4), **E. Working AirGuard Application** and **F. Insights** (four compact insights).
- **VII. Conclusion and Future Implementation**: one findings paragraph, one lesson paragraph, one future-work paragraph in future tense (CAMS archive completion, CAMS-to-station residual calibration, model-selection lock, protected final evaluation, severity-aware forecasting, adaptive and severity-conditioned conformal calibration, fuller pollutant support, receipt-time logging, prospective verification, in-app forecast verification). Nothing planned is described as completed.

## Figures

- **Fig. 3** simplified: one single-column forest plot of the four paired contrasts with 95% block-bootstrap intervals and a zero line. The two monthly-MAE line charts were removed.
- **Fig. 4** simplified to two panels: geographic exclusion (all pairs and Poor-or-worse pairs) and the censored-Severe forecast distributions with the 401 lower bound. The bias-by-category panel was removed; those numbers are now stated in the text.
- **Fig. 5** simplified to two panels: coverage of nominal 90% split-conformal and CQR intervals by observed category, and the warning trade-off with P0-P2 and the raw quantile curve. The fold-by-fold coverage panel was removed.
- **Fig. 6** screenshots: two real, unretouched crops, now printed full width at 0.82\textwidth instead of a small single-column block. (a) `01_Main_Dashboard.png` next-day forecast card; (b) `05a_Research_Operational_Validation_Status.png` research status. Crop boxes and source hashes in `evidence/application_figure_manifest.json`.

## Length and references

- Page count: **6** (A4, IEEEtran conference, unchanged margins and font sizes). Last page right column fills about 90%.
- Trimmed redundant prose in the introduction, related work, evaluation design, application subsection, insights and conclusion; shortened Figs. 1 and 2 by 6%.
- References reduced from 31 to 24 by removing citations that no longer carry a claim after the trims (riccio2024, natarajan2024, wadoux2021, qiu2023, gibbs2021, gneiting2011, angelopoulos2024, saberian2017, garciacrespi2026). Entries remain in `references.bib`. CPCB methodology, leakage, Indian background and forecasting, the strongest CAMS post-processing work, spatial validation, split conformal, CQR, non-exchangeable conformal, forecaster's dilemma, cost-loss warning value, the data sources and the block bootstrap and Diebold-Mariano references are all retained.

## AI disclosure and artifact scan

- IEEE submission policy requires AI-generated content to be disclosed in the acknowledgments section of the article, naming the system and the affected sections. The paper is AI-drafted, so the disclosure is mandatory and cannot be removed; it is now a single sentence. See `AI_DISCLOSURE_AUDIT.md`.
- `scripts/final_checks.py`: no TODO, PLACEHOLDER, RESULT PENDING, tool markers, Markdown remnants, temporary paths or watermark text in the source or the PDF; no overfull boxes; no undefined references; all citations resolve.
