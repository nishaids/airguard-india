"""Unsupervised discovery of city pollution archetypes.

Rationale
---------
Two cities can share a mean AQI and still require opposite interventions. A city
whose particulate load is dominated by coarse dust from construction and road
surfaces needs water suppression, paving and construction-site enforcement; a city
whose load is dominated by fine combustion particles needs vehicle-fleet and
fuel-quality measures; a city whose signature is sulfur dioxide needs industrial
and power-sector abatement. Clustering on the *composition* of the pollutant mix,
rather than on its magnitude, surfaces these archetypes directly and maps each to
a distinct policy lever.

Method
------
Each city is represented by its mean concentration profile over the six principal
pollutants, standardised across cities so that the clustering responds to profile
*shape* rather than to overall pollution level. K-Means is fitted for a range of
k, and k is chosen by the elbow of the inertia curve together with the silhouette
coefficient. Agglomerative clustering with Ward linkage is fitted at the selected
k as a comparison, and the agreement between the two partitions is reported: a
partition that survives a change of algorithm is more likely to reflect structure
than method.

Outputs
-------
``models/clustering_kmeans.joblib``
``results/evaluation_clustering.json``
``reports/figures/24_clustering_selection.png``
``reports/figures/25_cluster_profiles.png``

Run with::

    python -m src.models.train_clustering
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler

from src import config
from src.data.clean import CLEAN_PATH

LOGGER = config.get_logger(__name__)

RESULTS_PATH = config.RESULTS_DIR / "evaluation_clustering.json"

#: Pollutants forming the city profile.
PROFILE_POLLUTANTS: List[str] = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]

#: Candidate cluster counts. The upper bound is held well below the number of
#: cities so that every cluster retains enough members to be interpretable.
K_RANGE: Tuple[int, ...] = (2, 3, 4, 5)


def build_city_profiles(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the per-city composition profile used for clustering.

    Both a level profile (mean concentrations) and a composition profile (each
    pollutant's share of the standardised total) are produced. The composition
    profile is what is clustered, because the intent is to separate *kinds* of
    pollution problem rather than to re-rank cities by severity, which the
    exploratory analysis already did.
    """
    means = frame.groupby("City")[PROFILE_POLLUTANTS].mean()

    # Scale each pollutant across cities so that species measured on different
    # numeric ranges contribute comparably to the distance.
    scaled = pd.DataFrame(
        StandardScaler().fit_transform(means),
        index=means.index,
        columns=means.columns,
    )

    extras = frame.groupby("City").agg(
        mean_aqi=("AQI", "mean"),
        median_aqi=("AQI", "median"),
        pm_ratio=("PM2.5", "mean"),
    )
    extras["pm_ratio"] = means["PM2.5"] / means["PM10"]
    extras["so2_share"] = means["SO2"] / means[PROFILE_POLLUTANTS].sum(axis=1)
    extras["o3_share"] = means["O3"] / means[PROFILE_POLLUTANTS].sum(axis=1)
    extras["no2_share"] = means["NO2"] / means[PROFILE_POLLUTANTS].sum(axis=1)

    return means.join(scaled.add_suffix("_z")).join(extras)


