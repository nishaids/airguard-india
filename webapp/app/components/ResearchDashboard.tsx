"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ist } from "./NationwideDashboard";
import OperationalResearchPanel from "./OperationalResearchPanel";

type Forecast = { id: number; location: string; forecast_mode: string; issued_at: string; target_date: string; cams_aqi: number; corrected_aqi: number | null; interval: { lower: number; upper: number } | null; observed_aqi: number | null; qualifier: string | null; cams_error: number | null; airguard_error: number | null };
type Research = { ok: boolean; protocol: { protocol_version: string; issuance_time: string; timezone: string; rationale: string }; readiness: { status: string; checks: Record<string, boolean>; claims_supported: string[]; claims_not_supported: string[] }; prospective: { forecasts: number; outcomes: number; valid_days: number; started_at: string | null; fixed_issuance_logging_active: boolean; fixed_issuance_schedule_active: boolean; last_issued_at: string | null }; ledger: Forecast[]; archive_experiment: string; on_demand_forecasts: { id: number; issued_at: string; target_start: string; predicted_aqi: number; location_key: string }[]; on_demand_notice: string };
const questions = ["Does station correction improve on raw CAMS and persistence?", "Does it generalise to unseen cities and stations?", "How does it behave on high-pollution and Severe days?", "Do predictive intervals achieve coverage across pollution regimes?", "Can calibrated advisory policies reduce under-warning at an acceptable cost in over-warning?"];

