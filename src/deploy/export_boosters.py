"""Export the deployed LightGBM boosters to a dependency-free JSON format.

Why this exists
----------------
A Vercel Python serverless function has a hard 250 MB unzipped-bundle limit.
Measuring the *actual* Linux wheels Vercel installs (not a Windows guess)
showed numpy + pandas + scikit-learn + scipy alone come to 320 MB, and
``lightgbm`` itself unconditionally does ``import scipy.sparse`` at module load
(true in both 3.3.5 and the pinned 4.7.0), so even loading a ``.joblib`` model
through the ``lightgbm`` package pulls in scipy and stays over budget.

The fix is to not need the ``lightgbm`` package, scikit-learn, or scipy on the
serving path at all. LightGBM's ``Booster.dump_model()`` exposes the fitted
tree ensemble as plain JSON (split feature, threshold, children, leaf values),
which is enough to reproduce predictions with nothing but arithmetic. This
script dumps that JSON once, offline; ``src/deploy/tree_predict.py`` evaluates
it at request time using only numpy and pandas.

The dumped predictions are verified bit-for-bit (regression) or exactly
(classification labels) against the original model's own ``.predict()`` before
being trusted -- see ``python -m src.deploy.export_boosters --verify``.

Outputs
-------
``models/deploy/regression_booster.json``
``models/deploy/classification_booster.json``
``models/deploy/classification_classes.json``
``models/deploy/feature_order.json``
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from src import config
from src.models.common import load_task_data

DEPLOY_MODELS_DIR = config.MODELS_DIR / "deploy"


def _dump_booster(booster) -> dict:
    return json.loads(json.dumps(booster.dump_model()))


def export_regression() -> Path:
    model = joblib.load(config.MODELS_DIR / "tuned_regression.joblib")
    booster = model.booster_
    dumped = _dump_booster(booster)
    path = DEPLOY_MODELS_DIR / "regression_booster.json"
    path.write_text(json.dumps(dumped), encoding="utf-8")
    return path


def export_classification() -> Path:
    pipeline = joblib.load(config.MODELS_DIR / "deployment_classification_lightgbm.joblib")
    wrapper = pipeline.named_steps["model"]  # LabelEncodedClassifier
    lgbm_classifier = wrapper.estimator_  # the fitted LGBMClassifier
    booster = lgbm_classifier.booster_
    dumped = _dump_booster(booster)
    path = DEPLOY_MODELS_DIR / "classification_booster.json"
    path.write_text(json.dumps(dumped), encoding="utf-8")

    classes = wrapper.encoder_.classes_.tolist()
    (DEPLOY_MODELS_DIR / "classification_classes.json").write_text(
        json.dumps(classes), encoding="utf-8"
    )
    return path


def export_feature_order() -> Path:
    columns = json.loads((config.PROJECT_ROOT / "data" / "processed" / "feature_columns.json").read_text(encoding="utf-8"))
    order = {
        "regression": columns["regression"],
        "classification": columns["classification"],
    }
    path = DEPLOY_MODELS_DIR / "feature_order.json"
    path.write_text(json.dumps(order), encoding="utf-8")
    return path


def verify() -> None:
    """Confirm the exported JSON reproduces the original model's predictions."""
    from src.deploy.tree_predict import predict_classification, predict_regression

    reg_model = joblib.load(config.MODELS_DIR / "tuned_regression.joblib")
    clf_pipeline = joblib.load(config.MODELS_DIR / "deployment_classification_lightgbm.joblib")

    reg_data = load_task_data("regression")
    clf_data = load_task_data("classification")

    reg_expected = reg_model.predict(reg_data["X_test"])
    reg_booster = json.loads((DEPLOY_MODELS_DIR / "regression_booster.json").read_text(encoding="utf-8"))
    order = json.loads((DEPLOY_MODELS_DIR / "feature_order.json").read_text(encoding="utf-8"))
    reg_got = np.array(
        [predict_regression(row.to_dict(), reg_booster, order["regression"]) for _, row in reg_data["X_test"].iterrows()]
    )
    max_abs_diff = float(np.max(np.abs(reg_expected - reg_got)))
    print(f"regression max abs diff vs original model: {max_abs_diff:.10f}")
    assert max_abs_diff < 1e-6, "regression export does not match the original model"

    clf_expected = clf_pipeline.predict(clf_data["X_test"])
    clf_booster = json.loads((DEPLOY_MODELS_DIR / "classification_booster.json").read_text(encoding="utf-8"))
    classes = json.loads((DEPLOY_MODELS_DIR / "classification_classes.json").read_text(encoding="utf-8"))
    clf_got = np.array(
        [
            predict_classification(row.to_dict(), clf_booster, classes, order["classification"])["label"]
            for _, row in clf_data["X_test"].iterrows()
        ]
    )
    mismatches = int((clf_expected != clf_got).sum())
    print(f"classification label mismatches vs original model: {mismatches} / {len(clf_expected)}")
    assert mismatches == 0, "classification export does not match the original model"
    print("Both exports reproduce the original models exactly.")


def main() -> None:
    config.ensure_dirs()
    DEPLOY_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    r = export_regression()
    c = export_classification()
    f = export_feature_order()
    for p in (r, c, f):
        size_kb = p.stat().st_size / 1024
        print(f"wrote {p.relative_to(config.PROJECT_ROOT)}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    import sys

    main()
    if "--verify" in sys.argv:
        verify()
