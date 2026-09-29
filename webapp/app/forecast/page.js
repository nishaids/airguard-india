"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Area, AreaChart, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceDot, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";
import { Metric, Banner, Table, Loading, Badge } from "../components/ui";
import { BAND_COLOUR, BUCKET_COLOUR, axisTick, tooltipProps } from "../components/theme";

export default function ForecastPage() {
  const [meta, setMeta] = useState(null);
  const [city, setCity] = useState("");
  const [cohort, setCohort] = useState("healthy_adult");
  const [date, setDate] = useState("");
  const [adjustments, setAdjustments] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const adjustmentsRef = useRef({});

  useEffect(() => {
    adjustmentsRef.current = adjustments;
  }, [adjustments]);

  useEffect(() => {
    fetch("/data/meta.json")
      .then((r) => r.json())
      .then((m) => {
        const initialCity = m.cities.includes("Delhi") ? "Delhi" : m.cities[0];
        const zero = {};
        m.hai_pollutants.forEach((p) => (zero[p] = 0));
        setAdjustments(zero);
        adjustmentsRef.current = zero;
        setCity(initialCity);
        setDate(m.date_bounds[initialCity].max);
        setMeta(m);
      });
  }, []);

  const runForecast = useCallback(
    async (overrideCity, overrideDate, overrideCohort) => {
      const targetCity = overrideCity ?? city;
      const targetDate = overrideDate ?? date;
      const targetCohort = overrideCohort ?? cohort;
      if (!targetCity || !targetDate) return;
      setLoading(true);
      setFailed(false);
      try {
        const res = await fetch("/api/forecast", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            city: targetCity,
            date: targetDate,
            cohort: targetCohort,
            adjustments: adjustmentsRef.current,
          }),
        });
        setResult(await res.json());
      } catch {
        setFailed(true);
      } finally {
        setLoading(false);
      }
    },
    [city, date, cohort]
  );

  useEffect(() => {
    if (meta && city && date) runForecast();
  }, [meta, city, date, cohort, runForecast]);

  const chartData = useMemo(() => {
    if (!result?.ok) return [];
    const history = (result.history || []).map((row) => ({ date: row.Date, observed: row.AQI }));
    return [...history, { date: result.forecast_date, predicted: result.predicted_aqi }];
  }, [result]);

  const distributionData = useMemo(() => {
    if (!result?.ok || !meta) return [];
    return meta.aqi_buckets.map((b) => ({ bucket: b, probability: result.bucket_distribution[b] || 0 }));
  }, [result, meta]);

  if (!meta) return <Loading />;

  const bounds = city ? meta.date_bounds[city] : null;
  const ok = result?.ok;
  const band = ok ? result.cohort.band : null;
  const bandColour = BAND_COLOUR[band] || "#56B4E9";
  const activeWhatIf = ok ? Object.entries(result.what_if_applied).filter(([, v]) => v) : [];

  return (
    <div>
      <span className="eyebrow">Next-day prediction</span>
      <h1>Forecast</h1>
      <p className="caption" style={{ maxWidth: "76ch" }}>
        Tomorrow&apos;s AQI and band for the selected city, with the advisory the selected cohort
        should actually act on.
      </p>

      <div className="card">
        <div className="grid grid-4">
          <div>
            <label htmlFor="city">City</label>
            <select
              id="city"
              value={city}
              onChange={(e) => {
                const next = e.target.value;
                setCity(next);
                setDate(meta.date_bounds[next].max);
              }}
            >
              {meta.cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="cohort">Cohort</label>
            <select id="cohort" value={cohort} onChange={(e) => setCohort(e.target.value)}>
              {meta.cohorts.map((c) => <option key={c} value={c}>{meta.cohort_labels[c]}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="date">Date</label>
            <input
              id="date"
              type="date"
              value={date}
              min={bounds?.min}
              max={bounds?.max}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div>
            <label>Record coverage</label>
            <p className="mono" style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-soft)" }}>
              {bounds ? `${bounds.min} → ${bounds.max}` : "—"}
            </p>
          </div>
        </div>
      </div>

      <details className="card">
        <summary>What-if: reduce today&apos;s pollutants</summary>
        <p className="caption" style={{ marginTop: 12 }}>
          Reduce today&apos;s measured concentrations and watch the forecast and the advisory
          respond. Lag and rolling features are left untouched, because a what-if about today does
          not rewrite the preceding week.
        </p>
        <div className="grid grid-2" style={{ gap: "0 28px" }}>
          {meta.hai_pollutants.map((p) => (
            <div key={p} className="field-row">
              <label htmlFor={`slider-${p}`}>{p}</label>
              <input
                id={`slider-${p}`}
                type="range"
                min={0}
                max={80}
                step={5}
                value={(adjustments[p] || 0) * 100}
                onChange={(e) => setAdjustments((a) => ({ ...a, [p]: Number(e.target.value) / 100 }))}
                onMouseUp={() => runForecast()}
                onTouchEnd={() => runForecast()}
                onKeyUp={() => runForecast()}
              />
              <span className="slider-value">{Math.round((adjustments[p] || 0) * 100)}%</span>
            </div>
          ))}
        </div>
      </details>

      {failed && (
        <Banner kind="error">
          The forecast service did not respond. The two Python functions only run on Vercel (or via{" "}
          <code>vercel dev</code>); under a plain <code>next dev</code> server the static pages work
          but this endpoint is not served.
        </Banner>
      )}

      {loading && !result && <Loading rows={2} />}

      {result && !ok && !failed && <Banner kind="warn">{(result.messages || []).join(" ")}</Banner>}

      {ok && (
        <div style={{ opacity: loading ? 0.55 : 1, transition: "opacity 0.2s" }}>
          {result.messages.length > 0 && <Banner kind="info">{result.messages.join(" ")}</Banner>}
          {activeWhatIf.length > 0 && (
            <Banner kind="success">
              Counterfactual applied:{" "}
              {activeWhatIf.map(([k, v]) => `${k} reduced ${Math.round(v * 100)}%`).join(", ")}. Every
              figure below reflects that reduction.
            </Banner>
          )}

          <h2 style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            {result.city}
            <span className="caption" style={{ fontSize: "0.95rem" }}>
              forecast for{" "}
              {new Date(result.forecast_date).toLocaleDateString("en-GB", {
                day: "numeric", month: "long", year: "numeric",
              })}
            </span>
          </h2>

          <div className="grid grid-4">
            <Metric hero label="Predicted AQI" value={result.predicted_aqi.toFixed(0)} delta={`observed today ${result.observed_aqi_today?.toFixed(0) ?? "—"}`} />
            <Metric hero label="Predicted band" value={result.predicted_bucket} delta={result.confidence !== null ? `${Math.round(result.confidence * 100)}% confidence` : undefined} />
            <Metric hero label={`HAI · ${meta.cohort_labels[cohort]}`} value={result.cohort.hai.toFixed(0)} delta={band} help={result.cohort.rationale} />
            <Metric hero label="Dominant pollutant" value={result.cohort.dominant_pollutant || "n/a"} delta={result.safe_window ? `cleanest ${result.safe_window}` : undefined} />
          </div>

          <div className="advisory" style={{ "--band-colour": bandColour }}>
            <div className="advisory-band">
              <span className="dot" />
              {band} risk — {meta.cohort_labels[cohort]}
            </div>
            <p>{result.advisory.text}</p>
          </div>

          <div className="grid grid-1-4">
            <div>
              <h3>Thirty days of observed AQI, and tomorrow</h3>
              <div className="card" style={{ padding: "18px 10px 8px" }}>
                <ResponsiveContainer width="100%" height={310}>
                  <AreaChart data={chartData} margin={{ top: 6, right: 16, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="aqiFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#56B4E9" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="#56B4E9" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="date" tick={axisTick} tickLine={false} axisLine={false} minTickGap={28} />
                    <YAxis tick={axisTick} tickLine={false} axisLine={false} width={42} />
                    <Tooltip {...tooltipProps} />
                    <Area
                      type="monotone" dataKey="observed" name="Observed AQI"
                      stroke="#56B4E9" strokeWidth={2} fill="url(#aqiFill)" dot={false} connectNulls
                    />
                    <ReferenceDot
                      x={result.forecast_date} y={result.predicted_aqi} r={6}
                      fill="#D55E00" stroke="#06080c" strokeWidth={2}
                      label={{ value: "forecast", position: "top", fill: "#D55E00", fontSize: 11 }}
                    />
                    {result.actual_next_aqi !== null && (
                      <ReferenceDot
                        x={result.forecast_date} y={result.actual_next_aqi} r={6}
                        fill="none" stroke="#009E73" strokeWidth={2.5}
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <h3>Predicted band probability</h3>
              <div className="card" style={{ padding: "18px 10px 8px" }}>
                <ResponsiveContainer width="100%" height={210}>
                  <BarChart data={distributionData} layout="vertical" margin={{ left: 26, right: 40 }}>
                    <XAxis type="number" domain={[0, 1]} hide />
                    <YAxis type="category" dataKey="bucket" tick={axisTick} tickLine={false} axisLine={false} width={84} />
                    <Tooltip {...tooltipProps} formatter={(v) => `${(v * 100).toFixed(1)}%`} />
                    <Bar dataKey="probability" radius={[0, 6, 6, 0]} label={{ position: "right", fill: "#b6bfcd", fontSize: 11, formatter: (v) => (v > 0.005 ? `${Math.round(v * 100)}%` : "") }}>
                      {distributionData.map((d) => <Cell key={d.bucket} fill={BUCKET_COLOUR[d.bucket]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div>
              <h3>Observed today · {result.date}</h3>
              <Table
                columns={["Pollutant", "Value", "Unit"]}
                rows={Object.entries(result.observed_today).map(([p, v]) => ({
                  Pollutant: p, Value: v, Unit: meta.pollutant_units[p] || "",
                }))}
              />

              {result.safe_window && (
                <Banner kind="info" icon="🕒">
                  <strong>Cleanest outdoor window:</strong> {result.safe_window}{" "}
                  <span className="caption">({result.season})</span>
                </Banner>
              )}

              <h3>Every cohort, same day</h3>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Cohort</th><th>HAI</th><th>Band</th></tr></thead>
                  <tbody>
                    {[...result.all_cohorts].sort((a, b) => b.hai - a.hai).map((c) => (
                      <tr key={c.cohort}>
                        <td>{c.cohort_label}</td>
                        <td className="mono">{c.hai.toFixed(1)}</td>
                        <td><Badge colour={BAND_COLOUR[c.band]}>{c.band}</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="caption">
                The spread across this table is exactly the information a single population-average
                AQI discards.
              </p>

              {result.drift.n_flagged > 0 && (
                <Banner kind="warn" icon="📉">
                  <strong>Input drift.</strong> {result.drift.verdict} Flagged:{" "}
                  {result.drift.flagged.map((f) => `${f.pollutant} (z = ${f.z_score})`).join(", ")}
                </Banner>
              )}

              {result.actual_next_aqi !== null && (
                <div className="card">
                  <h3 style={{ marginTop: 0 }}>What actually happened</h3>
                  <p style={{ margin: 0 }}>
                    Actual next-day AQI <strong>{result.actual_next_aqi.toFixed(0)}</strong> (
                    {result.actual_next_bucket}). Forecast error{" "}
                    <strong className="mono">
                      {result.predicted_aqi - result.actual_next_aqi > 0 ? "+" : ""}
                      {(result.predicted_aqi - result.actual_next_aqi).toFixed(0)}
                    </strong>{" "}
                    AQI points.
                  </p>
                </div>
              )}
            </div>
          </div>

          <p className="footer-note">
            Regression: {result.models.regression} · Classification: {result.models.classification}
          </p>
          <Banner kind="warn">
            <strong>Disclaimer.</strong> {result.advisory.disclaimer}
          </Banner>
        </div>
      )}
    </div>
  );
}