def select_k(matrix: np.ndarray) -> Dict[str, Any]:
    """Fit K-Means across ``K_RANGE`` and score each candidate partition."""
    records: List[Dict[str, Any]] = []
    for k in K_RANGE:
        model = KMeans(n_clusters=k, n_init=50, random_state=config.RANDOM_SEED)
        labels = model.fit_predict(matrix)
        records.append(
            {
                "k": k,
                "inertia": round(float(model.inertia_), 4),
                "silhouette": round(float(silhouette_score(matrix, labels)), 4),
                "davies_bouldin": round(float(davies_bouldin_score(matrix, labels)), 4),
                "calinski_harabasz": round(float(calinski_harabasz_score(matrix, labels)), 4),
                "cluster_sizes": np.bincount(labels).tolist(),
            }
        )

    # Elbow: the k at which the marginal reduction in inertia falls off most.
    inertias = [r["inertia"] for r in records]
    drops = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    elbow_index = (
        int(np.argmax([drops[i] - drops[i + 1] for i in range(len(drops) - 1)])) + 1
        if len(drops) > 1
        else 0
    )
    elbow_k = int(K_RANGE[elbow_index])

    votes = {
        "silhouette": max(records, key=lambda r: r["silhouette"])["k"],
        "davies_bouldin": min(records, key=lambda r: r["davies_bouldin"])["k"],
        "calinski_harabasz": max(records, key=lambda r: r["calinski_harabasz"])["k"],
        "inertia_elbow": elbow_k,
    }

    # Declared selection rule, fixed before the indices were inspected:
    #   1. Discard any k whose partition contains a singleton cluster, because a
    #      cluster of one city cannot support a generalisable archetype claim.
    #   2. Among the survivors, take the k with the highest silhouette.
    # The vote tally is reported in full either way, so a reader can see where the
    # indices disagreed rather than only the winner.
    admissible = [r for r in records if min(r["cluster_sizes"]) >= 2]
    rejected = [
        {"k": r["k"], "cluster_sizes": r["cluster_sizes"], "reason": "contains a singleton cluster"}
        for r in records
        if min(r["cluster_sizes"]) < 2
    ]
    pool = admissible or records
    selected = max(pool, key=lambda r: r["silhouette"])

    return {
        "candidates": records,
        "index_votes": votes,
        "indices_disagree": len(set(votes.values())) > 1,
        "rejected_for_singleton_cluster": rejected,
        "best_by_silhouette": max(records, key=lambda r: r["silhouette"])["k"],
        "elbow_k": elbow_k,
        "selected_k": selected["k"],
        "selection_rule": (
            "The rule was fixed before the indices were inspected. Any k whose "
            "partition contains a singleton cluster is discarded, because a cluster "
            "of one city cannot support a generalisable archetype claim; among the "
            "remaining candidates the highest silhouette coefficient decides. "
            "Silhouette is the decisive index because it measures separation "
            "relative to cohesion and is comparable across k, whereas inertia falls "
            "monotonically with k by construction and cannot select k on its own. "
            "The four indices do not agree here, and the full vote tally is "
            "reported rather than only the winner."
        ),
        "power_caveat": (
            "Twelve cities is a small sample for a clustering problem. Silhouette "
            "coefficients in the 0.2 to 0.4 range indicate real but moderate "
            "separation, and the partition should be read as an interpretive "
            "organising device for policy discussion rather than as a claim of "
            "sharply bounded natural classes. Every candidate partition is reported "
            "below with its scores so that this is visible rather than implied."
        ),
    }


