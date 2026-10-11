"use client";
import { useEffect, useRef, useState } from "react";
import { useOperational } from "./OperationalProvider";
import type { AQI } from "../lib/live-types";
type Result = { forecast_run_id: number; location_key: string; target_date: string; baseline: AQI; scenario: AQI; methodology_version: string; input_reference: string; notice: string };
const pollutants = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"];
export default function CounterfactualScenario() {
  const { data, location } = useOperational();
  const forecast = data?.tomorrow;
  const [reductions, setReductions] = useState<Record<string, number>>({});
  const [result, setResult] = useState<Result | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => { request.current?.abort(); setResult(null); setError(""); setBusy(false); setReductions({}); return () => request.current?.abort(); }, [forecast?.forecast_run_id, location.key]);
  async function calculate(e: React.FormEvent) {
    e.preventDefault(); request.current?.abort(); const controller = new AbortController(); request.current = controller; setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch("/api/air-quality/scenario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ forecast_run_id: forecast?.forecast_run_id, location_key: data?.location.key || location.key, reductions }), signal: controller.signal });
      const value = await response.json(); if (!response.ok) throw new Error(value.message || "Scenario calculation is unavailable.");
      if (!forecast || value.forecast_run_id !== forecast.forecast_run_id || value.baseline.aqi !== forecast.aqi || value.location_key !== (data?.location.key || location.key)) throw new Error("The forecast baseline changed. Refresh before comparing scenarios.");
      if (!controller.signal.aborted) setResult(value);
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Scenario calculation is unavailable."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="live-section"><p className="live-kicker">COUNTERFACTUAL AQI SCENARIO</p><h2>Change tomorrow’s forecast concentrations</h2><p>Selected location: {location.name}. Tomorrow baseline: <strong>{forecast?.qualifier === "LOWER_BOUND" ? "≥" : ""}{forecast?.aqi ?? "Unavailable"}</strong> · {forecast?.category?.label || "Insufficient data"} · {forecast?.date || "Target unavailable"}. Forecast record: {forecast?.forecast_run_id ?? "Unavailable"}.</p><p>Reductions apply to the saved hourly forecast and its preceding gas-window support. They are assumptions, not estimates of a policy’s causal effect.</p><form onSubmit={calculate}><div className="scenario-sliders">{pollutants.map(p => <label key={p}>{p}: −{Math.round((reductions[p] || 0) * 100)}%<input type="range" aria-label={`${p} reduction`} min="0" max="100" step="5" disabled={forecast?.pollutants[p]?.concentration == null} value={Math.round((reductions[p] || 0) * 100)} onChange={e => { request.current?.abort(); setBusy(false); setReductions(v => ({ ...v, [p]: Number(e.target.value) / 100 })); setResult(null); setError(""); }} /><small>Tomorrow baseline {forecast?.pollutants[p]?.concentration?.toFixed(2) ?? "Unavailable"} {forecast?.pollutants[p]?.unit}</small></label>)}</div><button type="submit" disabled={busy || forecast?.aqi == null || !forecast?.forecast_run_id}>{busy ? "Calculating…" : "Calculate scenario"}</button></form>{error && <p role="alert" className="live-error">{error}</p>}{result && <div aria-live="polite"><div className="planning-row"><div><h3>Tomorrow baseline</h3><p>{result.baseline.qualifier === "LOWER_BOUND" ? "≥" : ""}<strong>{result.baseline.aqi}</strong> · {result.baseline.category?.label} · Dominant {result.baseline.dominant_pollutant}</p></div><div><h3>Counterfactual result</h3><p>{result.scenario.qualifier === "LOWER_BOUND" ? "≥" : ""}<strong>{result.scenario.aqi ?? "Insufficient data"}</strong> · {result.scenario.category?.label} · Dominant {result.scenario.dominant_pollutant}</p></div></div><p>{result.notice}</p><small>Same baseline record {result.forecast_run_id} · {result.methodology_version} · input {result.input_reference}</small></div>}</section>;
}
