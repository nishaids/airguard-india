"use client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea, ReferenceLine } from "recharts";
import type { Hour, AQI } from "../lib/live-types";

export function localHour(time: string) {
  return new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(time));
}
export default function HourlyChart({ hours, field, forecast }: { hours: Hour[]; field: string; forecast?: AQI }) {
  const rows = hours.map(h => ({ time: h.time, value: field === "AQI" ? h.aqi : h.concentrations[field] ?? null }));
  const bounds = (window: { start: string; end: string } | null | undefined) => {
    const selected = window ? hours.filter(h => Date.parse(h.time) >= Date.parse(window.start) && Date.parse(h.time) < Date.parse(window.end)) : [];
    return selected.length ? [selected[0].time, selected[selected.length-1].time] : null;
  };
  const lower=bounds(forecast?.lower_exposure_window), highest=bounds(forecast?.highest_exposure_window);
  return <div className="live-chart" aria-hidden="true"><ResponsiveContainer width="100%" height={230}><LineChart data={rows} margin={{ top: 8, right: 16, bottom: 12, left: 0 }}>
    <CartesianGrid stroke="#cbd5d0" strokeDasharray="3 4" vertical={false} />
    <XAxis dataKey="time" tickFormatter={localHour} minTickGap={65} tick={{ fill: "#324b43", fontSize: 11 }} />
    <YAxis tick={{ fill: "#324b43", fontSize: 12 }} width={44} />
    <Tooltip labelFormatter={value => localHour(String(value))} contentStyle={{ color: "#17342b", background: "#fff", borderColor: "#a8bbb2" }} />
    {lower && <ReferenceArea x1={lower[0]} x2={lower[1]} fill="#dcece0" fillOpacity={.65} label={{ value: "Lower relative exposure", position: "insideTop", fill: "#17342b", fontSize: 10 }} />}
    {highest && <ReferenceArea x1={highest[0]} x2={highest[1]} fill="#f2dfce" fillOpacity={.65} label={{ value: "Higher relative exposure", position: "insideTop", fill: "#603f24", fontSize: 10 }} />}
    {forecast?.peak_hour && <ReferenceLine x={forecast.peak_hour} stroke="#603f24" strokeDasharray="4 4" label={{ value: "AQI peak", position: "insideBottomRight", fill: "#603f24", fontSize: 10 }} />}
    <Line name={field} dataKey="value" type="linear" stroke="#215b49" strokeWidth={2.5} dot={false} isAnimationActive={false} connectNulls={false} />
  </LineChart></ResponsiveContainer></div>;
}
