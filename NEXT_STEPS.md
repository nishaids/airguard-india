# What is left for you to do

The pipeline is complete. All 20 stages ran, 14 of 14 smoke tests pass, and 12
of 13 Definition-of-Done checks pass. The one remaining failure is the
deployment URL, which cannot be recorded until you deploy.

Current state, verified by `python -m src.report.audit`:

| | |
| --- | --- |
| Figures | **41**, all at 300 DPI, all cited by a report, notebook or the app |
| Review documents | **3**, carrying **43 figures and 74 tables** between them |
| Rubric coverage | **30 / 30 / 40 = 100 marks** mapped, one table per document |
| Result artefacts | 16 JSON, 3 CSV, 1 Markdown |
| Model artefacts | 17 versioned joblib files |
| Notebooks | 3, built and executed with real output |
| Commits | 16, phase-wise |
| Smoke tests | 14 of 14 pass, **336** city/cohort/date combinations, zero exceptions |

---

## 1. Fill in the two teammate names

`src/config.py` → `TEAM` currently reads:

```python
{"register_no": "260598", "name": "<NAME>"},
{"register_no": "260600", "name": "<NAME>"},
```

Edit both, then regenerate so every cover page updates:

```bash
python -m src.report.build_docx
```

---

## 2. Deploy and record the URL

```bash
# Push (the repository already has its phase-wise history)
git remote add origin https://github.com/nishaids/airguard-india.git
git push -u origin main
```

Then at [share.streamlit.io](https://share.streamlit.io), create an app with
main file path `app/Home.py` on branch `main`.

`DEPLOY.md` has the full instructions, including which artefacts to force-add
past `.gitignore` and what to do if the build fails.

Finally, record the live URL so the README and Review 3 both cite it rather than
having it typed in by hand:

```bash
python -m src.report.readme --url https://<your-app>.streamlit.app
python -m src.report.build_docx
python -m src.report.audit      # all 13 checks should now pass
git add -A && git commit -m "docs: record the live deployment URL"
```

---

## Before you present

```bash
streamlit run app/Home.py       # check all five pages render
python -m tests.test_smoke      # 14 checks, ~1 minute
python run_all.py               # full reproduction, ~55 minutes
```

---

## Two things worth knowing when you present

**The persistence baseline is the point.** Daily AQI is strongly autocorrelated,
so "tomorrow equals today" already reaches R² = 0.841. Quoting R² = 0.912
without that comparison would overstate the work. The honest claim is the
**20.11% reduction in MAE over persistence**, and the reports lead with it.

**The engineered index turned out to be the strongest feature.**
`HAI_healthy_adult` is the top SHAP driver for *both* the regression and the
classification model, ahead of raw PM2.5 and the AQI itself. The composite this
project invented is more informative to the models than any single measurement
they were given — which is independent evidence for the contribution, obtained
without being aimed at.

---

## Known issues, stated rather than hidden

* **SVM (RBF) reports no ROC-AUC.** It was fitted without Platt scaling to keep
  fit time tractable, so it exposes `decision_function` rather than calibrated
  probabilities and one-versus-rest ROC-AUC is undefined for it. The other eight
  classifiers report it (0.905–0.962); the gap is recorded in
  `results/evaluation_classification.json` under `roc_auc_note`.
* **SHAP cannot parse a current multiclass XGBoost booster.** `shap` 0.49
  predates `base_score` becoming a per-class vector. Rather than pinning an old
  library or explaining a substitute model, `src/models/explain.py` falls back to
  XGBoost's own native TreeSHAP, which is the same algorithm computed by the
  model's own implementation.
* **Tuning is the slow stage (~38 min).** Inner estimators are pinned to
  `n_jobs=1` and the outer search to 3 workers, because this machine showed 84%
  memory load at rest and an unbounded `n_jobs=-1` exhausted memory twice. On a
  larger machine, raise `SEARCH_N_JOBS` in `src/models/tune.py`.
* **The repository is ~453 MB**, mostly `data/raw/`. Those files are gitignored
  and regenerable; see `DEPLOY.md` for what the deployed app actually needs.
