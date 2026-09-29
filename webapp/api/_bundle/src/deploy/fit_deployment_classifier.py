"""Fit a size-constrained classifier for the serverless (Vercel) deployment.

The academic model comparison in ``src/models/train_classification.py`` selects
XGBoost + SMOTE as the best classifier by macro-F1, and that selection is
unchanged: it remains the model reported in the reviews and the model deployed
by the Streamlit application.

A Vercel Python serverless function has a hard 250 MB unzipped-bundle limit per
function. The installed ``xgboost`` package alone is approximately 145 MB;
combined with numpy, pandas and scikit-learn it exceeds that limit even in a
function that imports nothing else. LightGBM's installed footprint is
approximately 5 MB, which fits comfortably.

This script fits the same SMOTE-augmented pipeline with a LightGBM classifier
in place of XGBoost, using the identical time-ordered split, feature set and
evaluation metrics as the academic comparison, so its numbers are measured on
the same basis rather than assumed to be close. Its result is saved separately
from ``results/evaluation_classification.json`` and never substituted into that
file: it is documented as what serves the Vercel deployment specifically, with
its own measured metrics disclosed alongside the reported model's.

Run with::

    python -m src.deploy.fit_deployment_classifier
"""

from __future__ import annotations

import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib

from src import config
from src.models.common import LabelEncodedClassifier, classification_metrics, load_task_data

OUTPUT_MODEL_PATH = config.MODELS_DIR / "deployment_classification_lightgbm.joblib"
OUTPUT_REPORT_PATH = config.RESULTS_DIR / "deployment_classifier.json"


def main() -> dict:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
    from lightgbm import LGBMClassifier

    data = load_task_data("classification")

    pipeline = ImbPipeline(
        [
            ("smote", SMOTE(random_state=config.RANDOM_SEED, k_neighbors=5)),
            (
                "model",
                LabelEncodedClassifier(
                    LGBMClassifier(
                        n_estimators=400,
                        learning_rate=0.05,
                        max_depth=6,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        n_jobs=-1,
                        random_state=config.RANDOM_SEED,
                        verbose=-1,
                    )
                ),
            ),
        ]
    )

    start = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipeline.fit(data["X_train"], data["y_train"])
        test_pred = pipeline.predict(data["X_test"])
    fit_seconds = time.perf_counter() - start

    metrics = classification_metrics(data["y_test"].to_numpy(), test_pred)

    reference_path = config.RESULTS_DIR / "evaluation_classification.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8")) if reference_path.exists() else {}
    reference_metrics = reference.get("best_test_metrics", {})

    joblib.dump(pipeline, OUTPUT_MODEL_PATH)
    model_size_mb = round(OUTPUT_MODEL_PATH.stat().st_size / 1e6, 2)

    report = {
        "generated_by": "src/deploy/fit_deployment_classifier.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Serves the Vercel serverless deployment only. XGBoost + SMOTE remains "
            "the reported best model in every review document and remains what the "
            "Streamlit application deploys; this LightGBM + SMOTE pipeline exists "
            "because XGBoost's installed size (~145 MB) exceeds Vercel's 250 MB "
            "per-function limit once combined with numpy, pandas and scikit-learn."
        ),
        "model": "LightGBM + SMOTE",
        "reference_model": reference.get("best_model", "XGBoost + SMOTE"),
        "same_split_same_features": True,
        "n_features": int(data["X_train"].shape[1]),
        "fit_seconds": round(fit_seconds, 2),
        "artifact": str(OUTPUT_MODEL_PATH.relative_to(config.PROJECT_ROOT)),
        "artifact_size_mb": model_size_mb,
        "test_metrics": metrics,
        "reference_test_metrics": reference_metrics,
        "macro_f1_gap_vs_reference": (
            round(metrics["macro_f1"] - reference_metrics["macro_f1"], 4)
            if "macro_f1" in reference_metrics
            else None
        ),
    }
    OUTPUT_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result["test_metrics"], indent=2))
    print(f"macro_f1 gap vs reference: {result['macro_f1_gap_vs_reference']}")
    print(f"artifact size: {result['artifact_size_mb']} MB -> {result['artifact']}")
