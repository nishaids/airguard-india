"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  PieChart, Pie,
} from "recharts";
import { Metric, Banner, Table, Loading, SectionTitle } from "../../components/ui";
import { axisTick, tooltipProps } from "../../components/theme";

export default function PolicySimulatorPage() {
  const [meta, setMeta] = useState(null);
  const [stored, setStored] = useState(null);
  const [preset, setPreset] = useState("Custom");
  const [reductions, setReductions] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const reductionsRef = useRef({});

  useEffect(() => {
    reductionsRef.current = reductions;
  }, [reductions]);

  useEffect(() => {
    Promise.all([
      fetch("/data/meta.json").then((r) => r.json()),
      fetch("/data/policy_simulation.json").then((r) => r.json()),
    ]).then(([m, s]) => {
      const zero = {};
      m.hai_pollutants.forEach((p) => (zero[p] = 0));
      setReductions(zero);
      reductionsRef.current = zero;
      setMeta(m);
      setStored(s);
    });
  }, []);

  const runSimulation = useCallback(async () => {
    const active = Object.fromEntries(Object.entries(reductionsRef.current).filter(([, v]) => v > 0));
    if (Object.keys(active).length === 0) {
      setResult(null);
      return;
    }
    setLoading(true);
    setFailed(false);
    try {
      const res = await fetch("/api/policy_simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reductions: active }),
      });
      setResult(await res.json());
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const applyPreset = (name) => {
    setPreset(name);
    if (name === "Custom") return;
    const scenario = stored.scenarios.find((s) => s.name === name);
    if (!scenario) return;
    const next = { ...reductionsRef.current };
    meta.hai_pollutants.forEach((p) => (next[p] = scenario.reductions[p] || 0));
    setReductions(next);
    reductionsRef.current = next;
    runSimulation();
  };

  if (!meta || !stored) return <Loading />;

  const activeCount = Object.values(reductions).filter((v) => v > 0).length;
  const presetContext = preset !== "Custom" ? stored.scenarios.find((s) => s.name === preset)?.context : null;

  return (
    <div><p className="research-notice" role="note">COUNTERFACTUAL SCENARIO · HISTORICAL RESEARCH. This recomputes indices after assumed concentration reductions; it does not establish the causal effect of a real policy.</p>
      <span className="eyebrow">Counterfactual re-scoring</span>
      <p className="research-notice">HISTORICAL POLICY EXPERIMENT · 2015–2020 DATA · NOT CURRENT AIR QUALITY</p><h1>Policy Simulator</h1>
      <p className="caption" style={{ maxWidth: "80ch" }}>
        Reduce pollutant concentrations and the entire historical record is re-scored from first
        principles: new sub-indices, new AQI, new bands, and new cohort Health Advisory Index values
        for all seven groups.
      </p>

      <Banner kind="info">
        <strong>What this tool does and does not claim.</strong> {stored.what_this_is_not}
      </Banner>

      <div className="card">
        <div className="grid grid-1-4" style={{ alignItems: "start" }}>
          <div>
            <label htmlFor="preset">Start from a preset</label>
            <select id="preset" value={preset} onChange={(e) => applyPreset(e.target.value)}>
              <option value="Custom">Custom</option>
              {stored.scenarios.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
            {presetContext && <p className="caption" style={{ marginTop: 12 }}>{presetContext}</p>}
          </div>

          <div className="grid grid-2" style={{ gap: "0 28px" }}>
            {meta.hai_pollutants.map((p) => (
              <div key={p} className="field-row">
                <label htmlFor={`red-${p}`}>{p}</label>
                <input
                  id={`red-${p}`}
                  type="range"
                  min={0}
                  max={80}
                  step={5}
                  value={(reductions[p] || 0) * 100}
                  onChange={(e) => {
                    setPreset("Custom");
                    setReductions((r) => ({ ...r, [p]: Number(e.target.value) / 100 }));
                  }}
                  onMouseUp={runSimulation}
                  onTouchEnd={runSimulation}
                  onKeyUp={runSimulation}
                />
                <span className="slider-value">{Math.round((reductions[p] || 0) * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {failed && (
        <Banner kind="error">
          The simulation service did not respond. This endpoint is a Python function that only runs
          on Vercel (or via <code>vercel dev</code>).
        </Banner>
      )}

      {activeCount === 0 ? (
        <Banner kind="info" icon="↑">Set at least one reduction above to run a scenario.</Banner>
      ) : loading && !result ? (
        <Loading rows={2} />
      ) : result?.ok ? (
        <div style={{ opacity: loading ? 0.55 : 1, transition: "opacity 0.2s" }}>
          <SimResult result={result.result} stored={stored} />
        </div>
      ) : result && !result.ok && !failed ? (
        <Banner kind="warn">{(result.messages || []).join(" ")}</Banner>
      ) : null}

      <details className="card" style={{ marginTop: 24 }}>
        <summary>Scenarios reported in the Review 3 document</summary>
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
      <SectionTitle>Result</SectionTitle>
      <div className="grid grid-4">
        <Metric hero label="Mean AQI" value={result.aqi.mean_after.toFixed(1)} delta={`${result.aqi.mean_change_pct.toFixed(1)}% from ${result.aqi.mean_before.toFixed(1)}`} deltaGood />
        <Metric hero label="Unsafe days" value={result.unsafe_days.after.toLocaleString()} delta={`−${result.unsafe_days.removed.toLocaleString()} (${result.unsafe_days.reduction_pct.toFixed(1)}%)`} deltaGood />
        <Metric hero label="City-days improving a band" value={migration.days_improved.toLocaleString()} delta={`${migration.pct_improved.toFixed(1)}% of all days`} deltaGood />
        <Metric hero label="Advisory-days averted" value={result.cohort_advisory_days.total_averted_across_cohorts.toLocaleString()} delta="across all seven cohorts" deltaGood />
      </div>

      <div className="grid grid-1-1_5">
        <div>
          <h3>Band migration</h3>
          <div className="card" style={{ padding: "12px 6px 4px" }}>
            <ResponsiveContainer width="100%" height={268}>
              <PieChart>
                <Pie
                  data={[
                    { name: "Improved a band", value: migration.days_improved, fill: "#009E73" },
                    { name: "Unchanged", value: migration.days_unchanged, fill: "#56B4E9" },
                    { name: "Worsened", value: migration.days_worsened, fill: "#D55E00" },
                  ]}
                  dataKey="value"
                  innerRadius={58}
                  outerRadius={96}
                  paddingAngle={2}
                  stroke="none"
                />
                <Tooltip {...tooltipProps} formatter={(v) => v.toLocaleString()} />
                <Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 12.5, color: "#b6bfcd" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {anchor && (
            <>
              <h3>Compared with a real reduction (not a validation)</h3>
              <div className="card">
                <div className="grid grid-2">
                  <Metric label="Measured lockdown effect" value={`${anchor.measured_aqi_change_pct.toFixed(1)}%`} />
                  <Metric label="This scenario" value={`${result.aqi.mean_change_pct.toFixed(1)}%`} />
                </div>
                <p className="caption" style={{ marginTop: 12, marginBottom: 0 }}>{anchor.use}</p>
                <p className="caption" style={{ marginTop: 8, marginBottom: 0 }}>
                  The lockdown changed traffic, industry and behaviour all at once, in one season. A similar number
                  here does not show the simulator is right, and nothing on this page is a causal estimate.
                </p>
              </div>
            </>
          )}
        </div>

        <div>
          <h3>Cohort advisory burden, before and after</h3>
          <div className="card" style={{ padding: "18px 10px 8px" }}>
            <ResponsiveContainer width="100%" height={330}>
              <BarChart
                data={cohorts.map((c) => ({ name: c.cohort_label, Before: c.restrictive_days_before, After: c.restrictive_days_after }))}
                layout="vertical"
                margin={{ left: 46, right: 20, top: 6 }}
              >
                <CartesianGrid horizontal={false} />
                <XAxis type="number" tick={axisTick} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={axisTick} tickLine={false} axisLine={false} width={120} />
                <Tooltip {...tooltipProps} formatter={(v) => v.toLocaleString()} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12.5, color: "#b6bfcd" }} />
                <Bar dataKey="Before" fill="#D55E00" radius={[0, 4, 4, 0]} />
                <Bar dataKey="After" fill="#009E73" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <Table
            rows={cohorts.map((c) => ({
              Cohort: c.cohort_label,
              Before: c.restrictive_days_before,
              After: c.restrictive_days_after,
              Averted: c.advisory_days_averted,
              "Reduction (%)": c.reduction_pct,
            }))}
            heat={["Reduction (%)"]}
          />
        </div>
      </div>

      <h3>Effect by city</h3>
      <div className="card" style={{ padding: "18px 10px 8px" }}>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={cityTable} layout="vertical" margin={{ left: 40, right: 50, top: 6 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="city" tick={axisTick} tickLine={false} axisLine={false} width={104} />
            <Tooltip {...tooltipProps} formatter={(v) => `${v.toFixed(1)}%`} />
            <Bar dataKey="pct_days_improved_band" name="Days improving a band" fill="#56B4E9" radius={[0, 5, 5, 0]} label={{ position: "right", fill: "#b6bfcd", fontSize: 11, formatter: (v) => `${Math.round(v)}%` }} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
