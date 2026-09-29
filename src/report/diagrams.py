"""Schematic figures for the review documents: the pipeline and the project plan.

These are the only figures in the project that depict a design rather than a
measurement, so they are generated here rather than in an analysis module. Both
are drawn with matplotlib at the project DPI so that they match every other
figure in the reports.

Outputs
-------
``reports/figures/39_pipeline_diagram.png``
``reports/figures/40_project_gantt.png``

Run with::

    python -m src.report.diagrams
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from src import config

LOGGER = config.get_logger(__name__)

#: Pipeline stages grouped into the five phases the reports describe.
PIPELINE: List[Tuple[str, str, List[str]]] = [
    (
        "Acquisition",
        config.PALETTE[0],
        [
            "kagglehub download\n(fallback: manual archive)",
            "SHA-256 checksums\nlicence scraped live",
            "PROVENANCE.json\nschema proof figure",
        ],
    ),
    (
        "Quality and cleaning",
        config.PALETTE[1],
        [
            "Quality assessment\nnulls, duplicates, outliers",
            "City retention gates\n80% complete, 730+ days",
            "Artefact rule\nevents protected",
            "Imputation bake-off\ncausal strategies only",
        ],
    ),
    (
        "Feature engineering",
        config.PALETTE[2],
        [
            "Temporal and cyclical\nevent flags",
            "Per-city lags\nand rolling windows",
            "Pollutant ratios\nsource proxies",
            "Health Advisory Index\nseven cohorts",
            "Leakage-safe encoding\ntrain-only statistics",
        ],
    ),
    (
        "Modelling",
        config.PALETTE[3],
        [
            "Regression\n5 families + baseline",
            "Classification\n6 families + SMOTE",
            "Clustering\narchetype discovery",
            "TimeSeriesSplit CV\nrandomised search",
        ],
    ),
    (
        "Delivery",
        config.PALETTE[4],
        [
            "SHAP\nglobal and local",
            "Policy simulator\ncounterfactual re-scoring",
            "Streamlit application\nfour pages, three languages",
            "Reports and cards\ngenerated from results",
        ],
    ),
]

#: Six-week plan: (task, start week, duration in weeks, phase index).
GANTT: List[Tuple[str, float, float, int]] = [
    ("Problem framing and literature", 0.0, 1.0, 0),
    ("Dataset acquisition and provenance", 0.5, 0.8, 0),
    ("Project charter and planning", 0.8, 0.7, 0),
    ("Data quality assessment", 1.0, 0.8, 1),
    ("Cleaning and imputation study", 1.5, 1.0, 1),
    ("Feature engineering", 2.0, 1.0, 2),
    ("Health Advisory Index design", 2.0, 1.2, 2),
    ("Exploratory data analysis", 2.5, 1.0, 1),
    ("Regression and classification", 3.2, 1.2, 3),
    ("Clustering and archetypes", 3.5, 0.6, 3),
    ("Hyperparameter optimisation", 4.0, 0.8, 3),
    ("Explainability and error analysis", 4.2, 0.8, 3),
    ("Policy simulator", 4.4, 0.7, 4),
    ("Streamlit application", 4.5, 1.2, 4),
    ("Reports, cards and deployment", 5.2, 0.8, 4),
]

MILESTONES: List[Tuple[str, float]] = [
    ("Review 1\nProblem and dataset", 1.6),
    ("Review 2\nPreprocessing and EDA", 3.4),
    ("Review 3\nModelling and product", 6.0),
]


def _save(fig: plt.Figure, name: str) -> str:
    path = config.FIGURES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", name)
    return name


def plot_pipeline() -> str:
    """Draw the end-to-end methodology diagram."""
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    n_phases = len(PIPELINE)
    column_width = 100.0 / n_phases
    box_width = column_width * 0.88
    top = 88.0

    for index, (phase, colour, steps) in enumerate(PIPELINE):
        x_centre = column_width * (index + 0.5)

        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x_centre - box_width / 2, top),
                box_width, 7,
                boxstyle="round,pad=0.4",
                facecolor=colour, edgecolor="none",
            )
        )
        ax.text(
            x_centre, top + 3.5, f"{index + 1}. {phase}",
            ha="center", va="center", fontsize=10.5, fontweight="bold", color="white",
        )

        box_height = 9.5
        gap = 3.0
        y = top - gap - box_height
        for step in steps:
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (x_centre - box_width / 2, y),
                    box_width, box_height,
                    boxstyle="round,pad=0.3",
                    facecolor="white", edgecolor=colour, linewidth=1.8,
                )
            )
            ax.text(
                x_centre, y + box_height / 2, step,
                ha="center", va="center", fontsize=8.6, color="#222222", linespacing=1.4,
            )
            y -= box_height + gap

        if index < n_phases - 1:
            ax.annotate(
                "", xy=(column_width * (index + 1) + box_width * 0.06, top + 3.5),
                xytext=(x_centre + box_width / 2, top + 3.5),
                arrowprops={"arrowstyle": "-|>", "linewidth": 2.4, "color": "#555555"},
            )

    ax.add_patch(
        mpatches.FancyBboxPatch(
            (2, 2), 96, 11, boxstyle="round,pad=0.5",
            facecolor="#F4F6F8", edgecolor="#BBBBBB", linewidth=1.2,
        )
    )
    ax.text(
        50, 10.4,
        "Leakage controls applied throughout",
        ha="center", va="center", fontsize=11, fontweight="bold", color="#222222",
    )
    ax.text(
        50, 5.8,
        "Fixed calendar train/test boundary, never shuffled   •   TimeSeriesSplit "
        "cross-validation   •   per-city lags via groupby   •   imputation, scaling "
        "and encoding fitted on training rows only\n"
        "Immutable raw layer   •   global seed 42   •   pinned dependencies   •   "
        "every reported number generated by executed code",
        ha="center", va="center", fontsize=8.8, color="#444444", linespacing=1.6,
    )

    ax.set_title(
        "Figure. AirGuard India end-to-end methodology",
        fontsize=14, loc="left", pad=16,
    )
    return _save(fig, "39_pipeline_diagram.png")


def plot_gantt() -> str:
    """Draw the six-week project plan with its review milestones."""
    fig, ax = plt.subplots(figsize=(14, 8))

    phase_names = [p[0] for p in PIPELINE]
    for index, (task, start, duration, phase) in enumerate(GANTT):
        y = len(GANTT) - index - 1
        ax.barh(
            y, duration, left=start, height=0.62,
            color=PIPELINE[phase][1], edgecolor="white", linewidth=1.2,
        )
        ax.text(
            start + duration + 0.08, y, f"{duration:.1f}w",
            va="center", fontsize=8, color="#555555",
        )

    ax.set_yticks(range(len(GANTT)))
    ax.set_yticklabels([t[0] for t in GANTT][::-1], fontsize=9.5)
    ax.set_xlim(0, 6.6)
    ax.set_xticks(range(7))
    ax.set_xticklabels([f"Week {w}" for w in range(7)], fontsize=9.5)
    ax.set_xlabel("Project timeline")
    ax.grid(axis="x", alpha=0.3, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)

    for label, week in MILESTONES:
        ax.axvline(week, color="#333333", linestyle="--", linewidth=1.6)
        ax.text(
            week, len(GANTT) - 0.1, label,
            ha="center", va="bottom", fontsize=8.6, fontweight="bold",
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#FFF6CC",
                  "edgecolor": "#CCB877"},
        )

    handles = [
        mpatches.Patch(color=PIPELINE[i][1], label=phase_names[i])
        for i in range(len(phase_names))
    ]
    ax.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.17),
        ncol=len(handles), frameon=False, fontsize=9,
    )

    ax.set_title(
        "Figure. Six-week project plan, with the three review milestones",
        fontsize=13, loc="left", pad=28,
    )
    fig.tight_layout()
    return _save(fig, "40_project_gantt.png")


def main() -> Dict[str, str]:
    """Generate both schematic figures."""
    config.ensure_dirs()
    return {"pipeline": plot_pipeline(), "gantt": plot_gantt()}


if __name__ == "__main__":
    main()
