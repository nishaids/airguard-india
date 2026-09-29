"use client";

import { useEffect, useState } from "react";
import { Metric, Banner, Table, Figure } from "../components/ui";

const TABS = ["Comparison", "Confusion and errors", "Explainability", "Tuning", "Leakage controls", "Metric glossary", "Data and model cards"];

const METRIC_GLOSSARY = {
  MAE: "Mean absolute error. The average size of the miss, in AQI points.",
  RMSE: "Root mean squared error. Like MAE, but large misses count disproportionately.",
  "R-squared": "The share of the variation in next-day AQI the model accounts for. 1.0 is perfect.",
  MAPE: "Mean absolute percentage error. The typical miss as a percentage of the true value.",
  Accuracy: "The share of days whose band was predicted exactly right. Misleading alone, since bands are uneven.",
  "Macro F1": "The average F1 across all six bands, equal weight regardless of rarity. The primary metric.",
  "Weighted F1": "The same average, weighted by how common each band is. Closer to accuracy.",
  "Balanced accuracy": "The average recall across bands.",
  "Cohen's kappa": "Agreement corrected for chance. 0 is chance-level; 1 is perfect.",
  "ROC-AUC (OvR)": "Probability a random day of one band scores higher than a random day of another. 0.5 is random.",
  Silhouette: "How well each city sits in its own cluster vs the nearest other. -1 to 1, higher better.",
  "Davies-Bouldin": "Average similarity between each cluster and its closest rival. Lower is better.",
  "Calinski-Harabasz": "Ratio of between-cluster to within-cluster dispersion. Higher is better.",
  "Persistence baseline": "The naive forecast that tomorrow equals today.",
  "Ordinal error": "How many severity bands away a wrong prediction landed.",
};

export default function ModelInsightsPage() {
  const [tab, setTab] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/data/evaluation_regression.json").then((r) => r.json()),
      fetch("/data/evaluation_classification.json").then((r) => r.json()),
      fetch("/data/evaluation_clustering.json").then((r) => r.json()),
      fetch("/data/tuning_report.json").then((r) => r.json()),
      fetch("/data/explainability.json").then((r) => r.json()),
      fetch("/data/error_analysis.json").then((r) => r.json()),
      fetch("/data/master_comparison_regression.json").then((r) => r.json()).catch(() => []),
      fetch("/data/master_comparison_classification.json").then((r) => r.json()).catch(() => []),
      fetch("/data/master_comparison_clustering.json").then((r) => r.json()).catch(() => []),
      fetch("/data/feature_engineering_report.json").then((r) => r.json()).catch(() => null),
      fetch("/data/cleaning_report.json").then((r) => r.json()).catch(() => null),
      fetch("/data/data_card.md").then((r) => r.text()).catch(() => ""),
      fetch("/data/model_card.md").then((r) => r.text()).catch(() => ""),
      fetch("/data/deployment_classifier.json").then((r) => r.json()).catch(() => null),
    ]).then(([regression, classification, clustering, tuning, explain, errors, masterReg, masterClf, masterClust, featuresReport, cleaning, dataCard, modelCard, deploymentClassifier]) => {
      setData({ regression, classification, clustering, tuning, explain, errors, masterReg, masterClf, masterClust, featuresReport, cleaning, dataCard, modelCard, deploymentClassifier });
    });
  }, []);

  if (!data) return <p className="caption">Loading...</p>;

  return (
    <div>
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
  const { regression, classification, masterReg, masterClf, masterClust, deploymentClassifier } = data;
  return (
    <div>
      <h2>Regression: next-day AQI value</h2>
      <p className="caption">{regression.primary_metric_justification}</p>
      <Table rows={masterReg} />
      <Figure src="/figures/27_regression_comparison.png" />

      <h2>Classification: next-day AQI band</h2>
      <p className="caption">{classification.primary_metric_justification}</p>
      <Table rows={masterClf} />
      <Figure src="/figures/28_classification_comparison.png" />

      {deploymentClassifier && (
        <Banner kind="info">
          <strong>Vercel deployment note.</strong> {deploymentClassifier.purpose} Measured gap:
          macro-F1 {deploymentClassifier.test_metrics.macro_f1.toFixed(4)} for the deployed
          LightGBM + SMOTE model vs {deploymentClassifier.reference_test_metrics.macro_f1.toFixed(4)}{" "}
          for the reported XGBoost + SMOTE model ({deploymentClassifier.macro_f1_gap_vs_reference}).
        </Banner>
      )}

      <h2>Clustering: city archetypes</h2>
      <Table rows={masterClust} />
      <Figure src="/figures/24_clustering_selection.png" />
      <Figure src="/figures/25_cluster_profiles.png" />

      <h2>Generalisation and learning behaviour</h2>
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
      <h2>Confusion matrices</h2>
      <Figure src="/figures/29_confusion_matrices.png" />

      <h2>Discrimination by class</h2>
      <Figure src="/figures/30_roc_curves.png" />

      <h2>Residual diagnostics</h2>
      <Figure src="/figures/31_residual_analysis.png" />
      <p><strong>Interpretation.</strong> {regression.residual_analysis?.interpretation}</p>

      <h2>Error analysis</h2>
      <Figure src="/figures/35_error_analysis.png" />
      {errors && (
        <>
          <div className="grid grid-4">
            <Metric label="Test predictions" value={errors.n_test.toLocaleString()} />
            <Metric label="Wrong" value={`${errors.n_wrong.toLocaleString()}`} delta={`${errors.error_rate_pct}%`} />
            <Metric label="Wrong by 2+ bands" value={errors.n_wrong_by_two_or_more_bands.toLocaleString()} delta={`${errors.pct_wrong_by_two_or_more_bands}%`} />
            <Metric label="Understating severity by 2+" value={errors.n_understating_severity_by_two_or_more.toLocaleString()} delta={`${errors.pct_understating_severity_by_two_or_more}%`} />
          </div>
          <p><strong>Interpretation.</strong> {errors.interpretation}</p>
          <h3>Most frequent misclassification transitions</h3>
          <Table rows={errors.most_frequent_transitions} />
        </>
      )}

      <h2>Error by city</h2>
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
      <h2>Why the model predicts what it predicts</h2>
      <p><strong>Method.</strong> {explain.method}</p>
      <Figure src="/figures/36_shap_global.png" />
      <p><strong>Interpretation.</strong> {explain.interpretation}</p>

      <h2>A single day, decomposed</h2>
      <Figure src="/figures/37_shap_local_waterfall.png" />
      <p>
        On <strong>{local.date}</strong> in <strong>{local.city}</strong>, the model forecast{" "}
        <strong>{local.prediction.toFixed(0)}</strong> against an actual{" "}
        <strong>{local.actual.toFixed(0)}</strong>, starting from a base value of {local.base_value.toFixed(0)}.
      </p>
      <Table rows={local.top_contributions} />
    </div>
  );
}

