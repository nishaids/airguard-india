# IEEE journal development draft

Compile `main.tex` from this directory with IEEEtran and BibTeX (Tectonic handles both). This version uses `\documentclass[journal]{IEEEtran}` with the standard Letter layout. The already-open standalone editor source remains `paper/station_calibration_skeleton.tex` and contains the same journal narrative with an embedded bibliography and native vector figures.

The companion conference variant is `paper/conference/main.tex`. See `paper/FORMAT_REFERENCE.md` for the reference-derived structure, deliberate layout improvements, evidence boundaries and regeneration instructions. `scripts/format_publication_drafts.py` now refreshes both variants from the verified development summaries. The previous packaging entry points delegate to it once the new format manifest exists, preserving their historical implementation without restoring the old layout.

Primary results, model parameters, and MODEL_SELECTION_LOCK are pending; no numerical placeholders are treated as results. The separate preliminary non-CAMS study cannot establish an improvement over raw CAMS. LogSight and PlanGen are presentation references only. Venue-specific author instructions and a complete evidence audit are still required before submission.
