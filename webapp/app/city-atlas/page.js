"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, ReferenceLine,
} from "recharts";
import { Metric, Banner, Table } from "../components/ui";

const TABS = ["Archetypes", "Ranked risk", "Seasonality", "Festival impact", "COVID-19 lockdown"];
const PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"];

export default function CityAtlasPage() {
  const [tab, setTab] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/data/evaluation_clustering.json").then((r) => r.json()),
      fetch("/data/eda_statistics.json").then((r) => r.json()),
      fetch("/data/hai_divergence.json").then((r) => r.json()),
      fetch("/data/ranked_risk_table.json").then((r) => r.json()),
      fetch("/data/seasonal_heatmap.json").then((r) => r.json()),
      fetch("/data/safe_windows.json").then((r) => r.json()),
      fetch("/data/meta.json").then((r) => r.json()),
    ]).then(([clustering, eda, divergence, rankedRisk, seasonalHeatmap, safeWindows, meta]) => {
      setData({ clustering, eda, divergence, rankedRisk, seasonalHeatmap, safeWindows, meta });
    });
  }, []);

  if (!data) return <p className="caption">Loading...</p>;
  const { clustering, eda, divergence, rankedRisk, seasonalHeatmap, safeWindows, meta } = data;

  return (
    <div>
      <h1>City Risk Atlas</h1>
      <div className="tabs">
        {TABS.map((t, i) => (
          <button key={t} className={i === tab ? "active" : ""} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ArchetypesTab clustering={clustering} />}
      {tab === 1 && <RankedRiskTab rankedRisk={rankedRisk} divergence={divergence} />}
      {tab === 2 && <SeasonalityTab eda={eda} seasonalHeatmap={seasonalHeatmap} safeWindows={safeWindows} meta={meta} />}
      {tab === 3 && <FestivalTab eda={eda} />}
      {tab === 4 && <LockdownTab eda={eda} />}
    </div>
  );
}

function ArchetypesTab({ clustering }) {
  return (
    <div>
      <h2>Pollution archetypes discovered without supervision</h2>
      <p className="caption">
        Cities are clustered on the shape of their pollutant mix rather than its magnitude, so
        the partition separates kinds of problem from degrees of severity. Each archetype maps to
        a different policy lever.
      </p>
      {clustering.archetypes.map((entry, i) => (
        <div key={entry.archetype} className="card">
          <div className="grid grid-1-4">
            <div>
              <h3>{entry.archetype}</h3>
              <p><strong>Leading pollutant:</strong> {entry.defining_pollutant} (+{entry.defining_pollutant_shape_score} vs cluster mean)</p>
              <p><strong>Overall burden level:</strong> {entry.burden_level} (z = {entry.mean_level_z.toFixed(2)})</p>
              <p><strong>Mean AQI:</strong> {entry.mean_aqi}</p>
              <p><strong>Cities ({entry.n_cities}):</strong> {entry.cities.join(", ")}</p>
              <p><strong>Policy lever.</strong> {entry.policy_lever}</p>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={Object.entries(entry.composition_profile).map(([k, v]) => ({ pollutant: k, z: v }))}>
                <CartesianGrid stroke="#2a2f3a" />
                <XAxis dataKey="pollutant" tick={{ fill: "#9aa1ad", fontSize: 11 }} />
                <YAxis tick={{ fill: "#9aa1ad", fontSize: 11 }} label={{ value: "z minus cluster mean", angle: -90, position: "insideLeft", fill: "#9aa1ad", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
                <Bar dataKey="z" fill={PALETTE[i % PALETTE.length]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}

      <details className="card">
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>How the number of archetypes was chosen</summary>
        <p>{clustering.k_selection.selection_rule}</p>
        <p className="caption"><em>{clustering.k_selection.power_caveat}</em></p>
        <Table rows={clustering.k_selection.candidates} />
        <p><strong>Agreement between algorithms.</strong> {clustering.algorithm_agreement.interpretation}</p>
      </details>
    </div>
  );
}

function RankedRiskTab({ rankedRisk, divergence }) {
  return (
    <div>
      <h2>Ranked risk table</h2>
      <Table rows={rankedRisk} />
      <p className="caption">
        The last four columns show how the advisory burden differs by cohort within the same
        city. The gap between the healthy-adult column and the cardiac column is what a single
        population-average index hides.
      </p>

      {divergence && (
        <>
          <h3>Cohort divergence from the official AQI</h3>
          <Table
            rows={divergence.per_cohort.map((entry) => ({
              Cohort: entry.cohort_label,
              "Mean HAI": entry.mean_hai,
              "Mean AQI / 5": entry.mean_aqi_rescaled,
              "Mean uplift": entry.mean_uplift_points,
              "Band differs from AQI (%)": entry.pct_band_differs_from_aqi,
              "Stricter than AQI (%)": entry.pct_band_stricter_than_aqi,
            }))}
          />
        </>
      )}
    </div>
  );
}

function SeasonalityTab({ eda, seasonalHeatmap, safeWindows, meta }) {
  const max = Math.max(...seasonalHeatmap.values.flat().filter((v) => v !== null));
  return (
    <div>
      <h2>Seasonality</h2>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>City</th>{seasonalHeatmap.months.map((m) => <th key={m}>{m}</th>)}</tr>
          </thead>
          <tbody>
            {seasonalHeatmap.cities.map((city, i) => (
              <tr key={city}>
                <td>{city}</td>
                {seasonalHeatmap.values[i].map((v, j) => (
                  <td key={j} style={{ background: v === null ? "transparent" : `rgba(86,180,233,${0.15 + 0.7 * (v / max)})` }}>
                    {v === null ? "-" : v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {eda && (
        <>
          <div className="grid grid-4" style={{ marginTop: 16 }}>
            {meta.season_order.map((season) => (
              <Metric key={season} label={season} value={(eda.seasonal.seasonal_mean_aqi[season] ?? NaN).toFixed(0)} />
            ))}
          </div>
          <p className="caption">
            Worst season: <strong>{eda.seasonal.worst_season}</strong>; cleanest: <strong>{eda.seasonal.best_season}</strong>;
            a {eda.seasonal.seasonal_ratio}-fold swing within the same cities.
          </p>
        </>
      )}

      <h3>Cleanest outdoor window by city and season</h3>
      {safeWindows && !safeWindows.degraded ? (
        <>
          <Table
            rows={Object.entries(safeWindows.per_city).sort().map(([city, entry]) => {
              const row = { City: city, "All year": entry.all_year.label };
              meta.season_order.forEach((season) => {
                row[season] = entry.by_season?.[season]?.label || "n/a";
              });
              row["Exposure cut (%)"] = entry.all_year.reduction_vs_day_mean_pct;
              return row;
            })}
          />
          <p className="caption">{safeWindows.why_not_the_supplied_hourly_aqi?.explanation}</p>
        </>
      ) : (
        <Banner kind="warn">{safeWindows?.reason || "Hourly data unavailable."}</Banner>
      )}
    </div>
  );
}

function FestivalTab({ eda }) {
  if (!eda) return <Banner kind="info">Exploratory statistics not found.</Banner>;
  const festival = eda.festival;
  const table = [...festival.per_city].sort((a, b) => b.uplift_pct - a.uplift_pct);
  const profile = Object.entries(festival.profile).map(([k, v]) => ({ offset: Number(k), aqi: v })).sort((a, b) => a.offset - b.offset);

  return (
    <div>
      <h2>Festival impact: the Diwali window</h2>
      <div className="grid grid-3">
        <Metric label="National uplift" value={`${festival.national_uplift_pct > 0 ? "+" : ""}${festival.national_uplift_pct.toFixed(1)}%`} />
        <Metric label="Cities with significant uplift" value={`${festival.n_cities_significant_uplift} of ${festival.per_city.length}`} />
        <Metric label="Peak" value={`${festival.peak_offset_days > 0 ? "+" : ""}${festival.peak_offset_days} days from Diwali`} />
      </div>

      <ResponsiveContainer width="100%" height={440}>
        <BarChart data={table} layout="vertical" margin={{ left: 90 }}>
          <XAxis type="number" tick={{ fill: "#9aa1ad", fontSize: 11 }} label={{ value: "Change vs seasonal baseline (%)", position: "insideBottom", offset: -5, fill: "#9aa1ad", fontSize: 10 }} />
          <YAxis type="category" dataKey="city" tick={{ fill: "#9aa1ad", fontSize: 11 }} width={90} />
          <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
          <Bar dataKey="uplift_pct">
            {table.map((row, i) => <Cell key={i} fill={row.significant_at_0_05 ? "#D55E00" : "#56B4E9"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="caption">
        Baseline: {festival.baseline_definition}. Orange bars are significant at the 5% level.
        These spikes are real signal and are never removed as outliers.
      </p>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={profile}>
          <CartesianGrid stroke="#2a2f3a" />
          <XAxis dataKey="offset" tick={{ fill: "#9aa1ad", fontSize: 11 }} label={{ value: "Days from Diwali", position: "insideBottom", offset: -5, fill: "#9aa1ad", fontSize: 10 }} />
          <YAxis tick={{ fill: "#9aa1ad", fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
          <ReferenceLine x={0} stroke="#D55E00" label={{ value: "Diwali", fill: "#D55E00", fontSize: 11 }} />
          <Line type="monotone" dataKey="aqi" stroke="#56B4E9" strokeWidth={2.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function LockdownTab({ eda }) {
  if (!eda) return <Banner kind="info">Exploratory statistics not found.</Banner>;
  const covid = eda.covid;
  const table = [...covid.per_city].sort((a, b) => a.change_pct - b.change_pct);

  return (
    <div>
      <h2>The 2020 lockdown as a natural experiment</h2>
      <div className="grid grid-4">
        <Metric label="National mean AQI before" value={covid.national_mean_before.toFixed(0)} />
        <Metric label="During lockdown" value={covid.national_mean_during.toFixed(0)} />
        <Metric label="Change" value={`${covid.national_change_pct > 0 ? "+" : ""}${covid.national_change_pct.toFixed(1)}%`} />
        <Metric label="Cities significantly declining" value={`${covid.n_cities_significant_decline} of ${covid.per_city.length}`} />
      </div>

      <ResponsiveContainer width="100%" height={440}>
        <BarChart data={table} layout="vertical" margin={{ left: 90 }}>
          <XAxis type="number" tick={{ fill: "#9aa1ad", fontSize: 11 }} label={{ value: "Change vs preceding 60 days (%)", position: "insideBottom", offset: -5, fill: "#9aa1ad", fontSize: 10 }} />
          <YAxis type="category" dataKey="city" tick={{ fill: "#9aa1ad", fontSize: 11 }} width={90} />
          <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
          <Bar dataKey="change_pct">
            {table.map((row, i) => <Cell key={i} fill={row.change_pct < 0 ? "#009E73" : "#D55E00"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="caption">{covid.test} This episode is the only abrupt, broad emission reduction in the record.</p>
      <p>
        <strong>How this is handled in modelling.</strong> 2020 is modelled with an explicit
        lockdown flag rather than deleted, and test-set error is reported separately for the
        lockdown period as a stress test.
      </p>
    </div>
  );
}
