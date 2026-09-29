# Where this build stopped, and how to finish it

Everything in `src/`, `app/`, `tests/` and `scripts/` is written and
syntax-verified (all 27 modules import cleanly). Stages 1–9 of the pipeline have
run and their artefacts are on disk. The remaining work is **running the last
stages and committing**, not writing code.

---

## Completed and verified

| Stage | Artefact | Status |
| --- | --- | --- |
| acquire | `data/raw/PROVENANCE.json`, `reports/dataset_provenance.md` | done — licence **CC0 1.0** verified live, SHA-256 for 5 files |
| quality | `results/data_quality_report.json` | done — 12 of 26 cities retained, every exclusion tabled |
| clean | `results/cleaning_report.json`, `data/processed/city_day_clean.csv` | done — imputation bake-off, 3,633 event-days protected |
| features | `results/feature_engineering_report.json`, `results/hai_divergence.json` | done — 178→100/102 features, **66.92%** cohort divergence |
| safe_windows | `results/safe_windows.json` | done — 39.6% vs 8.0% diurnal swing |
| eda | `results/eda_statistics.json`, `results/eda_insights.json` | done — 14 numbered insights |
| regression | `results/evaluation_regression.json` | done — LightGBM **MAE 15.10**, **+20.1%** over persistence |
| classification | `results/evaluation_classification.json` | done — XGBoost+SMOTE **macro-F1 0.7411**, ROC-AUC 0.959 |
| clustering | `results/evaluation_clustering.json` | done — k=2, **ARI 1.000** across algorithms |
| policy | `results/policy_simulation.json` | done — −37.0% vs measured −34.0% lockdown |
| cards | `reports/data_card.md`, `reports/model_card.md` | done |
| diagrams | figures `39`, `40` | done |
| Review 1 | `reports/Review1_Problem_and_Dataset.docx` | done — 5 figures, 20 tables |
| Review 2 | `reports/Review2_Preprocessing_and_EDA.docx` | done — 23 figures, 25 tables |
| README | results table injected from `results/*.json` | done |

**29 figures, all verified at 300 DPI.**

---

## Remaining — run these in order

`src/models/tune.py` was running when the build stopped. If
`results/tuning_report.json` exists, skip step 1.

```bash
cd "D:/PODS Project/airguard-india"
python run_all.py --from tuning
```

That single command runs the remaining stages in dependency order:

| # | Stage | Produces | Typical time |
| --- | --- | --- | --- |
| 1 | `tuning` | `results/tuning_report.json`, figure 26 | ~20 min |
| 2 | `evaluation` | 3 master comparison CSVs, `results/final_model_selection.md`, `results/error_analysis.json`, figures 27–35 | ~3 min |
| 3 | `explain` | `results/explainability.json`, figures 36–37 | ~2 min |
| 4 | `policy` | already done, idempotent | <1 min |
| 5 | `cards` | regenerates both cards with the error-analysis numbers | <1 min |
| 6 | `diagrams` | idempotent | <1 min |
| 7 | `notebooks` | builds **and executes** the three phase notebooks | ~5 min |
| 8 | `reports` | all three `.docx`, PDFs if LibreOffice is present, `reports/CHANGELOG.md` | ~2 min |
| 9 | `readme` | re-injects the live results table | <1 min |
| 10 | `smoke` | exercises every city × cohort × 4 dates through the app's inference layer | ~3 min |
| 11 | `audit` | `results/definition_of_done.json`, `reports/AUDIT.md` | <1 min |

If a stage fails, re-run just that one:

```bash
python run_all.py --only evaluation
python run_all.py --list          # see all 20 stages
```

---

## Then: commit, deploy, record the URL

```bash
# 1. Phase-wise commit history (13 commits telling the project story)
bash scripts/make_commits.sh

# 2. Push
git remote add origin https://github.com/nishaids/airguard-india.git
git push -u origin main

# 3. Deploy at share.streamlit.io, main file path: app/Home.py
#    (full instructions and the force-add list are in DEPLOY.md)

# 4. Record the live URL so README and Review 3 both cite it
python -m src.report.readme --url https://<your-app>.streamlit.app
python -m src.report.build_docx
python -m src.report.audit        # the deployment check should now pass
```

Verify locally first:

```bash
streamlit run app/Home.py
python -m tests.test_smoke
```

---

## Two things only you can do

1. **Fill in the two teammate names.** `src/config.py` → `TEAM` currently has
   `260598` and `260600` as `<NAME>`. Edit them, then re-run
   `python -m src.report.build_docx` so every cover page updates.
2. **Deploy and paste the URL** (step 3–4 above). Until then the audit's
   deployment check reports FAIL by design, rather than claiming a URL that does
   not exist.

---

## Known issues, stated rather than hidden

* **SVM (RBF) has no ROC-AUC.** It was fitted without Platt scaling to keep fit
  time tractable, so it exposes `decision_function` rather than calibrated
  probabilities, and one-versus-rest ROC-AUC is undefined for it. The other
  eight classifiers all report it (0.905–0.962). The gap is recorded in
  `results/evaluation_classification.json` under `roc_auc_note`.
* **Tuning is the slow stage** (~20 min). Inner estimators are pinned to
  `n_jobs=1` and the outer search to 3 workers, because this machine showed 84%
  memory load at rest and an unbounded `n_jobs=-1` exhausted memory twice. If
  you run on a larger machine, raise `SEARCH_N_JOBS` in `src/models/tune.py`.
* **`.gitignore` excludes `data/processed/*.csv`**, which the deployed app
  needs. `DEPLOY.md` lists the exact force-add commands.
