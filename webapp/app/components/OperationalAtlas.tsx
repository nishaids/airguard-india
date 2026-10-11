"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import LocationPicker from "./LocationPicker";
import { locationHref, useOperational } from "./OperationalProvider";
import { ist } from "./NationwideDashboard";
import type { Location, Summary } from "../lib/live-types";
const cities: Location[] = [
  { key: "28.6139,77.2090", name: "Delhi, India", lat: 28.6139, lon: 77.209, region: "Delhi" },
  { key: "19.0760,72.8777", name: "Mumbai, Maharashtra, India", lat: 19.076, lon: 72.8777, region: "Maharashtra" },
  { key: "13.0827,80.2707", name: "Chennai, Tamil Nadu, India", lat: 13.0827, lon: 80.2707, region: "Tamil Nadu" },
  { key: "13.1147,80.1098", name: "Avadi, Tamil Nadu, India", lat: 13.1147, lon: 80.10981, region: "Tamil Nadu" },
  { key: "11.0168,76.9558", name: "Coimbatore, Tamil Nadu, India", lat: 11.0168, lon: 76.9558, region: "Tamil Nadu" },
  { key: "9.9312,76.2673", name: "Kochi, Kerala, India", lat: 9.9312, lon: 76.2673, region: "Kerala" },
];
type Row = { location: Location; data?: Summary; error?: string };
const AtlasMap = dynamic(() => import("./AtlasMap"), { ssr: false, loading: () => <p role="status">Loading the source map…</p> });
export default function OperationalAtlas() {
  const { location, data, busy, error, getSummary, selectLocation } = useOperational();
  const [rows, setRows] = useState<Row[]>([]); const [loading, setLoading] = useState(false); const generation = useRef(0);
  const [mapOpen,setMapOpen] = useState(false); const [period,setPeriod] = useState<"current" | "tomorrow">("current");
  useEffect(() => () => { generation.current++; }, []);
  useEffect(() => { generation.current++; setRows([]); setLoading(false); }, [data?.tomorrow.date]);
  async function compare() {
    const token = ++generation.current; setLoading(true);
    // Two at a time: common grid inputs are already cached on the server.
    const output: Row[] = [];
    for (let i = 0; i < cities.length; i += 2) {
      const batch = await Promise.all(cities.slice(i, i + 2).map(async v => { try { return { location: v, data: await getSummary(v) }; } catch (e) { return { location: v, error: e instanceof Error ? e.message : "Unavailable" }; } }));
      output.push(...batch); if (token !== generation.current) return; setRows([...output]);
    }
    setLoading(false);
  }
  const tableRows = [{ location, data: data || undefined, error }, ...rows.filter(v => v.location.key !== location.key)];
  return <article className="nationwide"><p className="live-kicker">OPERATIONAL ATLAS · CURRENT / TOMORROW</p><h1>Air quality across selected places</h1><LocationPicker />{busy && <p role="status">Loading current conditions and tomorrow’s forecast…</p>}{error && <p role="alert">{error}</p>}<p>These are location estimates. CAMS grid cells are modelled areas, not monitoring stations. Each row retains its measurement/model distinction and freshness.</p><button type="button" onClick={compare} disabled={loading || busy}>{loading ? "Loading comparison places…" : "Load six-city comparison"}</button><section className="live-section"><h2>Source map</h2><button type="button" onClick={() => setMapOpen(v => !v)} aria-expanded={mapOpen}>{mapOpen ? "Close source map" : "Open source map"}</button>{mapOpen && <><label> Map period <select value={period} onChange={e => setPeriod(e.target.value as "current" | "tomorrow")}><option value="current">Current station context and estimates</option><option value="tomorrow">Tomorrow modelled forecast</option></select></label><AtlasMap samples={tableRows} period={period} /></>}</section><div className="live-table-scroll"><table><caption>Current and next IST calendar day. Comparison rows are snapshots when loaded; load again to refresh. Select a place to carry it into other operational pages.</caption><thead><tr><th>Place</th><th>Current AQI / category</th><th>Tomorrow AQI / category</th><th>Source / freshness / updated</th><th>Open</th></tr></thead><tbody>{tableRows.map(row => <tr key={row.location.key}><th scope="row"><button type="button" className="secondary" onClick={() => selectLocation(row.location)}>{row.location.name}</button></th><td>{row.data?.current.qualifier === "LOWER_BOUND" ? "≥" : ""}{row.data?.current.aqi ?? "—"}<small>{row.data?.current.category?.label || row.error || "Loading"}</small></td><td>{row.data?.tomorrow.qualifier === "LOWER_BOUND" ? "≥" : ""}{row.data?.tomorrow.aqi ?? "—"}<small>{row.data?.tomorrow.category?.label || "Unavailable"} · {row.data?.tomorrow.date}</small></td><td>{row.data?.current.measured_or_modelled || "Unavailable"} · {row.data?.current.freshness}<small>{row.data?.current.source} · {ist(row.data?.current.timestamp)}</small><small>Tomorrow MODELLED · {row.data?.tomorrow.freshness} · issued {ist(row.data?.tomorrow.issued_at)}</small></td><td>{[["/live", "Live"], ["/forecast", "Forecast & advisory"], ["/policy-simulator", "Policy scenarios"]].map(([path, label]) => <span key={path}><Link href={locationHref(path, row.location)} onClick={() => selectLocation(row.location)}>{label}</Link>{" · "}</span>)}</td></tr>)}</tbody></table></div><p><Link href="/research/historical-atlas">Historical 2015–2020 atlas: archetypes, seasonality, festivals and lockdown</Link></p></article>;
}