function TuningTab({ data }) {
  const { tuning } = data;
  if (!tuning) return <Banner kind="info">Tuning results not found.</Banner>;
  return (
    <div>
      <h2>Hyperparameter optimisation</h2>
      <p><strong>Strategy.</strong> {tuning.strategy}</p>
      <Figure src="/figures/26_tuning_before_after.png" />

      <div className="grid grid-2">
        <div>
          <h3>Regression: {tuning.regression.model}</h3>
          <Table
            rows={[
              { Setting: "Default", ...tuning.regression.untuned_test },
              { Setting: "Tuned", ...tuning.regression.tuned_test },
            ]}
            columns={["Setting", "MAE", "RMSE", "R2", "MAPE_pct"]}
          />
          <pre className="caption" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(tuning.regression.best_params, null, 2)}</pre>
        </div>
        <div>
          <h3>Classification: {tuning.classification.model}</h3>
          <Table rows={[{ Setting: "Default", ...tuning.classification.untuned_test }, { Setting: "Tuned", ...tuning.classification.tuned_test }]} />
          <pre className="caption" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(tuning.classification.best_params, null, 2)}</pre>
        </div>
      </div>

      <h3>Cost against gain</h3>
      <Banner kind="info" icon="⏱">{tuning.cost_vs_gain.assessment}</Banner>

      <details className="card">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Search spaces and why each parameter was included</summary>
        {Object.entries(tuning.search_space_rationale).map(([name, reason]) => (
          <p key={name}><strong>{name}</strong> — {reason}</p>
        ))}
        <h3>Exhaustive grid over the Ridge penalty</h3>
        <Table rows={tuning.ridge_exhaustive.cv_curve} />
        <p className="caption">{tuning.ridge_exhaustive.note}</p>
      </details>
    </div>
  );
}

function LeakageTab({ data }) {
  const { classification, featuresReport, cleaning } = data;
  const leak = classification.leakage_demonstration;
  return (
    <div>
      <h2>Leakage: demonstrated, not merely asserted</h2>
      {leak && (
        <>
          <p><strong>Experiment.</strong> {leak.experiment}</p>
          <Table
            rows={["same_day_nowcast_with_aqi", "same_day_nowcast_without_aqi", "next_day_forecast_this_project"].map((key) => ({
              Setup: key.replace(/_/g, " "),
              "Macro F1": leak[key].macro_f1,
              Accuracy: leak[key].accuracy,
              Features: leak[key].n_features,
              Description: leak[key].description,
            }))}
          />
          <Banner kind="error" icon="🚨">{leak.conclusion}</Banner>
        </>
      )}

      {featuresReport && (
        <>
          <h2>Every leakage control applied in this project</h2>
          {Object.entries(featuresReport.leakage_controls).map(([name, description]) => (
            <p key={name}><strong>{name[0].toUpperCase() + name.slice(1)}.</strong> {description}</p>
          ))}
        </>
      )}

      {cleaning && (
        <>
          <h2>Imputation chosen by measurement</h2>
          <Table
            rows={cleaning.imputation_comparison.results.map((r) => ({
              Strategy: r.strategy, Causal: r.causal, "MAE / IQR": r.mean_mae_over_iqr,
              "KS statistic": r.mean_ks_statistic, "Mean |std shift| (%)": r.mean_abs_std_shift_pct,
            }))}
          />
          <p><strong>Selection.</strong> {cleaning.imputation_comparison.selection_rationale}</p>
        </>
      )}
    </div>
  );
}

function GlossaryTab() {
  return (
    <div>
      <h2>What each metric means, in plain language</h2>
      {Object.entries(METRIC_GLOSSARY).map(([name, desc]) => (
        <p key={name}><strong>{name}.</strong> {desc}</p>
      ))}
    </div>
  );
}

function CardsTab({ data }) {
  return (
    <div className="grid grid-2">
      <div><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{data.dataCard}</pre></div>
      <div><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{data.modelCard}</pre></div>
    </div>
  );
}
