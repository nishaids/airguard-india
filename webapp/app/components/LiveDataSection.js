"use client";

import { useEffect, useState } from "react";

const time = (iso) => iso ? new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST" : "Not available";

export default function LiveDataSection() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [city, setCity] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(`/api/live${city ? `?city=${encodeURIComponent(city)}` : ""}`, {
          signal: controller.signal, cache: "no-store",
        });
        const body = await response.json();
        if (!response.ok || !body.ok) throw new Error(body.message || "Live data unavailable.");
        setData(body);
        setError(null);
      } catch (err) {
        if (err.name !== "AbortError") setError(err.message || "Live data unavailable.");
      }
    };
    setData(null);
    load();
    const interval = setInterval(load, 60000);
    return () => { controller.abort(); clearInterval(interval); };
  }, [city, refresh]);

  return (
    <section className="card" style={{ marginBottom: 24 }} aria-labelledby="live-data-title">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <h2 id="live-data-title" style={{ margin: 0 }}>Live data · AirGuard 2.0</h2>
        <button className="btn" type="button" onClick={() => setRefresh((n) => n + 1)}>Refresh</button>
      </div>
      <p className="caption">Station measurements, weather forecasts and regional fire detections stored in Supabase. These inputs are being collected for a future validated tomorrow-AQI prediction.</p>
      {error && <p role="alert">{error}{data ? " Previously loaded records are shown below; refresh failed." : ""}</p>}
      {!data && !error && <p role="status">Loading live records…</p>}
      {data && <>
        <label htmlFor="live-city">City </label>
        <select id="live-city" value={city} onChange={(event) => setCity(event.target.value)}>
          <option value="">All supported cities</option>
          {data.cities.map((name) => <option key={name}>{name}</option>)}
        </select>
        <p className="caption">Checked {time(data.generated_at)}. Fresh ≤ {data.freshness_thresholds.fresh_minutes} minutes; delayed ≤ {data.freshness_thresholds.stale_minutes} minutes. Observation age is checked on every refresh.</p>
        <div className="grid grid-4">
          {data.sources.map((source) => <div key={source.source_id}>
            <strong><a href={source.homepage} target="_blank" rel="noreferrer">{source.source_id}</a></strong>
            <p>{source.last_run_status || "Not ingested"} · {source.stored.toLocaleString()} stored</p>
            {source.source_type === "measured" && <p className="caption">{source.usable_measurements_now} usable current readings in this selection; {source.freshness_counts.unavailable} latest readings older than 24 hours.</p>}
            {source.error && <details><summary>Source error</summary><p className="caption" style={{ overflowWrap: "anywhere" }}>{source.error}</p></details>}
            <p className="caption">Last attempt {time(source.started_at)}</p>
          </div>)}
        </div>
        <details>
        <summary>Latest station readings ({data.measurements.length} shown)</summary>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%" }}>
            <thead><tr>{["Source / station", "Pollutant", "Value", "Observed (IST)", "Freshness / quality"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead>
            <tbody>{data.measurements.map((row) => <tr key={`${row.source_id}-${row.source_station_id}-${row.pollutant}-${row.averaging_period}-${row.observed_at}`}>
              <td>{row.source_id} · {row.station_name || row.source_station_id}<div className="caption">{row.city} · upstream {row.upstream_provider || "unspecified"}</div></td>
              <td>{row.pollutant}<div className="caption">{row.averaging_period} · {row.value_kind}</div></td>
              <td>{row.normalized_value == null ? `${row.raw_value} (raw; ${row.raw_unit || "unit unspecified"})` : `${row.normalized_value.toFixed(2)} ${row.normalized_unit}`}</td>
              <td>{time(row.observed_at)}</td>
              <td>{row.freshness} · {row.quality_state}<div className="caption">{row.quality_flags.join(", ")}{!row.usable_now && " · excluded from current modelling"}</div></td>
            </tr>)}</tbody>
          </table>
          {!data.measurements.length && <p>No station measurements stored for this selection.</p>}
        </div>
        <p className="caption">Showing up to 30 latest readings. OpenAQ is an aggregator; its readings retain their upstream provider and are labelled OpenAQ.</p>
        </details>
        <p>Open-Meteo: {data.weather.length} locations with upcoming weather forecasts. NASA FIRMS: {data.fires.count_last_24h.toLocaleString()} regional detections in the last 24 hours.</p>
        <p className="caption">{data.fires.scope}. Thermal detections are context for smoke transport; they are not AQI measurements. Weather and modelled AQI are separate from station observations.</p>
        <details><summary>Weather forecast details</summary>
          {data.weather.map((row) => <p key={`${row.location_label}-${row.model}`}>
            {row.location_label}: {row.temperature_2m ?? "—"} {row.units.temperature_2m}, wind {row.wind_speed_10m ?? "—"} {row.units.wind_speed_10m} · {row.model} · valid {time(row.valid_at)} · retrieved {time(row.retrieved_at)} · {row.freshness}
          </p>)}
        </details>
      </>}
    </section>
  );
}