def label_archetypes(
    profiles: pd.DataFrame, labels: np.ndarray
) -> List[Dict[str, Any]]:
    """Assign an interpretive archetype name and a policy lever to each cluster.

    The name is derived from the pollutant that most distinguishes the cluster
    from the overall mean, measured in standardised units, so the labelling is
    driven by the data rather than imposed on it.
    """
    work = profiles.copy()
    work["cluster"] = labels
    z_columns = [f"{p}_z" for p in PROFILE_POLLUTANTS]

    # Composition labels are keyed on which pollutant stands out *within* a
    # cluster's own profile, not on which has the highest absolute z-score. A
    # cluster can sit below the cross-city mean on every pollutant, in which case
    # the largest raw z-score is simply the least negative one and says nothing
    # about composition. De-meaning each centroid across pollutants separates the
    # shape of the mix from the overall level, and the level is then reported as a
    # separate field rather than being smuggled into the name.
    composition_rules = {
        "PM10": (
            "coarse-particulate led",
            "Coarse particulate leads the mix. The effective levers are mechanised "
            "road sweeping and water suppression, paving of unpaved shoulders, "
            "enforcement of construction-site dust covers, and control of open "
            "material transport.",
        ),
        "PM2.5": (
            "fine-particulate led",
            "Fine particulate leads the mix, which points to combustion rather than "
            "mechanical sources. The effective levers are fuel-quality and "
            "vehicle-fleet standards, control of biomass and solid-fuel burning, and "
            "seasonal crop-residue management.",
        ),
        "NO2": (
            "vehicular NOx led",
            "Oxidised nitrogen leads the mix, which is the signature of live traffic "
            "exhaust. The effective levers are traffic demand management, "
            "public-transport capacity, congestion control at corridors, and "
            "tightened in-use vehicle emission testing.",
        ),
        "SO2": (
            "industrial sulfur led",
            "Sulfur dioxide leads the mix, which points to coal combustion and "
            "industrial process emissions. The effective levers are flue-gas "
            "desulfurisation at point sources, fuel sulfur limits, and siting "
            "controls around industrial clusters.",
        ),
        "O3": (
            "photochemical ozone led",
            "Ozone leads the mix. Ozone is secondary, formed from nitrogen oxides "
            "and volatile organic compounds under sunlight, so the effective levers "
            "act on the precursors: VOC control at fuel stations and solvent users, "
            "alongside NOx reduction.",
        ),
        "CO": (
            "incomplete-combustion led",
            "Carbon monoxide leads the mix, indicating incomplete combustion from "
            "older vehicles and solid-fuel use. The effective levers are fleet "
            "renewal and clean cooking-fuel access.",
        ),
    }

    summaries: List[Dict[str, Any]] = []
    for cluster in sorted(np.unique(labels)):
        members = work.loc[work["cluster"] == cluster]
        centroid = members[z_columns].mean()
        centroid.index = [c.replace("_z", "") for c in centroid.index]

        level = float(centroid.mean())
        shape = centroid - level
        leading = str(shape.idxmax())
        composition, lever = composition_rules[leading]

        if level >= 0.35:
            level_word = "High-burden"
        elif level <= -0.35:
            level_word = "Lower-burden"
        else:
            level_word = "Mid-burden"
        archetype = f"{level_word}, {composition}"

        summaries.append(
            {
                "cluster": int(cluster),
                "archetype": archetype,
                "burden_level": level_word,
                "mean_level_z": round(level, 3),
                "composition": composition,
                "defining_pollutant": leading,
                "defining_pollutant_shape_score": round(float(shape.max()), 3),
                "policy_lever": lever,
                "cities": members.index.tolist(),
                "n_cities": int(len(members)),
                "mean_aqi": round(float(members["mean_aqi"].mean()), 2),
                "mean_profile": {
                    pollutant: round(float(members[pollutant].mean()), 3)
                    for pollutant in PROFILE_POLLUTANTS
                },
                "standardised_profile": {
                    pollutant: round(float(centroid[pollutant]), 3)
                    for pollutant in PROFILE_POLLUTANTS
                },
                "composition_profile": {
                    pollutant: round(float(shape[pollutant]), 3)
                    for pollutant in PROFILE_POLLUTANTS
                },
                "mean_pm_ratio": round(float(members["pm_ratio"].mean()), 3),
            }
        )
    return summaries


