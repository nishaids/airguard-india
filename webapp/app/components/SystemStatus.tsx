"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ist } from "./NationwideDashboard";

type Provider = { provider: string; operation: string; status: string; created_at: string | null; record_count: number; error_class?: string };
type Schedule = { jobname: string; schedule: string; active: boolean };
type Scheduler = { generated_at: string; issuance: { state: string; expected_cutoff: string; next_cutoff: string; outbound_alerts: string; alert_required: boolean }; forecasts: number; last_issue: string | null; schedules: Schedule[]; heartbeats: Provider[] };
export default function SystemStatus() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [scheduler, setScheduler] = useState<Scheduler | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(true); const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError("");
    async function load() {
      try {
        const values = await Promise.all(["/api/providers/status", "/api/status/scheduler"].map(async path => {
          const response = await fetch(path, { signal: controller.signal, cache: "no-store" });
          if (!response.ok) throw new Error("Source and schedule status is temporarily unavailable.");
          const result = await response.json(); if (!result.ok) throw new Error("Incomplete status response."); return result;
        }));
        if (!controller.signal.aborted) { setProviders(values[0].providers); setScheduler(values[1]); }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Unable to load status."); }
      finally { if (!controller.signal.aborted) setBusy(false); }
    }
    void load(); const timer = window.setInterval(() => setRevision(v => v+1), 60_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [revision]);
  return <article className="nationwide methods"><p className="live-kicker">OPERATIONS · SOURCE AND SCHEDULE HEALTH</p><h1>Live system status</h1>
    <p>Each source keeps its own identity. A successful model request does not establish a working CPCB feed or a station-validated forecast.</p>
    <button type="button" disabled={busy} onClick={() => setRevision(v => v+1)}>{busy ? "Checking status…" : "Refresh status"}</button>
    {busy && <p role="status">Checking provider events and the fixed-time ledger…</p>}
    {error && <p role="alert" className="live-error">{error} Existing cards, if present, show the previous check.</p>}
    <section className="live-section"><h2>Data sources</h2><div className="status-grid">{providers.map((provider, i) => <article className="status-card" key={`${provider.provider}-${provider.operation}-${i}`}><h3>{provider.provider}</h3><strong>{provider.status}</strong><p>{provider.operation} · {provider.record_count} records</p><p>Last event: {ist(provider.created_at || undefined)}</p>{provider.error_class && <p>Error class: {provider.error_class}</p>}</article>)}</div>
    <p>These are last recorded events, not continuous uptime guarantees. Observation and retrieval times on the live page determine freshness. CPCB/data.gov.in failures remain visible.</p></section>
    {scheduler && <section className="live-section"><h2>20:00 IST prospective issuance</h2><strong>{scheduler.issuance.state.split("_").join(" ")}</strong><p>Checked {ist(scheduler.generated_at)}. Last forecast issued: {ist(scheduler.last_issue || undefined)}. Fixed-time forecast records: {scheduler.forecasts}.</p><p>Expected cutoff: {ist(scheduler.issuance.expected_cutoff)}. Next cutoff: {ist(scheduler.issuance.next_cutoff)}.</p><p>{scheduler.issuance.outbound_alerts}</p><div className="status-grid">{scheduler.schedules.map(job => <article className="status-card" key={job.jobname}><h3>{job.jobname}</h3><p>{job.active ? "Active" : "Inactive"} · cron {job.schedule} UTC</p></article>)}</div><details><summary>Recorded job heartbeats</summary><ul>{scheduler.heartbeats.map((event,i) => <li key={i}>{event.operation}: {event.status}, {event.record_count} records · {ist(event.created_at || undefined)}</li>)}</ul></details><p>Cron dispatch success, forecast issuance and measured-outcome verification are different events. The ledger starts forward in time and never backdates forecasts.</p></section>}
    <p><Link href="/live">Current air quality</Link> · <Link href="/research/track-record">Forecast ledger</Link> · <Link href="/methods">Sources and methods</Link></p>
  </article>;
}
