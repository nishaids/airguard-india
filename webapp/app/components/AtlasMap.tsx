"use client";
import { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, Marker, NavigationControl, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Location, Summary } from "../lib/live-types";

type Sample = { location: Location; data?: Summary };
export default function AtlasMap({ samples, period }: { samples: Sample[]; period: "current" | "tomorrow" }) {
  const element = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!element.current) return;
    let map: MapLibreMap | undefined;
    try {
      const first=samples.find(row => row.data);
      map = new MapLibreMap({ container: element.current, center: first ? [first.location.lon,first.location.lat] : [79,22], zoom: 4,
        minZoom: 3,maxZoom: 12, renderWorldCopies: false, attributionControl: { compact: false }, cooperativeGestures: true,
        style: { version: 8, sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256,
          attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>' } },
          layers: [{ id: "osm", type: "raster", source: "osm" }] } });
      map.addControl(new NavigationControl(),"top-right");
      map.on("error", () => setError("Some map tiles are unavailable. The source-labelled table remains available below."));
      const marked=new Set<string>();
      function marker(lon: number,lat: number,label: string,modelled: boolean) {
        if (!map || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
        const key=`${lon},${lat},${modelled}`; if(marked.has(key)) return; marked.add(key);
        const button=document.createElement("button");button.type="button";button.className=`atlas-marker ${modelled ? "modelled" : "measured"}`;
        button.setAttribute("aria-label",label);button.title=label;
        const detail=document.createElement("p");detail.textContent=label;
        new Marker({element:button}).setLngLat([lon,lat]).setPopup(new Popup({offset:18}).setDOMContent(detail)).addTo(map);
      }
      for(const row of samples) {
        if(!row.data) continue;
        const value=row.data[period]; const grid=value.grid || row.data.tomorrow.grid;
        if(grid && value.aqi !== null && (period==="tomorrow" || value.measured_or_modelled!=="MEASURED"))
          marker(grid.lon,grid.lat,`${row.location.name}: MODELLED ${period==="tomorrow" ? row.data.tomorrow.date : "current"} AQI ${value.qualifier==="LOWER_BOUND" ? "≥" : ""}${value.aqi} (${value.category?.label}) · ${value.freshness} · CAMS grid point, approximately 0.4°, not a station`,true);
        if(period==="current") for(const station of row.data.measured_context.stations) {
          if(!station.coordinates) continue;
          const calc=station.calculation;
          marker(station.coordinates.longitude,station.coordinates.latitude,`${station.name}: MEASURED station context · ${calc?.aqi ?? "AQI unavailable: incomplete pollutant coverage"} · ${station.freshness || "Check observation time"} · last observed ${station.last_observed_at || "unknown"}`,false);
        }
      }
    } catch { setError("The map could not initialize on this device. Use the source-labelled table below."); }
    return () => { map?.remove(); };
  }, [samples,period]);
  return <><p>Solid circles: measured monitoring locations, including incomplete stations. Hatched squares: raw CAMS model grid points. Marker popups retain coverage and freshness; a model point is not neighbourhood exposure.</p>{error && <p role="alert">{error}</p>}<div ref={element} className="atlas-map" role="region" aria-label="Air quality source map" /><p className="privacy-note">Map tiles load from OpenStreetMap only when you open this map. No offline tile downloads or bulk prefetching.</p></>;
}