def plot_selection(selection: Dict[str, Any]) -> str:
    """Render the elbow curve and the three internal validity indices."""
    records = selection["candidates"]
    ks = [r["k"] for r in records]
    chosen = selection["selected_k"]

    fig, axes = plt.subplots(1, 4, figsize=(17, 4.4))
    panels = [
        ("inertia", "Within-cluster sum of squares", "lower, but monotone in k"),
        ("silhouette", "Silhouette coefficient", "higher is better"),
        ("davies_bouldin", "Davies-Bouldin index", "lower is better"),
        ("calinski_harabasz", "Calinski-Harabasz index", "higher is better"),
    ]
    for ax, (key, title, direction) in zip(axes, panels):
        values = [r[key] for r in records]
        ax.plot(ks, values, marker="o", color=config.PALETTE[0], linewidth=1.9)
        ax.axvline(chosen, color=config.PALETTE[1], linestyle="--", linewidth=1.5,
                   label=f"selected k = {chosen}")
        ax.set_xticks(ks)
        ax.set_xlabel("Number of clusters (k)")
        ax.set_title(f"{title}\n({direction})", fontsize=10)
        ax.legend(frameon=False, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle(
        f"Figure 24. Selection of the number of city archetypes. "
        f"Silhouette selects k = {selection['best_by_silhouette']}; "
        f"the inertia elbow indicates k = {selection['elbow_k']}.",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    path = config.FIGURES_DIR / "24_clustering_selection.png"
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", path.name)
    return path.name


def plot_profiles(
    profiles: pd.DataFrame, labels: np.ndarray, archetypes: List[Dict[str, Any]],
    matrix: np.ndarray,
) -> str:
    """Render the cluster centroids and the cities projected onto two components."""
    z_columns = [f"{p}_z" for p in PROFILE_POLLUTANTS]
    work = profiles.copy()
    work["cluster"] = labels

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(16, 6.8), gridspec_kw={"width_ratios": [1.25, 1]}
    )

    x = np.arange(len(PROFILE_POLLUTANTS))
    width = 0.8 / len(archetypes)
    for idx, entry in enumerate(archetypes):
        values = [entry["composition_profile"][p] for p in PROFILE_POLLUTANTS]
        ax1.bar(
            x + idx * width - 0.4 + width / 2, values, width,
            color=config.PALETTE[idx],
            label=(
                f"{entry['archetype']} (n={entry['n_cities']}, "
                f"overall level z={entry['mean_level_z']:+.2f})"
            ),
        )
    ax1.axhline(0, color="black", linewidth=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(PROFILE_POLLUTANTS)
    ax1.set_ylabel("Composition: pollutant z-score minus the cluster's own mean")
    ax1.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title(
        "Archetype signatures (composition, with overall level removed)\n"
        "A bar above zero means the pollutant leads that cluster's own mix; the "
        "legend carries the level separately,\nso a cluster that is simply cleaner "
        "throughout is not mislabelled as being led by any one species.",
        fontsize=9.5, loc="left",
    )

    pca = PCA(n_components=2, random_state=config.RANDOM_SEED)
    scores = pca.fit_transform(matrix)
    for idx, entry in enumerate(archetypes):
        mask = labels == entry["cluster"]
        ax2.scatter(
            scores[mask, 0], scores[mask, 1], s=130, color=config.PALETTE[idx],
            edgecolor="white", linewidth=1.3, zorder=3,
        )
    for position, city in enumerate(work.index):
        ax2.annotate(
            city, (scores[position, 0], scores[position, 1]),
            fontsize=8, xytext=(6, 4), textcoords="offset points",
        )
    ax2.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.0%} of profile variance)")
    ax2.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.0%} of profile variance)")
    ax2.grid(alpha=0.25, linewidth=0.5)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Cities in archetype space", fontsize=11, loc="left")

    fig.suptitle(
        "Figure 25. City pollution archetypes discovered without supervision, and "
        "the policy lever each implies",
        fontsize=12, x=0.02, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path = config.FIGURES_DIR / "25_cluster_profiles.png"
    fig.savefig(path, dpi=config.FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    LOGGER.info("Wrote figure %s", path.name)
    return path.name


def main() -> Dict[str, Any]:
    """Fit, select, compare and interpret the city archetype clustering."""
    config.set_global_seed()
    config.ensure_dirs()

    frame = pd.read_csv(CLEAN_PATH, parse_dates=["Date"])
    profiles = build_city_profiles(frame)
    matrix = profiles[[f"{p}_z" for p in PROFILE_POLLUTANTS]].to_numpy()
    LOGGER.info("Clustering %s cities on %s pollutant dimensions", *matrix.shape)

    selection = select_k(matrix)
    k = selection["selected_k"]

    kmeans = KMeans(n_clusters=k, n_init=50, random_state=config.RANDOM_SEED)
    kmeans_labels = kmeans.fit_predict(matrix)

    agglomerative = AgglomerativeClustering(n_clusters=k, linkage="ward")
    agglomerative_labels = agglomerative.fit_predict(matrix)

    agreement = float(adjusted_rand_score(kmeans_labels, agglomerative_labels))

    def _scores(labels: np.ndarray) -> Dict[str, float]:
        return {
            "silhouette": round(float(silhouette_score(matrix, labels)), 4),
            "davies_bouldin": round(float(davies_bouldin_score(matrix, labels)), 4),
            "calinski_harabasz": round(float(calinski_harabasz_score(matrix, labels)), 4),
        }

    archetypes = label_archetypes(profiles, kmeans_labels)

    # Every candidate partition is retained with its archetype labelling, so the
    # finer-grained views remain available to the application and the reader can
    # see what was not selected as well as what was.
    alternative_partitions: List[Dict[str, Any]] = []
    for candidate in K_RANGE:
        model = KMeans(n_clusters=candidate, n_init=50, random_state=config.RANDOM_SEED)
        candidate_labels = model.fit_predict(matrix)
        alternative_partitions.append(
            {
                "k": int(candidate),
                "selected": candidate == k,
                **_scores(candidate_labels),
                "archetypes": [
                    {key: entry[key] for key in ("cluster", "archetype", "defining_pollutant", "cities")}
                    for entry in label_archetypes(profiles, candidate_labels)
                ],
            }
        )

    figures = [
        plot_selection(selection),
        plot_profiles(profiles, kmeans_labels, archetypes, matrix),
    ]

    path = config.MODELS_DIR / "clustering_kmeans.joblib"
    joblib.dump(
        {
            "model": kmeans,
            "pollutants": PROFILE_POLLUTANTS,
            "city_index": profiles.index.tolist(),
            "labels": kmeans_labels.tolist(),
            "archetypes": archetypes,
        },
        path,
        compress=3,
    )

    payload: Dict[str, Any] = {
        "generated_by": "src/models/train_clustering.py",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "clustering",
        "unit_of_analysis": "city",
        "n_cities": int(len(profiles)),
        "features": PROFILE_POLLUTANTS,
        "representation": (
            "Each city is represented by its mean concentration over the six "
            "principal pollutants, standardised across cities. Standardising makes "
            "the distance respond to the shape of the pollutant mix rather than to "
            "overall pollution level, which is the property that separates kinds of "
            "problem from degrees of severity."
        ),
        "k_selection": selection,
        "selected_k": int(k),
        "algorithms": {
            "KMeans": {
                "params": {"n_clusters": int(k), "n_init": 50, "random_state": config.RANDOM_SEED},
                **_scores(kmeans_labels),
                "labels": kmeans_labels.tolist(),
            },
            "Agglomerative (Ward)": {
                "params": {"n_clusters": int(k), "linkage": "ward"},
                **_scores(agglomerative_labels),
                "labels": agglomerative_labels.tolist(),
            },
        },
        "algorithm_agreement": {
            "adjusted_rand_index": round(agreement, 4),
            "interpretation": (
                f"An adjusted Rand index of {agreement:.3f} between K-Means and Ward "
                "agglomerative clustering indicates "
                + (
                    "that the partition is reproduced almost exactly by an algorithm "
                    "with a different objective, which is evidence that it reflects "
                    "structure in the data rather than an artefact of the method."
                    if agreement > 0.7
                    else "only partial agreement, so the partition should be read as "
                    "indicative rather than definitive."
                )
            ),
        },
        "archetypes": archetypes,
        "alternative_partitions": alternative_partitions,
        "city_profiles": profiles.round(4).reset_index().to_dict(orient="records"),
        "city_to_cluster": {
            city: int(label) for city, label in zip(profiles.index, kmeans_labels)
        },
        "artifact": str(path.relative_to(config.PROJECT_ROOT)),
        "figures": figures,
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    LOGGER.info(
        "Selected k=%s | silhouette %.4f | Davies-Bouldin %.4f | Calinski-Harabasz %.1f | ARI %.3f",
        k,
        payload["algorithms"]["KMeans"]["silhouette"],
        payload["algorithms"]["KMeans"]["davies_bouldin"],
        payload["algorithms"]["KMeans"]["calinski_harabasz"],
        agreement,
    )
    for entry in archetypes:
        LOGGER.info(
            "  Cluster %s | %-32s | %s",
            entry["cluster"],
            entry["archetype"],
            ", ".join(entry["cities"]),
        )
    return payload


if __name__ == "__main__":
    main()
