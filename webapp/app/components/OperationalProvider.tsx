"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { cohorts, type Cohort } from "../lib/i18n";
import type { Location, Summary } from "../lib/live-types";

export const DEFAULT_LOCATION: Location = { key: "13.1147,80.1098", name: "Avadi, Tamil Nadu, India", lat: 13.1147, lon: 80.10981, region: "Tamil Nadu", country: "IN" };
export const LOCATION_STORAGE = "airguard.location.v1";
const COHORT_STORAGE = "airguard.cohort.v1";
const TTL = 60_000;
export function istDay(now = new Date()) { return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(now); }
export function nextIstMidnight(now = Date.now()) { const offset = 5.5 * 3600_000; return (Math.floor((now + offset) / 86400_000) + 1) * 86400_000 - offset; }
export function validLocation(value: unknown): Location | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Partial<Location>;
  if (typeof v.lat !== "number" || typeof v.lon !== "number" || !Number.isFinite(v.lat) || !Number.isFinite(v.lon) || v.lat < 6 || v.lat > 38 || v.lon < 68 || v.lon > 98 || typeof v.name !== "string" || !v.name.trim() || v.name.length > 160 || (v.country && v.country !== "IN")) return null;
  return { key: `${v.lat.toFixed(4)},${v.lon.toFixed(4)}`, lat: v.lat, lon: v.lon, name: v.name.trim(), region: typeof v.region === "string" ? v.region.slice(0, 100) : undefined, district: typeof v.district === "string" ? v.district.slice(0, 100) : undefined, country: "IN" };
}
export function locationFromUrl(search: string) {
  const p = new URLSearchParams(search);
  if (!p.has("lat") || !p.has("lon") || !p.get("lat")?.trim() || !p.get("lon")?.trim()) return null;
  return validLocation({ lat: Number(p.get("lat")), lon: Number(p.get("lon")), name: p.get("name") || "Selected Indian coordinates", region: p.get("region"), district: p.get("district"), country: p.get("country") || "IN" });
}
export function locationHref(path: string, location: Location) {
  const p = new URLSearchParams({ lat: String(location.lat), lon: String(location.lon), name: location.name });
  if (location.region) p.set("region", location.region);
  if (location.district) p.set("district", location.district);
  p.set("country", "IN");
  return `${path}?${p}`;
}
type State = { location: Location; selectLocation: (v: Location) => void; cohort: Cohort; setCohort: (v: Cohort) => void; data: Summary | null; busy: boolean; error: string; refresh: () => void; href: (path: string) => string; getSummary: (v: Location, force?: boolean) => Promise<Summary> };
const Context = createContext<State | null>(null);
export function useOperational() { const state = useContext(Context); if (!state) throw new Error("OperationalProvider is required."); return state; }

export default function OperationalProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const active = ["/", "/live", "/forecast", "/policy-simulator", "/city-atlas", "/research"].includes(pathname || "/");
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [cohort, setCohortState] = useState<Cohort>("General adult");
  const [ready, setReady] = useState(false);
  const [data, setData] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const cache = useRef(new Map<string, { at: number; day: string; data: Summary }>());
  const inflight = useRef(new Map<string, { day: string; request: Promise<Summary> }>());
  const forceNext = useRef(false);
  useEffect(() => {
    let saved: Location | null = null;
    try { saved = validLocation(JSON.parse(localStorage.getItem(LOCATION_STORAGE) || "null")); const c = localStorage.getItem(COHORT_STORAGE); if (cohorts.includes(c as Cohort)) setCohortState(c as Cohort); } catch { /* Storage can be unavailable. */ }
    setLocation(locationFromUrl(window.location.search) || saved || DEFAULT_LOCATION); setReady(true);
    const back = () => { const v = locationFromUrl(window.location.search); if (v) { setLocation(v); setData(null); setError(""); setBusy(true); } };
    window.addEventListener("popstate", back); return () => window.removeEventListener("popstate", back);
  }, []);
  useEffect(() => {
    if (!ready) return;
    try { localStorage.setItem(LOCATION_STORAGE, JSON.stringify(location)); } catch { /* Selection still works without persistence. */ }
    if (active) window.history.replaceState(window.history.state, "", locationHref(window.location.pathname, location));
  }, [location, ready, active, pathname]);
  const selectLocation = useCallback((v: Location) => { const valid = validLocation(v); if (valid) { setLocation(valid); setData(null); setError(""); setBusy(true); } }, []);
  const setCohort = useCallback((v: Cohort) => { if (cohorts.includes(v)) { setCohortState(v); try { localStorage.setItem(COHORT_STORAGE, v); } catch { /* Browser-local only. */ } } }, []);
  const getSummary = useCallback(async (v: Location, force = false): Promise<Summary> => {
    const key = `${v.lat},${v.lon}`;
    const day = istDay();
    const hit = cache.current.get(key);
    if (!force && hit && Date.now() - hit.at < TTL && hit.day === day) return hit.data;
    const pending = inflight.current.get(key); if (pending?.day === day) return pending.request;
    const request = (async () => {
      const params = new URLSearchParams({ lat: String(v.lat), lon: String(v.lon), name: v.name, ...(v.region ? { region: v.region } : {}) });
      let result: Summary | null = null;
      for (let attempt = 0; attempt < 24; attempt++) {
        if (day !== istDay()) throw new Error('The IST day changed. Refreshing current data.');
        const response = await fetch(`/api/air-quality/summary?${params}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
        result = await response.json();
        if (response.status !== 202) break;
        await new Promise(resolve => window.setTimeout(resolve, 5000));
      }
      if (!result) throw new Error('Live data is temporarily unavailable.');
      if (!result.current || !result.tomorrow) throw new Error(result.message || "Live data is temporarily unavailable.");
      if (day === istDay()) cache.current.set(key, { at: Date.now(), day, data: result });
      // Bounded browser cache; no cohort or provider credentials enter it.
      if (cache.current.size > 24) cache.current.delete(cache.current.keys().next().value!);
      return result;
    })();
    inflight.current.set(key, { day, request });
    try { return await request; } finally { if (inflight.current.get(key)?.request === request) inflight.current.delete(key); }
  }, []);
  useEffect(() => {
    if (!ready || !active) { if (ready) setBusy(false); return; }
    let cancelled = false;
    const force = forceNext.current; forceNext.current = false;
    setBusy(true); setError("");
    void getSummary(location, force).then(result => { if (!cancelled) { setData(result); if (!result.ok) setError("All air-quality sources are unavailable. No substitute values are shown."); } }).catch(e => { if (!cancelled) { setData(null); setError(e instanceof Error ? e.message : "Unable to load live data."); } }).finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [ready, active, location, revision, getSummary]);
  useEffect(() => { if (!ready || !active) return; const timer = window.setInterval(() => setRevision(v => v + 1), TTL); return () => window.clearInterval(timer); }, [ready, active]);
  useEffect(() => {
    if (!ready || !active) return;
    // Invalidate immediately at IST midnight, even during a navigation cache hit.
    const timer = window.setTimeout(() => { cache.current.clear(); setData(null); setRevision(v => v + 1); }, nextIstMidnight() - Date.now() + 10);
    return () => window.clearTimeout(timer);
  }, [ready, active, revision]);
  const refresh = useCallback(() => { forceNext.current = true; setRevision(v => v + 1); }, []);
  const href = useCallback((path: string) => locationHref(path, location), [location]);
  const value = useMemo(() => ({ location, selectLocation, cohort, setCohort, data, busy, error, refresh, href, getSummary }), [location, selectLocation, cohort, setCohort, data, busy, error, refresh, href, getSummary]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
