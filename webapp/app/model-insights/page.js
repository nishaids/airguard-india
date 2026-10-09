"use client";

import { useEffect, useState } from "react";
import { Metric, Banner, Table, Figure, Loading, Markdown, SectionTitle, Badge } from "../components/ui";

const TABS = [
  "Comparison",
  "Confusion and errors",
  "Explainability",
  "Tuning",
  "Leakage controls",
  "Metric glossary",
  "Data and model cards",
];

const METRIC_GLOSSARY = {
  MAE: "Mean absolute error. The average size of the miss, in AQI points. An MAE of 15 means the forecast is typically 15 AQI points away from what happened.",
  RMSE: "Root mean squared error. Like MAE, but large misses count disproportionately, so it is sensitive to a handful of extreme days.",
  "R-squared": "The share of the variation in next-day AQI that the model accounts for. 1.0 is perfect; 0 is no better than always predicting the average.",
  MAPE: "Mean absolute percentage error. The typical miss expressed as a percentage of the true value.",
  Accuracy: "The share of days whose band was predicted exactly right. Misleading on its own here, because the bands are unevenly common.",
  "Macro F1": "The average F1 score across all six bands, giving each band equal weight no matter how rare. This is the primary metric, chosen so a model cannot score well by ignoring the rare Severe band.",
  "Weighted F1": "The same average, but weighted by how common each band is. Closer to accuracy in behaviour.",
  "Balanced accuracy": "The average recall across bands. Another way of refusing to let common bands dominate the score.",
  "Cohen's kappa": "Agreement corrected for the agreement that chance alone would produce. 0 is chance-level; 1 is perfect.",
  "ROC-AUC (OvR)": "For each band in turn, the probability that a randomly chosen day of that band is scored higher than a randomly chosen day that is not. 0.5 is random.",
  Silhouette: "How well each city sits inside its own cluster compared with the nearest other cluster. Runs from −1 to 1; higher is better.",
  "Davies-Bouldin": "Average similarity between each cluster and the one most like it. Lower is better.",
  "Calinski-Harabasz": "Ratio of between-cluster to within-cluster dispersion. Higher is better.",
  "Persistence baseline": "The naive forecast that tomorrow equals today. Any model that cannot beat it has added nothing.",
  "Ordinal error": "How many severity bands away a wrong prediction landed. An error of one band is far less serious than an error of three.",
};