export default function ResearchDashboard({ ledgerOnly = false }: { ledgerOnly?: boolean }) {
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setError("");
      try {
        const response = await fetch("/api/research/status", { signal: controller.signal });
        if (!response.ok) throw new Error("Research records are temporarily unavailable.");
        const result: Research = await response.json();
        if (!result.ok) throw new Error("Research records are unavailable.");
        setData(result);
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Unable to load research records."); }
    }
    void load(); return () => controller.abort();
  }, [revision]);
  return <article className="nationwide methods">
    <p className="live-kicker">RESEARCH MODE · EVIDENCE BEFORE CLAIMS</p>
    <h1>{ledgerOnly ? "Prospective forecast ledger" : "Station-calibrated forecasting research"}</h1>
    <p>AirGuard provides nationwide CAMS-based estimates today. India-specific correction and uncertainty-aware advisory policies are experimental; improvement has not been established.</p>
    <nav aria-label="Research sections"><Link href="/live">Live air quality</Link> · <Link href="/research">Research overview</Link> · <Link href="/research/track-record">Forecast ledger</Link> · <Link href="/research/legacy">Historical research baseline</Link> · <Link href="/methods">Methods</Link></nav>
    {!ledgerOnly && <OperationalResearchPanel />}
    {error && <div className="live-error"><p role="alert">{error}</p><button type="button" onClick={() => setRevision(v => v+1)}>Retry research records</button></div>}
    {!data && !error && <p role="status">Loading the research evidence…</p>}
    {data && <>
      {!ledgerOnly && <>
        <h2>Research questions</h2><ol>{questions.map(q => <li key={q}>{q}</li>)}</ol>
        <h2>Locked forecast protocol</h2><p>{data.protocol.protocol_version}. Issue at {data.protocol.issuance_time} IST for the next calendar day. Only inputs retrieved or demonstrably available by the cutoff are eligible. Targets require measured hourly data from a station bound before the outcome.</p><p>{data.protocol.rationale}</p>
        <h2>Baselines, backtests and uncertainty</h2><p>Climatology, persistence, raw CAMS, ridge residual correction, LightGBM, XGBoost and direct AQI modelling use the same evaluation rows. Date-blocked rolling and expanding folds, separate calibration, a final test, spatial holdouts and feature ablations are required.</p><p>80% and 90% prediction intervals and advisory trade-offs will be evaluated when eligible pairs exist. No operational prediction interval, empirical risk guarantee or correction performance is currently claimed.</p>
        <h2>Readiness gates</h2><p>Research readiness: collecting evidence. A passing software test does not establish forecast skill.</p><ul>{Object.entries(data.readiness.checks).map(([name, passed]) => <li key={name}>{passed ? "Evidence recorded" : "Pending"}: {name.replace(/_/g, " ")}</li>)}</ul>
        <h2>Data and reproducibility</h2><p>{data.archive_experiment}. Reanalysis and newly downloaded past-days CAMS fields cannot substitute for archived forecasts available at issuance. The historical 2015–2020 reported-AQI experiment stays separate.</p><p>Rebuild artifacts with <code>python run_research_pipeline.py</code>. Dataset hashes, protocol versions, seeds, dependency versions and working-tree hashes accompany each experiment.</p>
      </>}
      <h2>Fixed 20:00 IST prospective track record</h2>
      <p>Started: {data.prospective.started_at ? ist(data.prospective.started_at) : "Awaiting the first scheduled issuance"}. Forecasts: {data.prospective.forecasts}. Verified outcomes: {data.prospective.outcomes}. Valid target days: {data.prospective.valid_days}.</p>
      <p>30-day evaluation: {data.prospective.valid_days >= 30 ? "Check completed window coverage" : "Collecting"}. 90-day evaluation: {data.prospective.valid_days >= 90 ? "Check completed window coverage" : "Collecting"}. Cloud schedule: {data.prospective.fixed_issuance_schedule_active ? "Active" : "Inactive"}. Fixed-time forecasts issued: {data.prospective.forecasts}{data.prospective.last_issued_at ? `, most recently ${data.prospective.last_issued_at}` : ""}. An active schedule is not an issued forecast, so both are shown.</p>
      {data.ledger.length ? <div className="live-table-wrap"><table className="live-table"><caption>Forecasts frozen before the target; signed error means predicted minus measured AQI.</caption><thead><tr><th>Issued IST</th><th>Target</th><th>Location / mode</th><th>Raw CAMS</th><th>AirGuard correction</th><th>Interval</th><th>Measured outcome</th><th>CAMS error</th><th>AirGuard error</th></tr></thead><tbody>{data.ledger.map(row => <tr key={row.id}><td>{ist(row.issued_at)}</td><td>{row.target_date}</td><td>{row.location}<br />{row.forecast_mode === "STATION_CALIBRATED_AIRGUARD" ? "Station calibrated" : "CAMS nationwide"}</td><td>{row.cams_aqi}</td><td>{row.corrected_aqi ?? "Not validated"}</td><td>{row.interval ? `${row.interval.lower}–${row.interval.upper}` : "Not available"}</td><td>{row.observed_aqi === null ? "Awaiting eligible outcome" : `${row.qualifier === "LOWER_BOUND" ? "≥" : ""}${row.observed_aqi}`}</td><td>{row.cams_error ?? "—"}</td><td>{row.airguard_error ?? "—"}</td></tr>)}</tbody></table></div> : <p>No fixed-time research forecast has been issued yet. Past forecasts are never backdated into this protocol.</p>}
      <details><summary>Existing on-demand nationwide forecast records</summary><p>{data.on_demand_notice}</p><div className="live-table-wrap"><table className="live-table"><thead><tr><th>Record</th><th>Issued IST</th><th>Target starts IST</th><th>Raw CAMS estimate</th></tr></thead><tbody>{data.on_demand_forecasts.map(row => <tr key={row.id}><td>{row.id}</td><td>{ist(row.issued_at)}</td><td>{ist(row.target_start)}</td><td>{row.predicted_aqi}</td></tr>)}</tbody></table></div></details>
      <h2>Claims and limitations</h2><p>No claim of superiority, clinical validation, guaranteed safety or nationwide station calibration is supported. Coarse model grids do not resolve neighbourhood exposure. Severe AQI above the last closed breakpoint is a lower bound; exact Severe-day regression error cannot be invented.</p>
    </>}
  </article>;
}
