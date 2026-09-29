"use client";

import { useEffect, useState } from "react";
import { Metric, Banner } from "./components/ui";

export default function Home() {
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/data/evaluation_regression.json").then((r) => r.json()),
      fetch("/data/evaluation_classification.json").then((r) => r.json()),
      fetch("/data/hai_divergence.json").then((r) => r.json()),
      fetch("/data/evaluation_clustering.json").then((r) => r.json()),
      fetch("/data/meta.json").then((r) => r.json()),
      fetch("/data/PROVENANCE.json").then((r) => r.json()).catch(() => null),
    ]).then(([regression, classification, divergence, clustering, meta, provenance]) => {
      setData({ regression, classification, divergence, clustering, meta, provenance });
    });
  }, []);

  if (!data) return <p className="caption">Loading...</p>;

  const { regression, classification, divergence, clustering, meta, provenance } = data;

  return (
    <div>
      <h1>AirGuard India</h1>
      <p className="caption">{meta.academic.project_subtitle}</p>

      <p>
        Air quality indices in India report a single number for an entire city, and the same
        number for every person in it. A child with developing airways, a person with COPD, a
        cardiac patient and a healthy adult receive identical advice, although the documented
        exposure-response relationships differ substantially between them. The index also
        describes the air that has already been breathed rather than the air that is coming.
      </p>
      <p>
        <strong>AirGuard India addresses both gaps.</strong> It forecasts the next day rather
        than summarising today, and it reports a <strong>vulnerability-weighted Health Advisory
        Index</strong> for seven population cohorts alongside the official AQI.
      </p>

      <h2>Headline results</h2>
      <div className="grid grid-4">
        <Metric
          label="Next-day AQI error (MAE)"
          value={regression.best_test_metrics.MAE.toFixed(1)}
          delta={`${regression.baseline_comparison.improvement_over_persistence_pct.toFixed(1)}% vs persistence`}
          deltaGood={true}
        />
        <Metric
          label="Band classification (macro F1)"
          value={classification.best_test_metrics.macro_f1.toFixed(3)}
          delta={`${classification.baseline_comparison.improvement_over_persistence_pct.toFixed(1)}% vs persistence`}
          deltaGood={true}
        />
        <Metric
          label="Days where a cohort differs from AQI"
          value={`${(divergence?.any_cohort_differs?.pct ?? 0).toFixed(1)}%`}
        />
        <Metric label="Cities covered" value={meta.cities.length} />
      </div>

      <div className="grid grid-1-4" style={{ marginTop: 24 }}>
        <div>
          <h2>What each page does</h2>
          <p>
            <strong>Forecast</strong> — pick a city, a date and a cohort. Returns tomorrow&apos;s
            predicted AQI, the predicted band with the model&apos;s confidence, the cohort&apos;s
            Health Advisory Index and band, the dominant pollutant, the cleanest outdoor window,
            and plain-language advice. Includes what-if sliders.
          </p>
          <p>
            <strong>City Risk Atlas</strong> — the pollution archetypes discovered without
            supervision, the ranked risk table, the seasonal heatmap, and the festival and
            lockdown panels.
          </p>
          <p>
            <strong>Policy Simulator</strong> — reduce pollutants by a chosen proportion and see
            how many city-days move to a safer band and how many cohort advisory-days are
            averted.
          </p>
          <p>
            <strong>Model Insights</strong> — the full comparison tables, confusion matrices,
            SHAP explanations, the leakage demonstration, and the data and model cards.
          </p>

          {clustering ? (
            <>
              <h3>City archetypes</h3>
              {clustering.archetypes.map((entry) => (
                <p key={entry.archetype}>
                  <strong>{entry.archetype}</strong> ({entry.n_cities} cities:{" "}
                  {entry.cities.join(", ")}) — {entry.policy_lever}
                </p>
              ))}
            </>
          ) : null}
        </div>

        <div>
          <h2>Dataset and licence</h2>
          {provenance ? (
            <div className="card">
              <strong>{provenance.dataset.title_scraped}</strong>
              <table style={{ marginTop: 10 }}>
                <tbody>
                  <tr><td>Source</td><td>{provenance.upstream_source.organisation}</td></tr>
                  <tr><td>Licence</td><td><strong>{provenance.license.string_as_displayed_on_kaggle}</strong></td></tr>
                  <tr><td>Records</td><td>{provenance.primary_file.rows.toLocaleString()} city-days</td></tr>
                  <tr><td>Coverage</td><td>{provenance.primary_file.date_min} to {provenance.primary_file.date_max}</td></tr>
                  <tr><td>Cities in source</td><td>{provenance.primary_file.n_cities}</td></tr>
                </tbody>
              </table>
              <p className="caption" style={{ marginTop: 10 }}>
                Code in this repository is MIT licensed. Verified live: {String(provenance.license.verified_live)}.
              </p>
            </div>
          ) : (
            <Banner kind="info">Provenance record not found.</Banner>
          )}

          <h2>Models in use</h2>
          <ul>
            <li>Regression: <strong>{regression.best_model} (tuned)</strong></li>
            <li>
              Classification (this deployment): <strong>LightGBM + SMOTE</strong>{" "}
              <span className="caption">
                — XGBoost + SMOTE is the reported best model (macro-F1 {classification.best_test_metrics.macro_f1.toFixed(3)});
                the Vercel deployment serves LightGBM instead because XGBoost&apos;s size exceeds
                the serverless function limit. See Model Insights for the measured gap.
              </span>
            </li>
            <li>Clustering: <strong>K-Means, k={clustering?.selected_k ?? "?"}</strong></li>
          </ul>
        </div>
      </div>

      <Banner kind="warn" icon="⚠">
        <strong>Important.</strong> AirGuard India provides general air quality guidance for
        public-health awareness. It is not medical advice and must not replace consultation with
        a qualified clinician.
      </Banner>

      <p className="footer-note">
        {meta.academic.course_code} {meta.academic.course_name} · {meta.academic.institution} ·{" "}
        <a href={meta.repo_url}>{meta.repo_url}</a>
      </p>
    </div>
  );
}
