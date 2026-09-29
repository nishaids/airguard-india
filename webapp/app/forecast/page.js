"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceDot, ResponsiveContainer,
  BarChart, Bar, ReferenceLine, Cell,
} from "recharts";
import { Metric, Banner, Table } from "../components/ui";

const BAND_COLOUR = {
  Low: "#009E73",
  Moderate: "#F0E442",
  High: "#E69F00",
  "Very High": "#D55E00",
  Extreme: "#CC79A7",
};

const BUCKET_COLOUR = {
  Good: "#009E73",
  Satisfactory: "#A8DDB5",
  Moderate: "#F0E442",
  Poor: "#E69F00",
  "Very Poor": "#D55E00",
  Severe: "#8B0000",
};

export default function ForecastPage() {
  const [meta, setMeta] = useState(null);
  const [city, setCity] = useState("Delhi");
  const [cohort, setCohort] = useState("healthy_adult");
  const [date, setDate] = useState("");
  const [adjustments, setAdjustments] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/data/meta.json").then((r) => r.json()).then((m) => {
      setMeta(m);
      const initialCity = m.cities.includes("Delhi") ? "Delhi" : m.cities[0];
      setCity(initialCity);
      setDate(m.date_bounds[initialCity].max);
      const zero = {};
      m.hai_pollutants.forEach((p) => (zero[p] = 0));
      setAdjustments(zero);
    });
  }, []);

  const bounds = meta && city ? meta.date_bounds[city] : null;

  const runForecast = async () => {
    if (!city || !date) return;
    setLoading(true);
    try {
      const res = await fetch("/api/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, date, cohort, adjustments }),
      });
      const payload = await res.json();
      setResult(payload);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (city && date && meta) runForecast();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, date, cohort, meta]);

  const applyAdjustments = () => runForecast();

  if (!meta) return <p className="caption">Loading...</p>;

  const band = result?.ok ? result.cohort.band : null;
  const bandColour = BAND_COLOUR[band] || "#56B4E9";

  const chartData = useMemo(() => {
    if (!result?.ok) return [];
    return (result.history || []).map((row) => ({ date: row.Date, observed: row.AQI }));
  }, [result]);

  const forecastPoint = result?.ok
    ? { date: result.forecast_date, value: result.predicted_aqi }
    : null;

  const distributionData = result?.ok
    ? meta.aqi_buckets.map((b) => ({ bucket: b, probability: result.bucket_distribution[b] || 0 }))
    : [];

  return (
    <div>
      <h1>Next-day forecast</h1>

      <div className="grid grid-4">
        <div>
          <label>City</label>
          <select value={city} onChange={(e) => { setCity(e.target.value); setDate(meta.date_bounds[e.target.value].max); }}>
            {meta.cities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Cohort</label>
          <select value={cohort} onChange={(e) => setCohort(e.target.value)}>
            {meta.cohorts.map((c) => (
              <option key={c} value={c}>{meta.cohort_labels[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Date</label>
          <input
            type="date"
            value={date}
            min={bounds?.min}
            max={bounds?.max}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <Metric
          label="Records available"
          value={bounds ? `${Math.round((new Date(bounds.max) - new Date(bounds.min)) / 86400000) + 1} days` : "-"}
        />
      </div>

      <details className="card" style={{ marginTop: 16 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>What-if: reduce today&apos;s pollutants</summary>
        <p className="caption">
          Reduce today&apos;s measured concentrations and watch the forecast and the advisory
          respond. Lag and rolling features are left untouched, because a what-if about today
          does not rewrite the preceding week.
        </p>
        <div className="grid grid-3" style={{ marginTop: 10 }}>
          {meta.hai_pollutants.map((p) => (
            <div key={p} className="slider-row">
              <label style={{ minWidth: 60, marginBottom: 0 }}>{p}</label>
              <input
                type="range" min={0} max={80} step={5}
                value={(adjustments[p] || 0) * 100}
                onChange={(e) => setAdjustments((a) => ({ ...a, [p]: Number(e.target.value) / 100 }))}
                onMouseUp={applyAdjustments}
                onTouchEnd={applyAdjustments}
              />
              <span className="slider-value">{Math.round((adjustments[p] || 0) * 100)}%</span>
            </div>
          ))}
        </div>
      </details>

      {!result ? (
        <p className="caption">Loading forecast...</p>
      ) : !result.ok ? (
        <Banner kind="warn">{(result.messages || []).join(" ")}</Banner>
      ) : (
        <>
          {result.messages.length > 0 && <Banner kind="info">{result.messages.join(" ")}</Banner>}
          {Object.values(result.what_if_applied).some(Boolean) && (
            <Banner kind="success">
              What-if applied: {Object.entries(result.what_if_applied).filter(([, v]) => v).map(([k, v]) => `${k} reduced ${Math.round(v * 100)}%`).join(", ")}. Figures below are counterfactual.
            </Banner>
          )}

          <h2>{city} · {new Date(result.forecast_date).toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" })}</h2>

          <div className="grid grid-4">
            <Metric label="Predicted AQI" value={result.predicted_aqi.toFixed(0)} />
            <Metric label="Predicted band" value={result.predicted_bucket} />
            <Metric label="Confidence" value={result.confidence !== null ? `${Math.round(result.confidence * 100)}%` : "n/a"} />
            <Metric label={`HAI (${meta.cohort_labels[cohort]})`} value={result.cohort.hai.toFixed(0)} help={result.cohort.rationale} />
          </div>

          <div
            style={{ background: bandColour, color: "#11151c", padding: "16px 20px", borderRadius: 10, margin: "14px 0" }}
          >
            <strong style={{ fontSize: "1.15rem" }}>{band} — {meta.cohort_labels[cohort]}</strong>
            <p style={{ margin: "6px 0 0" }}>{result.advisory.text}</p>
          </div>

          <div className="grid grid-1-4">
            <div>
              <h3>History and forecast</h3>
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={[...chartData, { date: forecastPoint.date }]}>
                  <CartesianGrid stroke="#2a2f3a" />
                  <XAxis dataKey="date" tick={{ fill: "#9aa1ad", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#9aa1ad", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
                  <Legend />
                  <Line type="monotone" dataKey="observed" name="Observed AQI" stroke="#56B4E9" dot={{ r: 3 }} />
                  <ReferenceDot x={forecastPoint.date} y={forecastPoint.value} r={7} fill="#D55E00" stroke="none" label={{ value: "Forecast", position: "top", fill: "#D55E00", fontSize: 11 }} />
                  {result.actual_next_aqi !== null && (
                    <ReferenceDot x={forecastPoint.date} y={result.actual_next_aqi} r={6} fill="none" stroke="#009E73" strokeWidth={3} />
                  )}
                </LineChart>
              </ResponsiveContainer>

              <h3>Predicted band probability</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={distributionData} layout="vertical" margin={{ left: 40 }}>
                  <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fill: "#9aa1ad", fontSize: 11 }} />
                  <YAxis type="category" dataKey="bucket" tick={{ fill: "#9aa1ad", fontSize: 11 }} width={90} />
                  <Tooltip formatter={(v) => `${Math.round(v * 100)}%`} contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
                  <Bar dataKey="probability">
                    {distributionData.map((d) => (
                      <Cell key={d.bucket} fill={BUCKET_COLOUR[d.bucket]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div>
              <h3>Observed today ({result.date})</h3>
              <Table
                columns={["Pollutant", "Value", "Unit"]}
                rows={Object.entries(result.observed_today).map(([p, v]) => ({
                  Pollutant: p, Value: v, Unit: meta.pollutant_units[p] || "",
                }))}
              />

              {result.safe_window && (
                <Banner kind="info" icon="🕒">
                  <strong>Cleanest outdoor window:</strong> {result.safe_window} ({result.season})
                </Banner>
              )}

              <h3>Health Advisory Index across all cohorts</h3>
              <Table
                columns={["Cohort", "HAI", "Band"]}
                rows={[...result.all_cohorts].sort((a, b) => b.hai - a.hai).map((c) => ({
                  Cohort: c.cohort_label, HAI: c.hai, Band: c.band,
                }))}
              />
              <p className="caption">The spread across this table is the information a single population-average AQI discards.</p>

              {result.drift.n_flagged > 0 && (
                <Banner kind="warn" icon="📉">
                  <strong>Input drift check.</strong> {result.drift.verdict} Flagged:{" "}
                  {result.drift.flagged.map((f) => `${f.pollutant} (z = ${f.z_score})`).join(", ")}
                </Banner>
              )}

              {result.actual_next_aqi !== null && (
                <p>
                  Actual next-day AQI <strong>{result.actual_next_aqi.toFixed(0)}</strong> ({result.actual_next_bucket}).
                  Forecast error <strong>{(result.predicted_aqi - result.actual_next_aqi > 0 ? "+" : "") + (result.predicted_aqi - result.actual_next_aqi).toFixed(0)}</strong> AQI points.
                </p>
              )}
            </div>
          </div>

          <p className="footer-note">
            Regression: {result.models.regression} · Classification: {result.models.classification}
          </p>
          <Banner kind="warn" icon="⚠">
            <strong>Disclaimer.</strong> {result.advisory.disclaimer}
          </Banner>
        </>
      )}
    </div>
  );
}
