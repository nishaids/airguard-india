# Deployment

The AirGuard India application is deployed to **Streamlit Community Cloud**,
which is free and requires no card.

---

## 1. What the deployed app needs

The application loads artefacts rather than recomputing them, so the following
must be present in the deployed repository:

| Path | Contents | Approximate size |
| --- | --- | --- |
| `models/*.joblib` | Fitted model artefacts | see note below |
| `results/*.json`, `results/*.csv` | Every metric the app displays | small |
| `data/processed/features_full.csv` | Feature matrix for lookups and history charts | ~30 MB |
| `data/raw/PROVENANCE.json` | Provenance block shown on the Home page | small |
| `reports/figures/*.png` | Figures shown on the Model Insights page | ~15 MB |
| `reports/data_card.md`, `reports/model_card.md` | Rendered in the app | small |

`.gitignore` excludes `data/raw/*.csv` and `data/processed/*.csv` by default,
because the raw layer is large and regenerable. For deployment, **force-add** the
two files the app genuinely needs:

```bash
git add -f data/processed/features_full.csv
git add -f data/raw/PROVENANCE.json
git add models/ results/ reports/
```

Check the total repository size before pushing. GitHub warns above 50 MB per file
and 1 GB per repository; this project stays well inside both when only the files
above are committed.

```bash
du -sh models results reports data/processed/features_full.csv
```

If `models/` is larger than you want to commit, keep only the two deployed
artefacts and the clustering bundle:

```bash
# The app loads only these three, plus the tuned variants when they improved
ls models/regression_lightgbm.joblib \
   models/classification_xgboost_plus_smote.joblib \
   models/clustering_kmeans.joblib \
   models/tuned_*.joblib
```

---

## 2. Deploy

1. Push the repository to GitHub:

   ```bash
   git remote add origin https://github.com/nishaids/airguard-india.git
   git push -u origin main
   ```

2. Sign in at [share.streamlit.io](https://share.streamlit.io) with the same
   GitHub account.

3. Choose **New app** and set:

   | Field | Value |
   | --- | --- |
   | Repository | `nishaids/airguard-india` |
   | Branch | `main` |
   | Main file path | `app/Home.py` |
   | Python version | 3.10 |

4. Deploy. The first build installs `requirements.txt` and takes a few minutes.

5. Record the live URL so the README and the Review 3 document both cite it:

   ```bash
   python -m src.report.readme --url https://<your-app>.streamlit.app
   python -m src.report.build_docx
   ```

   The URL is stored in `results/deployment.json` and injected into both
   documents, so it is never typed into a report by hand.

---

## 3. Configuration notes

* `app/.streamlit/config.toml` sets the dark theme and disables usage-statistics
  gathering. Streamlit Cloud reads it automatically.
* No secrets are required. The application uses no external API at request time,
  which is why the advisory translations are a static dictionary rather than a
  translation service.
* `@st.cache_resource` deserialises each model once per session and
  `@st.cache_data` caches the tables, so cold start is paid once.

---

## 4. Verifying the deployment

After the app is live, confirm each page renders:

| Page | What to check |
| --- | --- |
| Home | Headline metrics populate; the provenance block shows the licence string |
| Forecast | Change city, cohort, date and language; move a what-if slider |
| City Risk Atlas | All five tabs render; the archetype cards appear |
| Policy Simulator | Select a preset, then move a slider; the tables update |
| Model Insights | All seven tabs render; figures and both cards appear |

Locally, the same guarantee is checked by executing the smoke tests, which
exercise every city against every cohort at four dates each:

```bash
python -m tests.test_smoke
```

---

## 5. Running locally instead

```bash
python -m pip install -r requirements.txt
python run_all.py            # regenerate every artefact
streamlit run app/Home.py
```

The app opens at `http://localhost:8501`.

---

## 6. If a deployment fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| `No deployable regression artefact found` | `models/` was not committed | Commit the joblib artefacts, or add a build step running `python run_all.py` |
| `Model results are not available` on Home | `results/*.json` missing | Commit `results/` |
| Figures missing on Model Insights | `reports/figures/` excluded | Commit the figures directory |
| Build exceeds the memory limit | The full raw CSV was committed | Remove `data/raw/*.csv`; the app does not read them |
| `ModuleNotFoundError: src` | Main file path set incorrectly | It must be `app/Home.py`; the page modules insert the repository root onto `sys.path` themselves |
