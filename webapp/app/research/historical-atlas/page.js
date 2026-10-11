"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, ReferenceLine,
} from "recharts";
import { Metric, Banner, Table, Loading, Badge, SectionTitle } from "../../components/ui";
import { PALETTE, axisTick, tooltipProps } from "../../components/theme";

const TABS = ["Archetypes", "Ranked risk", "Seasonality", "Festival impact", "COVID-19 lockdown"];

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
    ]).then(([clustering, eda, divergence, rankedRisk, seasonalHeatmap, safeWindows, meta]) =>
      setData({ clustering, eda, divergence, rankedRisk, seasonalHeatmap, safeWindows, meta })
    );
  }, []);

  if (!data) return <><p className="research-notice">HISTORICAL RESEARCH · 2015–2020 DATA · NOT CURRENT AIR QUALITY</p><Loading /></>;

  return (
    <div><p className="research-notice" role="note">HISTORICAL REPLAY — NOT CURRENT AIR QUALITY. Legacy model / research record: 2015–2020, original training cities. SHAP shows model attribution, not causality.</p>
      <span className="eyebrow">Unsupervised structure and event analysis</span>
      <h1>City Risk Atlas</h1>

      <div className="tabs">
        {TABS.map((t, i) => (
          <button key={t} className={i === tab ? "active" : ""} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ArchetypesTab clustering={data.clustering} />}
      {tab === 1 && <RankedRiskTab rankedRisk={data.rankedRisk} divergence={data.divergence} />}
      {tab === 2 && <SeasonalityTab {...data} />}
      {tab === 3 && <FestivalTab eda={data.eda} />}
      {tab === 4 && <LockdownTab eda={data.eda} />}
    </div>
  );
}

function ArchetypesTab({ clustering }) {
  return (
    <div>
      <SectionTitle caption="Cities are clustered on the shape of their pollutant mix rather than its magnitude, so the partition separates kinds of problem from degrees of severity. Each archetype maps to a different policy lever.">
        Pollution archetypes discovered without supervision
      </SectionTitle>

      {clustering.archetypes.map((entry, i) => (
        <div key={entry.archetype} className="card">
          <div className="grid grid-1-4">
            <div>
              <h3 style={{ marginTop: 0 }}>{entry.archetype}</h3>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                <Badge colour={PALETTE[i % PALETTE.length]}>{entry.defining_pollutant} led</Badge>
                <Badge>{entry.burden_level}</Badge>
                <Badge>mean AQI {entry.mean_aqi}</Badge>
              </div>
              <p className="caption" style={{ marginBottom: 10 }}>
                Leading pollutant scores +{entry.defining_pollutant_shape_score} against this
                cluster&apos;s own mean; overall level z = {entry.mean_level_z.toFixed(2)}.
              </p>
              <p style={{ marginBottom: 10 }}>
                <strong>{entry.n_cities} cities.</strong> {entry.cities.join(", ")}
              </p>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>
                <strong>Policy lever.</strong> {entry.policy_lever}
              </p>
            </div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart
                data={Object.entries(entry.composition_profile).map(([k, v]) => ({ pollutant: k, z: v }))}
                margin={{ top: 16, right: 6, left: -14, bottom: 0 }}
              >
                <CartesianGrid vertical={false} />
                <XAxis dataKey="pollutant" tick={axisTick} tickLine={false} axisLine={false} />
                <YAxis tick={axisTick} tickLine={false} axisLine={false} />
                <Tooltip {...tooltipProps} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.22)" />
                <Bar dataKey="z" name="z minus cluster mean" radius={[5, 5, 0, 0]}>
                  {Object.entries(entry.composition_profile).map(([k, v]) => (
                    <Cell key={k} fill={v >= 0 ? PALETTE[i % PALETTE.length] : "rgba(255,255,255,0.18)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}

      <details className="card">
        <summary>How the number of archetypes was chosen</summary>
        <p style={{ marginTop: 12 }}>{clustering.k_selection.selection_rule}</p>
        <p className="caption"><em>{clustering.k_selection.power_caveat}</em></p>
        <Table rows={clustering.k_selection.candidates} />
        <p style={{ marginBottom: 0 }}>
          <strong>Agreement between algorithms.</strong> {clustering.algorithm_agreement.interpretation}
        </p>
      </details>
    </div>
  );
}

function RankedRiskTab({ rankedRisk, divergence }) {
  return (
    <div>
      <SectionTitle caption="The cohort columns show how the advisory burden differs within the same city. The gap between the healthy-adult column and the cardiac column is what a single population-average index hides.">
        Ranked risk table
      </SectionTitle>
      <Table rows={rankedRisk} heat={["Mean AQI", "Days Poor or worse (%)", "Days Severe (%)"]} />

      {divergence && (
        <>
          <SectionTitle>Cohort divergence from the official AQI</SectionTitle>
          <Table
            rows={divergence.per_cohort.map((entry) => ({
              Cohort: entry.cohort_label,
              "Mean HAI": entry.mean_hai,
              "Mean AQI / 5": entry.mean_aqi_rescaled,
              "Mean uplift": entry.mean_uplift_points,
              "Band differs (%)": entry.pct_band_differs_from_aqi,
              "Stricter (%)": entry.pct_band_stricter_than_aqi,
            }))}
            heat={["Band differs (%)", "Stricter (%)"]}
          />
        </>
      )}
    </div>
  );
}

function SeasonalityTab({ eda, seasonalHeatmap, safeWindows, meta }) {
  const flat = seasonalHeatmap.values.flat().filter((v) => v !== null);
  const min = Math.min(...flat);
  const max = Math.max(...flat);

  const shade = (v) => {
    if (v === null) return "transparent";
    const t = (v - min) / (max - min || 1);
    // Viridis-like ramp, dark blue → teal → yellow
    const stops = [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]];
    const pos = t * (stops.length - 1);
    const i = Math.min(Math.floor(pos), stops.length - 2);
    const f = pos - i;
    const c = stops[i].map((s, n) => Math.round(s + (stops[i + 1][n] - s) * f));
    return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  };

  return (
    <div>
      <SectionTitle caption="Mean AQI by city and calendar month. Northern cities show an extreme winter maximum while southern coastal cities stay comparatively flat, which is why the models carry a city interaction.">
        Seasonality
      </SectionTitle>

      <div className="table-wrap">
        <table className="heatmap">
          <thead>
            <tr><th>City</th>{seasonalHeatmap.months.map((m) => <th key={m} style={{ textAlign: "center" }}>{m}</th>)}</tr>
          </thead>
          <tbody>
            {seasonalHeatmap.cities.map((city, i) => (
              <tr key={city}>
                <td>{city}</td>
                {seasonalHeatmap.values[i].map((v, j) => {
                  const t = v === null ? 0 : (v - min) / (max - min || 1);
                  return (
                    <td key={j} style={{ background: shade(v), color: t > 0.6 ? "#0b0e15" : "#eef1f6", fontWeight: 500 }}>
                      {v === null ? "–" : Math.round(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {eda && (
        <>
          <div className="grid grid-4" style={{ marginTop: 18 }}>
            {meta.season_order.map((season) => (
              <Metric
                key={season}
                label={season}
                value={(eda.seasonal.seasonal_mean_aqi[season] ?? NaN).toFixed(0)}
                delta={season === eda.seasonal.worst_season ? "worst season" : season === eda.seasonal.best_season ? "cleanest season" : undefined}
                deltaGood={season === eda.seasonal.best_season}
              />
            ))}
          </div>
          <p className="caption">
            A <strong>{eda.seasonal.seasonal_ratio}-fold</strong> swing within the same cities between{" "}
            {eda.seasonal.best_season} and {eda.seasonal.worst_season}.
          </p>
        </>
      )}

      <SectionTitle>Cleanest outdoor window by city and season</SectionTitle>
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
  const profile = Object.entries(festival.profile)
    .map(([k, v]) => ({ offset: Number(k), aqi: v }))
    .sort((a, b) => a.offset - b.offset);

  return (
    <div>
      <SectionTitle caption={`Baseline: ${festival.baseline_definition}. Orange bars are significant at the 5% level under a one-sided Mann-Whitney U test. These spikes are real signal and are never removed as outliers; the cleaning rule explicitly exempts documented event windows.`}>
        Festival impact: the Diwali window
      </SectionTitle>

      <div className="grid grid-3">
        <Metric hero label="National uplift" value={`${festival.national_uplift_pct > 0 ? "+" : ""}${festival.national_uplift_pct.toFixed(1)}%`} deltaGood={false} delta="against a matched seasonal baseline" />
        <Metric hero label="Cities with significant uplift" value={`${festival.n_cities_significant_uplift} / ${festival.per_city.length}`} delta="one-sided Mann-Whitney U, α = 0.05" />
        <Metric hero label="Peak" value={`${festival.peak_offset_days > 0 ? "+" : ""}${festival.peak_offset_days} d`} delta="from Diwali night" />
      </div>

      <div className="card" style={{ padding: "18px 10px 8px" }}>
        <ResponsiveContainer width="100%" height={430}>
          <BarChart data={table} layout="vertical" margin={{ left: 40, right: 54, top: 6 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="city" tick={axisTick} tickLine={false} axisLine={false} width={104} />
            <Tooltip {...tooltipProps} formatter={(v) => `${v.toFixed(1)}%`} />
            <Bar dataKey="uplift_pct" name="Change vs baseline" radius={[0, 5, 5, 0]} label={{ position: "right", fill: "#b6bfcd", fontSize: 11, formatter: (v) => `${v > 0 ? "+" : ""}${Math.round(v)}%` }}>
              {table.map((row, i) => <Cell key={i} fill={row.significant_at_0_05 ? "#D55E00" : "rgba(86,180,233,0.55)"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h3>Daily profile around Diwali</h3>
      <div className="card" style={{ padding: "18px 10px 8px" }}>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={profile} margin={{ top: 6, right: 18, left: 0 }}>
            <defs>
              <linearGradient id="festFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#E69F00" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#E69F00" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="offset" tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis tick={axisTick} tickLine={false} axisLine={false} width={42} />
            <Tooltip {...tooltipProps} labelFormatter={(v) => `${v > 0 ? "+" : ""}${v} days from Diwali`} />
            <ReferenceLine x={0} stroke="#D55E00" strokeWidth={2} label={{ value: "Diwali", fill: "#D55E00", fontSize: 11, position: "top" }} />
            <Area type="monotone" dataKey="aqi" name="Mean AQI" stroke="#E69F00" strokeWidth={2.4} fill="url(#festFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function LockdownTab({ eda }) {
  if (!eda) return <Banner kind="info">Exploratory statistics not found.</Banner>;
  const covid = eda.covid;
  const table = [...covid.per_city].sort((a, b) => a.change_pct - b.change_pct);

  return (
    <div>
      <SectionTitle caption={`${covid.test} This episode is the only abrupt, broad emission reduction in the record, and it is the empirical anchor against which the Policy Simulator's whole-economy scenarios can be checked.`}>
        The 2020 lockdown as a natural experiment
      </SectionTitle>

      <div className="grid grid-4">
        <Metric hero label="Mean AQI before" value={covid.national_mean_before.toFixed(0)} />
        <Metric hero label="During lockdown" value={covid.national_mean_during.toFixed(0)} />
        <Metric hero label="Change" value={`${covid.national_change_pct.toFixed(1)}%`} delta="national mean" deltaGood />
        <Metric hero label="Significant declines" value={`${covid.n_cities_significant_decline} / ${covid.per_city.length}`} delta="cities" />
      </div>

      <div className="card" style={{ padding: "18px 10px 8px" }}>
        <ResponsiveContainer width="100%" height={430}>
          <BarChart data={table} layout="vertical" margin={{ left: 40, right: 54, top: 6 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="city" tick={axisTick} tickLine={false} axisLine={false} width={104} />
            <Tooltip {...tooltipProps} formatter={(v) => `${v.toFixed(1)}%`} />
            <Bar dataKey="change_pct" name="Change vs preceding 60 days" radius={[0, 5, 5, 0]} label={{ position: "right", fill: "#b6bfcd", fontSize: 11, formatter: (v) => `${Math.round(v)}%` }}>
              {table.map((row, i) => <Cell key={i} fill={row.change_pct < 0 ? "#009E73" : "#D55E00"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <Banner kind="info">
        <strong>How this is handled in modelling.</strong> 2020 is a genuine regime change rather
        than noise, so it is kept in the data rather than deleted, and test-set error is reported
        separately for the lockdown period as a stress test. A lockdown flag was offered to the
        models, but feature selection did not retain it.
      </Banner>
    </div>
  );
}