export default function ModelInsightsPage() {
  const [tab, setTab] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => {
    const json = (p) => fetch(p).then((r) => r.json()).catch(() => null);
    const text = (p) => fetch(p).then((r) => r.text()).catch(() => "");
    Promise.all([
      json("/data/evaluation_regression.json"),
      json("/data/evaluation_classification.json"),
      json("/data/evaluation_clustering.json"),
      json("/data/tuning_report.json"),
      json("/data/explainability.json"),
      json("/data/error_analysis.json"),
      json("/data/master_comparison_regression.json"),
      json("/data/master_comparison_classification.json"),
      json("/data/master_comparison_clustering.json"),
      json("/data/feature_engineering_report.json"),
      json("/data/cleaning_report.json"),
      text("/data/data_card.md"),
      text("/data/model_card.md"),
      json("/data/deployment_classifier.json"),
    ]).then((v) =>
      setData({
        regression: v[0], classification: v[1], clustering: v[2], tuning: v[3], explain: v[4],
        errors: v[5], masterReg: v[6] || [], masterClf: v[7] || [], masterClust: v[8] || [],
        featuresReport: v[9], cleaning: v[10], dataCard: v[11], modelCard: v[12], deployed: v[13],
      })
    );
  }, []);

  if (!data) return <Loading />;

  return (
    <div>
      <span className="eyebrow">Evidence behind every number</span>
      <h1>Model Insights</h1>

      <div className="tabs">
        {TABS.map((t, i) => (
          <button key={t} className={i === tab ? "active" : ""} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ComparisonTab data={data} />}
      {tab === 1 && <ErrorsTab data={data} />}
      {tab === 2 && <ExplainTab data={data} />}
      {tab === 3 && <TuningTab data={data} />}
      {tab === 4 && <LeakageTab data={data} />}
      {tab === 5 && <GlossaryTab />}
      {tab === 6 && <CardsTab data={data} />}
    </div>
  );
}

function ComparisonTab({ data }) {
  const { regression, classification, masterReg, masterClf, masterClust, deployed } = data;
  return (
    <div>
      <SectionTitle eyebrow="Task 1" caption={regression.primary_metric_justification}>
        Regression — next-day AQI value
      </SectionTitle>
      <Table rows={masterReg} />
      <Figure src="/figures/27_regression_comparison.png" />

      <SectionTitle eyebrow="Task 2" caption={classification.primary_metric_justification}>
        Classification — next-day AQI band
      </SectionTitle>
      <Table rows={masterClf} />
      <Figure src="/figures/28_classification_comparison.png" />

      {deployed && (
        <Banner kind="info">
          <strong>What this deployment actually serves.</strong> {deployed.purpose} Measured on the
          same split and feature set: macro-F1{" "}
          <strong>{deployed.test_metrics.macro_f1.toFixed(4)}</strong> for the deployed{" "}
          {deployed.model}, against <strong>{deployed.reference_test_metrics.macro_f1.toFixed(4)}</strong>{" "}
          for the reported {deployed.reference_model} — a gap of{" "}
          <strong>{deployed.macro_f1_gap_vs_reference}</strong>.
        </Banner>
      )}

      <SectionTitle eyebrow="Task 3">Clustering — city archetypes</SectionTitle>
      <Table rows={masterClust} />
      <div className="grid grid-2">
        <Figure src="/figures/24_clustering_selection.png" />
        <Figure src="/figures/25_cluster_profiles.png" />
      </div>

      <SectionTitle>Generalisation and learning behaviour</SectionTitle>
      <div className="grid grid-2">
        <Figure src="/figures/34_train_test_gap.png" />
        <Figure src="/figures/32_learning_curves.png" />
      </div>
    </div>
  );
}

function ErrorsTab({ data }) {
  const { regression, errors } = data;
  return (
    <div>
      <SectionTitle>Confusion matrices</SectionTitle>
      <Figure src="/figures/29_confusion_matrices.png" />

      <SectionTitle>Discrimination by class</SectionTitle>
      <Figure src="/figures/30_roc_curves.png" />

      <SectionTitle caption={regression.residual_analysis?.interpretation}>
        Residual diagnostics
      </SectionTitle>
      <Figure src="/figures/31_residual_analysis.png" />

      <SectionTitle>Error analysis</SectionTitle>
      {errors && (
        <>
          <div className="grid grid-4">
            <Metric hero label="Test predictions" value={errors.n_test.toLocaleString()} />
            <Metric hero label="Wrong" value={errors.n_wrong.toLocaleString()} delta={`${errors.error_rate_pct}% of days`} />
            <Metric hero label="Wrong by 2+ bands" value={errors.n_wrong_by_two_or_more_bands.toLocaleString()} delta={`${errors.pct_wrong_by_two_or_more_bands}%`} />
            <Metric
              hero
              label="Understating severity by 2+"
              value={errors.n_understating_severity_by_two_or_more.toLocaleString()}
              delta={`${errors.pct_understating_severity_by_two_or_more}% — the health-critical failure`}
            />
          </div>
          <p>{errors.interpretation}</p>
          <Figure src="/figures/35_error_analysis.png" />
          <h3>Most frequent misclassification transitions</h3>
          <Table rows={errors.most_frequent_transitions} />
        </>
      )}

      <SectionTitle>Error by city</SectionTitle>
      <Figure src="/figures/33_per_city_error.png" />
    </div>
  );
}

function ExplainTab({ data }) {
  const { explain } = data;
  if (!explain) return <Banner kind="info">Explainability results not found.</Banner>;
  const local = explain.local_example;
  return (
    <div>
      <SectionTitle caption={explain.method}>Why the model predicts what it predicts</SectionTitle>
      <Figure src="/figures/36_shap_global.png" />
      <Banner kind="success">{explain.interpretation}</Banner>
      <Banner kind="warn">
        <strong>How not to read this ranking.</strong> The healthy-adult Health Advisory Index is computed from
        today&apos;s sub-indices, so it is strongly correlated with the AQI and with PM2.5. A high rank shows how the
        attribution is shared among correlated inputs. It is not independent evidence that the index is valid.
      </Banner>

      <SectionTitle>A single day, decomposed</SectionTitle>
      <div className="grid grid-3">
        <Metric hero label="Base value" value={local.base_value.toFixed(0)} delta="dataset mean" />
        <Metric hero label="Forecast" value={local.prediction.toFixed(0)} delta={`${local.city}, ${local.date}`} />
        <Metric hero label="Actual" value={local.actual.toFixed(0)} delta={`error ${(local.prediction - local.actual > 0 ? "+" : "") + (local.prediction - local.actual).toFixed(0)}`} />
      </div>
      <Figure src="/figures/37_shap_local_waterfall.png" />
      <Table rows={local.top_contributions} />
    </div>
  );
}

function TuningTab({ data }) {
  const { tuning } = data;
  if (!tuning) return <Banner kind="info">Tuning results not found.</Banner>;
  return (
    <div>
      <SectionTitle caption={tuning.strategy}>Hyperparameter optimisation</SectionTitle>
      <Figure src="/figures/26_tuning_before_after.png" />

      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            <Badge colour="#009E73">Regression</Badge> {tuning.regression.model}
          </h3>
          <Table
            columns={["Setting", "MAE", "RMSE", "R2", "MAPE_pct"]}
            rows={[
              { Setting: "Default", ...tuning.regression.untuned_test },
              { Setting: "Tuned", ...tuning.regression.tuned_test },
            ]}
          />
          <p className="caption">
            These are errors on one held-out year. Four-fold expanding-window cross-validation gives a larger MAE,
            29.9 &plusmn; 10.0. The test year is cleaner than the training years and includes the lockdown, so the
            single-year figure flatters the model.
          </p>
          <details>
            <summary className="caption" style={{ cursor: "pointer" }}>Best parameters</summary>
            <pre>{JSON.stringify(tuning.regression.best_params, null, 2)}</pre>
          </details>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            <Badge colour="#E69F00">Classification</Badge> {tuning.classification.model}
          </h3>
          <Table
            rows={[
              { Setting: "Default", ...tuning.classification.untuned_test },
              { Setting: "Tuned", ...tuning.classification.tuned_test },
            ]}
          />
          <details>
            <summary className="caption" style={{ cursor: "pointer" }}>Best parameters</summary>
            <pre>{JSON.stringify(tuning.classification.best_params, null, 2)}</pre>
          </details>
        </div>
      </div>

      <Banner kind="info" icon="⏱">
        <strong>Cost against gain.</strong> {tuning.cost_vs_gain.assessment}
      </Banner>

      <details className="card">
        <summary>Search spaces and why each parameter was included</summary>
        <div style={{ marginTop: 12 }}>
          {Object.entries(tuning.search_space_rationale).map(([name, reason]) => (
            <p key={name}><strong>{name}</strong> — {reason}</p>
          ))}
        </div>
        <h3>Exhaustive grid over the Ridge penalty</h3>
        <Table rows={tuning.ridge_exhaustive.cv_curve} />
        <p className="caption" style={{ marginBottom: 0 }}>{tuning.ridge_exhaustive.note}</p>
      </details>
    </div>
  );
}

function LeakageTab({ data }) {
  const { classification, featuresReport, cleaning } = data;
  const leak = classification.leakage_demonstration;
  return (
    <div>
      <SectionTitle caption={leak?.experiment}>Leakage: demonstrated, not merely asserted</SectionTitle>
      {leak && (
        <>
          <Table
            rows={["same_day_nowcast_with_aqi", "same_day_nowcast_without_aqi", "next_day_forecast_this_project"].map((key) => ({
              Setup: key.replace(/_/g, " "),
              "Macro F1": leak[key].macro_f1,
              Accuracy: leak[key].accuracy,
              Features: leak[key].n_features,
            }))}
          />
          <Banner kind="error">{leak.conclusion}</Banner>
        </>
      )}

      {featuresReport && (
        <>
          <SectionTitle>Every leakage control applied in this project</SectionTitle>
          {Object.entries(featuresReport.leakage_controls).map(([name, description]) => (
            <div className="card" key={name}>
              <h3 style={{ marginTop: 0, textTransform: "capitalize" }}>{name}</h3>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>{description}</p>
            </div>
          ))}
        </>
      )}

      {cleaning && (
        <>
          <SectionTitle caption={cleaning.imputation_comparison.selection_rationale}>
            Imputation chosen by measurement
          </SectionTitle>
          <Table
            rows={cleaning.imputation_comparison.results.map((r) => ({
              Strategy: r.strategy,
              Causal: r.causal,
              "MAE / IQR": r.mean_mae_over_iqr,
              "KS statistic": r.mean_ks_statistic,
              "Mean |std shift| (%)": r.mean_abs_std_shift_pct,
            }))}
          />
        </>
      )}
    </div>
  );
}

function GlossaryTab() {
  return (
    <div>
      <SectionTitle>What each metric means, in plain language</SectionTitle>
      <div className="grid grid-2">
        {Object.entries(METRIC_GLOSSARY).map(([name, desc]) => (
          <div className="card" key={name} style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>{name}</h3>
            <p className="caption" style={{ margin: 0 }}>{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CardsTab({ data }) {
  return (
    <div className="grid grid-2">
      <div className="card"><Markdown text={data.dataCard} /></div>
      <div className="card"><Markdown text={data.modelCard} /></div>
    </div>
  );
}
