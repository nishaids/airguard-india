"use client";
import { useEffect, useRef, useState } from "react";
import { copy } from "../lib/i18n";
import type { Location } from "../lib/live-types";
import { useOperational } from "./OperationalProvider";
export default function LocationPicker() {
  const { location, selectLocation, busy, refresh } = useOperational();
  const [query, setQuery] = useState(""); const [results, setResults] = useState<Location[]>([]); const [status, setStatus] = useState("");
  const controller = useRef<AbortController | null>(null); const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function search(e: React.FormEvent) {
    e.preventDefault(); controller.current?.abort(); const request = new AbortController(); controller.current = request; setStatus("Searching…"); setResults([]);
    try { const response = await fetch(`/api/locations/search?q=${encodeURIComponent(query.trim())}`, { signal: request.signal }); const result = await response.json(); if (!response.ok) throw new Error(result.message || "Location search is unavailable."); if (request.signal.aborted) return; setResults(result.results); setStatus(result.results.length ? `${result.results.length} matching places. Choose a result.` : "No matching place. Try a nearby town or coordinates; postal codes depend on provider coverage."); } catch (e) { if (!request.signal.aborted) setStatus(e instanceof Error ? e.message : "Search failed."); }
  }
  function choose(v: Location) { selectLocation(v); setResults([]); setStatus(""); heading.current?.focus(); }
  function geolocate() {
    if (!navigator.geolocation) { setStatus("This browser does not support geolocation. Use place search or coordinates."); return; }
    setStatus("Waiting for your location permission…");
    navigator.geolocation.getCurrentPosition(({ coords: { latitude: lat, longitude: lon } }) => {
      if (!(lat >= 6 && lat <= 38 && lon >= 68 && lon <= 98)) { setStatus("Your coordinates are outside the India service region. Please search for an Indian place."); return; }
      choose({ key: `${lat.toFixed(4)},${lon.toFixed(4)}`, name: `Your selected coordinates (${lat.toFixed(3)}, ${lon.toFixed(3)})`, lat, lon, country: "IN" });
    }, () => setStatus("Location permission was denied or unavailable. You can still search by place, PIN code or coordinates."), { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  }
  return <><form className="live-search" onSubmit={search}><label htmlFor="place-search">{copy.search}</label><div className="search-controls"><input id="place-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Avadi, Kochi, 600054 or 13.11, 80.11" minLength={2} maxLength={100} required /><button type="submit">Search</button><button type="button" className="secondary" onClick={geolocate}>Use my location</button></div></form><p className="privacy-note">Your selected place is saved in this browser and included in shareable page links. Coordinates are sent to AirGuard and its data providers. Your health group stays in this browser.</p><p role="status">{status}</p>{results.length > 0 && <ul className="place-results" aria-label="Matching Indian places">{results.map(v => <li key={v.key}><button type="button" onClick={() => choose(v)}>{v.name}<small>{v.lat.toFixed(3)}°N · {v.lon.toFixed(3)}°E</small></button></li>)}</ul>}<div className="selected-place"><h2 ref={heading} tabIndex={-1}>{location.name}</h2><button type="button" className="secondary" disabled={busy} onClick={refresh}>Refresh</button></div></>;
}
