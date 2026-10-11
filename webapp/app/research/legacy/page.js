"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Metric, Banner, Loading, Badge } from "../../components/ui";
import LiveDataSection from "../../components/LiveDataSection";

const PAGES = [
  {
    href: "/live",
    title: "Historical replay",
    body: "Nationwide raw CAMS estimates with provider provenance. Station-correction skill and operational uncertainty are not established; earlier past-fields comparisons remain exploratory research.",
  },
  {
    href: "/historical-replay",
    title: "Historical explorer",
    body: "Replays the 2015-2020 record. Pick a city, a date and a cohort. Returns the next day's predicted AQI, the predicted band with the model's score, the cohort's Health Advisory Index, the dominant pollutant, the cleanest outdoor window and plain-language advice. Includes what-if sliders.",
  },
  {
    href: "/research/historical-atlas",
    title: "City Risk Atlas",
    body: "The pollution archetypes discovered without supervision, the ranked risk table, the seasonal heatmap, and the festival and lockdown panels.",
  },
  {
    href: "/research/historical-policy",
    title: "Policy Simulator",
    body: "Counterfactual AQI recomputation under declared concentration reductions. Category changes are arithmetic scenarios, not causal policy effects or prevented clinical outcomes.",
  },
  {
    href: "/model-insights",
    title: "Model Insights",
    body: "The full comparison tables, confusion matrices, SHAP explanations, the leakage demonstration, and the data and model cards.",
  },
];

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
    ]).then(([regression, classification, divergence, clustering, meta, provenance]) =>
      setData({ regression, classification, divergence, clustering, meta, provenance })
    );
  }, []);

  if (!data) return <Loading />;
  const { regression, classification, divergence, clustering, meta, provenance } = data;

  return (
    <div><p role="note" className="research-notice">HISTORICAL REPLAY — NOT CURRENT AIR QUALITY. Legacy research using 2015–2020 observations and the original training cities.</p>
      <section className="hero">
        <span className="eyebrow">Vulnerability-weighted air quality intelligence</span>
        <p role="note">Legacy CV scores require re-evaluation: original city-ordered folds were not chronological.</p><h1>
          <span className="gradient-text">AirGuard India</span>
        </h1>
        <p style={{ fontSize: "1.05rem", marginTop: 14 }}>
          Air quality indices in India report a single number for an entire city, and the same
          number for every person in it. A child with developing airways, a person with COPD, a
          cardiac patient and a healthy adult receive identical advice, although the documented
          exposure–response relationships differ substantially between them. The index also
          describes the air that has already been breathed rather than the air that is coming.
        </p>
        <p style={{ fontSize: "1.05rem" }}>
          <strong>AirGuard India addresses both gaps.</strong> It forecasts the next day rather than
          summarising today, and reports a <strong>Health Advisory Index</strong> for seven
          population cohorts alongside the official AQI.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 20, position: "relative" }}>
          <Link href="/historical-replay">
            <button className="btn">Open historical replay â†’</button>
          </Link>
          <Badge colour="#009E73">{meta.cities.length} cities</Badge>
          <Badge colour="#56B4E9">7 cohorts</Badge>
          <Badge colour="#CC79A7">3 ML paradigms</Badge>
        </div>
      </section>

      <LiveDataSection />

      <h2>Headline results</h2>
      <div className="grid grid-4">
        <Metric
          hero
          label="Next-day AQI error (MAE)"
          value={regression.best_test_metrics.MAE.toFixed(1)}
          delta={`${regression.baseline_comparison.improvement_over_persistence_pct.toFixed(1)}% better than persistence`}
          deltaGood
          help="Mean absolute error on the held-out test period, against the naive forecast that tomorrow equals today."
        />
        <Metric
          hero
          label="Band classification (macro F1)"
          value={classification.best_test_metrics.macro_f1.toFixed(3)}
          delta={`${classification.baseline_comparison.improvement_over_persistence_pct.toFixed(1)}% better than persistence`}
          deltaGood
          help="Macro-averaged F1 across the six CPCB bands, chosen so the rare Severe class cannot be ignored."
        />
        <Metric
          hero
          label="Days a cohort differs from AQI"
          value={`${(divergence?.any_cohort_differs?.pct ?? 0).toFixed(1)}%`}
          delta="of all city-days"
          help="Share of city-days on which at least one cohort would receive a different advisory band from the official AQI."
        />
        <Metric hero label="Cities covered" value={meta.cities.length} delta="passing the completeness gates" />
      </div>

      <h2>What each page does</h2>
      <div className="grid grid-2">
        {PAGES.map((page) => (
          <Link key={page.href} href={page.href} style={{ color: "inherit" }}>
            <div className="card" style={{ height: "100%", margin: 0 }}>
              <h3 style={{ marginTop: 0, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                {page.title}
                <span style={{ color: "var(--accent)", fontSize: "1.1rem" }}>â†’</span>
              </h3>
              <p className="caption" style={{ margin: 0 }}>{page.body}</p>
            </div>
          </Link>
        ))}
      </div>

      <div className="grid grid-1-4">
        <div>
          <h2>City archetypes</h2>
          {clustering?.archetypes.map((entry, i) => (
            <div className="card" key={entry.archetype}>
              <h3 style={{ marginTop: 0 }}>
                <Badge colour={["#0072B2", "#D55E00", "#009E73"][i % 3]}>{entry.defining_pollutant}</Badge>{" "}
                {entry.archetype}
              </h3>
              <p className="caption" style={{ marginBottom: 8 }}>
                {entry.n_cities} cities — {entry.cities.join(", ")}
              </p>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>{entry.mix_interpretation} <em>Association only; no source apportionment is cited, so no intervention is implied.</em></p>
            </div>
          ))}
        </div>

        <div>
          <h2>Dataset and licence</h2>
          {provenance ? (
            <div className="card">
              <strong>{provenance.dataset.title_scraped}</strong>
              <div className="table-wrap" style={{ marginTop: 12 }}>
                <table>
                  <tbody>
                    <tr><td>Source</td><td>{provenance.upstream_source.organisation}</td></tr>
                    <tr><td>Licence</td><td><strong>{provenance.license.string_as_displayed_on_kaggle}</strong></td></tr>
                    <tr><td>Records</td><td>{provenance.primary_file.rows.toLocaleString()} city-days</td></tr>
                    <tr><td>Coverage</td><td>{provenance.primary_file.date_min} â†’ {provenance.primary_file.date_max}</td></tr>
                    <tr><td>Cities in source</td><td>{provenance.primary_file.n_cities}</td></tr>
                  </tbody>
                </table>
              </div>
              <p className="caption" style={{ marginTop: 12, marginBottom: 0 }}>
                The licence string was read from the dataset page at download time and recorded with a
                SHA-256 checksum for every file. Code in this repository is MIT licensed.
              </p>
            </div>
          ) : (
            <Banner kind="info">Provenance record not found.</Banner>
          )}

          <h2>Models in use</h2>
          <div className="card">
            <p style={{ marginBottom: 10 }}>
              <Badge colour="#009E73">Regression</Badge>{" "}
              <strong>{regression.best_model} (tuned)</strong>
            </p>
            <p style={{ marginBottom: 10 }}>
              <Badge colour="#E69F00">Classification</Badge> <strong>LightGBM + SMOTE</strong>
              <span className="caption">
                {" "}— this deployment. XGBoost + SMOTE is the reported best model (macro-F1{" "}
                {classification.best_test_metrics.macro_f1.toFixed(3)}); it exceeds the serverless
                size limit, so the measured gap is disclosed in Model Insights.
              </span>
            </p>
            <p style={{ margin: 0 }}>
              <Badge colour="#CC79A7">Clustering</Badge>{" "}
              <strong>K-Means, k={clustering?.selected_k ?? "?"}</strong>
            </p>
          </div>
        </div>
      </div>

      <Banner kind="warn">
        <strong>Important.</strong> AirGuard India provides general air quality guidance for
        public-health awareness. It is not medical advice and must not replace consultation with a
        qualified clinician.
      </Banner>

      <p className="footer-note">
        {meta.academic.course_code} {meta.academic.course_name} Â· {meta.academic.institution} Â·{" "}
        <a href={meta.repo_url} target="_blank" rel="noreferrer">{meta.repo_url}</a>
      </p>
    </div>
  );
}
