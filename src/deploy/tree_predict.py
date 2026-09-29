"""Dependency-free LightGBM tree-ensemble evaluation.

Reproduces ``Booster.predict()`` from the JSON produced by
``Booster.dump_model()`` using nothing but Python arithmetic, so the Vercel
serverless functions never need to import ``lightgbm``, ``scikit-learn`` or
``scipy`` -- see ``src/deploy/export_boosters.py`` for why those are too large
for a 250 MB serverless function bundle.

Every split in these models is a plain numeric threshold (``feature <=
threshold``); none of the training scripts declare a categorical feature, so
LightGBM's bitset-encoded categorical splits are not implemented here and are
never produced by these particular models. ``export_boosters.py --verify``
confirms this module's output is bit-identical to the real ``Booster`` on the
full test set before it is trusted for the live application.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence


def _eval_tree(node: Dict[str, Any], x: List[float]) -> float:
    while "leaf_value" not in node:
        feature_value = x[node["split_feature"]]
        if feature_value != feature_value:  # NaN
            go_left = node.get("default_left", True)
        else:
            go_left = feature_value <= node["threshold"]
        node = node["left_child"] if go_left else node["right_child"]
    return node["leaf_value"]


def _raw_scores(x: List[float], dumped_model: Dict[str, Any]) -> List[float]:
    """Sum every tree's leaf contribution into one raw score per class."""
    num_class = dumped_model.get("num_class", 1)
    scores = [0.0] * num_class
    for tree in dumped_model["tree_info"]:
        class_index = tree["tree_index"] % num_class
        scores[class_index] += _eval_tree(tree["tree_structure"], x)
    return scores


def _softmax(scores: Sequence[float]) -> List[float]:
    top = max(scores)
    exps = [math.exp(s - top) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def _row_to_vector(row: Dict[str, Any], feature_order: List[str]) -> List[float]:
    vector: List[float] = []
    for name in feature_order:
        value = row.get(name)
        vector.append(float("nan") if value is None else float(value))
    return vector


def predict_regression(
    row: Dict[str, Any], dumped_model: Dict[str, Any], feature_order: List[str]
) -> float:
    """Predict a single next-day AQI value."""
    x = _row_to_vector(row, feature_order)
    return _raw_scores(x, dumped_model)[0]


def predict_classification(
    row: Dict[str, Any],
    dumped_model: Dict[str, Any],
    classes: List[str],
    feature_order: List[str],
) -> Dict[str, Any]:
    """Predict a bucket label with the full class-probability distribution."""
    x = _row_to_vector(row, feature_order)
    raw = _raw_scores(x, dumped_model)
    probabilities = _softmax(raw)
    best_index = max(range(len(classes)), key=lambda i: probabilities[i])
    return {
        "label": classes[best_index],
        "confidence": probabilities[best_index],
        "distribution": dict(zip(classes, probabilities)),
    }
