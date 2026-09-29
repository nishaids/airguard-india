"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  PieChart, Pie,
} from "recharts";
import { Metric, Banner, Table } from "../components/ui";

export default function PolicySimulatorPage() {
  const [meta, setMeta] = useState(null);
  const [stored, setStored] = useState(null);
  const [preset, setPreset] = useState("Custom");
  const [reductions, setReductions] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch("/data/meta.json").then((r) => r.json()),
      fetch("/data/policy_simulation.json").then((r) => r.json()),
    ]).then(([m, s]) => {
      setMeta(m);
      setStored(s);
      const zero = {};
      m.hai_pollutants.forEach((p) => (zero[p] = 0));
      setReductions(zero);
    });
  }, []);

  const applyPreset = (name) => {
    setPreset(name);
    if (name === "Custom") return;
    const scenario = stored.scenarios.find((s) => s.name === name);
    if (scenario) setReductions({ ...reductions, ...scenario.reductions });
  };

  const runSimulation = async () => {
    const active = Object.fromEntries(Object.entries(reductions).filter(([, v]) => v > 0));
    if (Object.keys(active).length === 0) {
      setResult(null);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/policy_simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reductions: active }),
      });
      setResult(await res.json());
    } finally {
      setLoading(false);
    }
  };

  if (!meta || !stored) return <p className="caption">Loading...</p>;

  const activeCount = Object.values(reductions).filter((v) => v > 0).length;
  const presetContext = preset !== "Custom" ? stored.scenarios.find((s) => s.name === preset)?.context : null;

  return (
    <div>
      <h1>Policy Simulator</h1>
      <p className="caption">
        Reduce pollutant concentrations and the entire historical record is re-scored from first
        principles: new sub-indices, new AQI, new bands, and new cohort Health Advisory Index
        values for all seven groups.
      </p>

      <div className="card">
        <strong>What this tool does and does not claim</strong>
        <p style={{ margin: "6px 0 0" }}>{stored.what_this_is_not}</p>
      </div>

      <h2>Set the reduction</h2>
      <label>Start from a preset</label>
      <select value={preset} onChange={(e) => applyPreset(e.target.value)}>
        <option value="Custom">Custom</option>
        {stored.scenarios.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
      </select>
      {presetContext && <Banner kind="info">{presetContext}</Banner>}

      <div className="grid grid-3" style={{ marginTop: 14 }}>
        {meta.hai_pollutants.map((p) => (
          <div key={p} className="slider-row">
            <label style={{ minWidth: 60, marginBottom: 0 }}>{p}</label>
            <input
              type="range" min={0} max={80} step={5}
              value={(reductions[p] || 0) * 100}
              onChange={(e) => { setPreset("Custom"); setReductions((r) => ({ ...r, [p]: Number(e.target.value) / 100 })); }}
              onMouseUp={runSimulation}
              onTouchEnd={runSimulation}
            />
            <span className="slider-value">{Math.round((reductions[p] || 0) * 100)}%</span>
          </div>
        ))}
      </div>

      {activeCount === 0 ? (
        <Banner kind="info" icon="👆">Set at least one reduction above to run a scenario.</Banner>
      ) : loading ? (
        <p className="caption">Re-scoring the historical record...</p>
      ) : result?.ok ? (
        <SimResult result={result.result} stored={stored} />
      ) : result && !result.ok ? (
        <Banner kind="warn">{(result.messages || []).join(" ")}</Banner>
      ) : null}

      <details className="card" style={{ marginTop: 20 }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>Scenarios reported in the Review 3 document</summary>
        <Table
          rows={stored.scenarios.map((s) => ({
            Scenario: s.name,
            "Mean AQI change (%)": s.result.aqi.mean_change_pct,
            "Unsafe days removed (%)": s.result.unsafe_days.reduction_pct,
            "Advisory-days averted": s.result.cohort_advisory_days.total_averted_across_cohorts,
          }))}
        />
      </details>
    </div>
  );
}

function SimResult({ result, stored }) {
  const cohorts = result.cohort_advisory_days.per_cohort;
  const migration = result.band_migration;
  const cityTable = [...result.per_city].sort((a, b) => b.pct_days_improved_band - a.pct_days_improved_band);
  const anchor = stored.lockdown_anchor;

  return (
    <div>
      <h2>Result</h2>
      <div className="grid grid-4">
        <Metric label="Mean AQI" value={result.aqi.mean_after.toFixed(1)} delta={`${result.aqi.mean_change_pct.toFixed(1)}%`} deltaGood={true} />
        <Metric label="Unsafe days" value={result.unsafe_days.after.toLocaleString()} delta={`-${result.unsafe_days.removed.toLocaleString()} (${result.unsafe_days.reduction_pct.toFixed(1)}%)`} deltaGood={true} />
        <Metric label="City-days improving a band" value={result.band_migration.days_improved.toLocaleString()} delta={`${result.band_migration.pct_improved.toFixed(1)}% of days`} deltaGood={true} />
        <Metric label="Cohort advisory-days averted" value={result.cohort_advisory_days.total_averted_across_cohorts.toLocaleString()} />
      </div>

      <div className="grid grid-1-1_5" style={{ marginTop: 16 }}>
        <div>
          <h3>Cohort advisory burden, before and after</h3>
          <ResponsiveContainer width="100%" height={380}>
            <BarChart data={cohorts.map((c) => ({ name: c.cohort_label, Before: c.restrictive_days_before, After: c.restrictive_days_after }))} layout="vertical" margin={{ left: 100 }}>
              <XAxis type="number" tick={{ fill: "#9aa1ad", fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#9aa1ad", fontSize: 11 }} width={100} />
              <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
              <Legend />
              <Bar dataKey="Before" fill="#D55E00" />
              <Bar dataKey="After" fill="#009E73" />
            </BarChart>
          </ResponsiveContainer>
          <Table
            rows={cohorts.map((c) => ({
              Cohort: c.cohort_label, Before: c.restrictive_days_before, After: c.restrictive_days_after,
              Averted: c.advisory_days_averted, "Reduction (%)": c.reduction_pct,
            }))}
          />
        </div>

        <div>
          <h3>Band migration</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={[
                  { name: "Improved a band", value: migration.days_improved, fill: "#009E73" },
                  { name: "Unchanged", value: migration.days_unchanged, fill: "#56B4E9" },
                  { name: "Worsened", value: migration.days_worsened, fill: "#D55E00" },
                ]}
                dataKey="value" innerRadius={55} outerRadius={95} label
              />
              <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
            </PieChart>
          </ResponsiveContainer>

          <h3>Effect by city</h3>
          <ResponsiveContainer width="100%" height={420}>
            <BarChart data={cityTable} layout="vertical" margin={{ left: 90 }}>
              <XAxis type="number" tick={{ fill: "#9aa1ad", fontSize: 11 }} label={{ value: "Days improving a band (%)", position: "insideBottom", offset: -5, fill: "#9aa1ad", fontSize: 10 }} />
              <YAxis type="category" dataKey="city" tick={{ fill: "#9aa1ad", fontSize: 11 }} width={90} />
              <Tooltip contentStyle={{ background: "#161a23", border: "1px solid #2a2f3a" }} />
              <Bar dataKey="pct_days_improved_band" fill="#56B4E9" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {anchor && (
        <>
          <h2>Sanity check against a real emission reduction</h2>
          <div className="grid grid-3">
            <Metric label="Measured lockdown effect" value={`${anchor.measured_aqi_change_pct.toFixed(1)}%`} />
            <Metric label="This scenario" value={`${result.aqi.mean_change_pct.toFixed(1)}%`} />
            <Metric label="Cities with significant measured decline" value={anchor.cities_with_significant_decline} />
          </div>
          <p className="caption">{anchor.use}</p>
        </>
      )}
    </div>
  );
}
