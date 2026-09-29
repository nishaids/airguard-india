# Deploying to Vercel

This is the second deployment target alongside Streamlit Community Cloud
(`DEPLOY.md`). It serves the same application as a Next.js frontend with two
Python serverless functions, because Vercel cannot run a long-lived Streamlit
process — see the reasoning below if you want it, or skip to **Steps**.

## Why this isn't just `streamlit run` on Vercel

Vercel only runs short-lived serverless functions, not a persistent process
holding a WebSocket connection open, which is what Streamlit needs. The
application was rebuilt as a static Next.js site (everything read-only: Home,
City Risk Atlas, Model Insights) plus two live Python functions for the two
interactive tools (Forecast, Policy Simulator).

## Why the classifier differs from the Streamlit deployment

A Vercel Python function has a **250 MB unzipped limit**. Measuring the actual
Linux wheels Vercel installs (not a Windows guess) showed numpy + pandas +
scikit-learn + scipy alone come to **320 MB**, and `lightgbm` itself
unconditionally does `import scipy.sparse` at module load — true in every
version checked, including the pinned 4.7.0 — so even loading a tuned
LightGBM model through the `lightgbm` package pulls in scipy and stays over
budget. XGBoost alone is 145 MB on top of that.

The fix: `src/deploy/export_boosters.py` dumps both tuned models' trees to
plain JSON (`Booster.dump_model()`), and `src/deploy/tree_predict.py`
re-implements prediction as pure arithmetic over that JSON — no `lightgbm`,
`scikit-learn`, or `scipy` needed at serving time. This was verified to
reproduce the original models **exactly**: 0.0 max absolute difference on the
regression test set (4,397 rows), 0 label mismatches on classification.

The classification model itself also changed for this deployment.
XGBoost + SMOTE remains the model reported everywhere and the model the
Streamlit app deploys (macro-F1 0.7411). For Vercel, `src/deploy/fit_deployment_classifier.py`
fits the identical SMOTE pipeline with **LightGBM** in place of XGBoost
(macro-F1 0.7145 — a measured gap of −0.0266, recorded in
`results/deployment_classifier.json` and disclosed in the app itself, in
Model Insights → Comparison). The regression model is unchanged: the same
tuned LightGBM model deployed everywhere.

Measured final bundle sizes (real `manylinux2014` wheels + actual data files):

| Function | Contents | Size |
| --- | --- | --- |
| `api/forecast.py` | numpy + pandas + two booster JSONs + `features_full.csv` | **≈199 MB** |
| `api/policy_simulate.py` | numpy + pandas + `city_day_clean.csv` | **≈168 MB** |

Both comfortably under the 250 MB cap.

## What's static vs. live

Everything in `webapp/public/data/*.json` and `webapp/public/figures/*.png` is
a copy of `results/*.json` and `reports/figures/*.png`, produced offline by
`python -m src.deploy.build_static_bundle` (run this again any time the
pipeline output changes, then redeploy). The two ranked tables the City Risk
Atlas page needs (the per-city risk table, the seasonal heatmap) are computed
in that same script from `data/processed/features_full.csv`, reproducing
exactly what `app/pages/2_City_Risk_Atlas.py` computes live in Streamlit.

Only Forecast and Policy Simulator are live Python functions, because they
depend on user input (city, date, cohort, what-if sliders, reduction
sliders).

## Running it locally

Two processes, because `next dev` does not run the Python functions and
`vercel dev` cannot start them on a path containing a space (see the last
section). In two terminals, from `webapp/`:

```bash
npm run dev:api
```

```bash
npm run dev
```

Then open <http://localhost:3000>. `next.config.mjs` rewrites `/api/*` to the
Python server on port 8787 **in development only**, so the whole application —
including the Forecast and Policy Simulator — works locally exactly as it will
in production. `dev_api_server.py` calls the same `handle()` functions the
deployed Vercel handlers call, so the two cannot drift apart. In a production
build no rewrite is emitted and Vercel routes `/api/*` to the real functions.

## Steps

1. **Push this repository to GitHub** (see `DEPLOY.md` for the git remote
   setup if not done already).
2. On [vercel.com](https://vercel.com), **New Project** → import the repo.
3. **Root Directory**: set it to `webapp`.
4. In the same import screen (or afterwards under Project Settings →
   General), enable **"Include source files outside of the Root Directory in
   the Build"**. This is required: the Python functions import `src/` and
   read `data/`, `results/` and `models/deploy/` from outside `webapp/`.
5. Framework preset should auto-detect as Next.js. Leave the build command as
   `next build`.
6. Deploy.

No environment variables are needed.

## Regenerating the static bundle after a pipeline change

```bash
python -m src.deploy.build_static_bundle
python -m src.deploy.export_boosters --verify
```

The second command re-exports the tree JSON from whatever is currently in
`models/tuned_regression.joblib` and `models/deployment_classification_lightgbm.joblib`,
and refuses (via `assert`) to finish if the exported predictions stop matching
the real models. Commit the changed files under `webapp/public/` and
`models/deploy/`, then push; Vercel redeploys automatically.

If the classifier itself is retrained, re-run
`python -m src.deploy.fit_deployment_classifier` first to refit the
LightGBM + SMOTE deployment model, then the two commands above.

## What was and wasn't tested before you deploy

Verified directly, without needing a live server:

- The booster export is bit-exact against the real models (`export_boosters.py --verify`).
- `forecast()` and `simulate()` (the business logic both API functions call)
  were run directly in Python and produce correct results.
- The actual `handler` classes in `api/forecast.py` and `api/policy_simulate.py`
  were exercised directly (constructing the request/response objects Python's
  own `http.server` machinery would build) and returned correct HTTP 200
  responses with correct payloads.
- `npm run build` completes cleanly with no errors.
- The real installed size of every dependency was measured from actual Linux
  wheels, not estimated.

**Verified locally since**: the full request path now runs end to end against `dev_api_server.py`, which calls the same `handle()` functions the Vercel handlers call. **Still not verified**: the request over an actual HTTP connection
through Vercel's own Python runtime, and the `includeFiles` bundling in
`webapp/vercel.json`. Local `vercel dev` could not be used to close this gap
on this machine — its Python-function bootstrap invokes `uv` through a
command string that isn't quoted for a path containing a space, and this
Windows account's home directory is `C:\Users\Nishanth R\...`, so `vercel dev`
crashes on the space before the function ever runs. This is a Vercel CLI bug
on this specific machine, not a defect in this code. If you deploy from a
machine or account without a space in the path, `vercel dev` should work
directly.

**After deploying**, check Vercel's function logs for `api/forecast` and
`api/policy_simulate` on the first real request. If either 500s, the most
likely cause is `includeFiles`: open the function's log, and if it's a
`FileNotFoundError` for something under `data/`, `models/deploy/` or `results/`,
widen the matching glob in `webapp/vercel.json`.
