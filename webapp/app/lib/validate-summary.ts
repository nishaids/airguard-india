import type { Summary } from "./live-types";

const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length <= 2000;
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nonnegative = (v: unknown) => finite(v) && v >= 0;
const nullable = (v: unknown) => v === null || nonnegative(v);
const list = (v: unknown, check: (v: unknown) => boolean, max = 240) => Array.isArray(v) && v.length <= max && v.every(check);
const strings = (v: unknown) => object(v) && Object.values(v).every(text);
const timestamp = (v: unknown) => text(v) && Number.isFinite(Date.parse(v));
function category(v: unknown): boolean {
  return v === null || (object(v) && text(v.label) && text(v.colour) && /^#[0-9a-f]{6}$/i.test(v.colour) && finite(v.index) && Number.isInteger(v.index) && v.index >= 0 && v.index <= 5 && nonnegative(v.upper));
}
function pollutant(v: unknown): boolean {
  return object(v) && nullable(v.concentration) && text(v.unit) && nonnegative(v.valid_hours) && text(v.averaging_window) && text(v.quality) && text(v.trend) && (v.sub_index === null || (object(v.sub_index) && nonnegative(v.sub_index.value) && text(v.sub_index.qualifier)));
}
function aqi(v: unknown): boolean {
  if (!object(v) || !nullable(v.aqi) || !category(v.category) || !text(v.status) || !text(v.source_type) || !text(v.freshness) || !object(v.pollutants) || !Object.values(v.pollutants).every(pollutant)) return false;
  if (v.aqi !== null && v.category === null) return false;
  if (v.prediction_interval != null && (!object(v.prediction_interval) || !nonnegative(v.prediction_interval.lower) || !nonnegative(v.prediction_interval.upper) || Number(v.prediction_interval.lower) > Number(v.prediction_interval.upper))) return false;
  return true;
}
function hour(v: unknown): boolean {
  return object(v) && timestamp(v.time) && nullable(v.aqi) && category(v.category) && text(v.status) && object(v.concentrations) && Object.values(v.concentrations).every(nonnegative);
}
function station(v: unknown): boolean {
  return object(v) && text(v.name) && nonnegative(v.distance_km) && list(v.latest, r => object(r) && text(r.pollutant) && nonnegative(r.value) && text(r.unit) && timestamp(r.observed_at) && nonnegative(r.sensor) && text(r.raw_unit));
}
/** Fail closed before render/cache; missing forecasts remain explicit nulls. */
// A cell's scores exist exactly when it is eligible; an ineligible cell can never carry an error figure.
function trackCell(m: unknown): boolean {
  if (!object(m) || !text(m.region) || !text(m.lead) || !text(m.predicted_category) || typeof m.eligible !== "boolean") return false;
  if (!["n", "forecasts", "days", "min_forecasts", "min_days"].every(k => nonnegative(m[k]))) return false;
  const scores = ["mae", "rmse", "category_accuracy", "within_one_category"];
  if (!m.eligible) return [...scores, "bias"].every(k => m[k] === null);
  return scores.every(k => nonnegative(m[k])) && finite(m.bias) && (m.forecasts as number) >= (m.min_forecasts as number) && (m.days as number) >= (m.min_days as number);
}

export function isSummary(v: unknown): v is Summary {
  if (!object(v) || typeof v.ok !== "boolean" || !object(v.location) || !finite(v.location.lat) || !finite(v.location.lon) || v.location.lat < 6 || v.location.lat > 38 || v.location.lon < 68 || v.location.lon > 98 || !text(v.location.name) || !aqi(v.current) || !aqi(v.tomorrow) || !list(v.hourly_forecast, hour) || !timestamp(v.refreshed_at)) return false;
  const times = (v.hourly_forecast as { time: string }[]).map(h => h.time);
  if (new Set(times.map(t => Date.parse(t))).size !== times.length) return false;
  if (!object(v.measured_context) || !text(v.measured_context.reason) || !list(v.measured_context.stations, station, 20)) return false;
  if (!object(v.weather_context) || !text(v.weather_context.status) || !text(v.weather_context.model) || !strings(v.weather_context.units) || !list(v.weather_context.hourly, h => object(h) && timestamp(h.time) && Object.entries(h).every(([k, x]) => k === "time" || finite(x)))) return false;
  if (!object(v.fire_context) || !Array.isArray(v.fire_context.detections) || !text(v.fire_context.meaning) || !object(v.provider_status) || !Object.values(v.provider_status).every(s => object(s) && text(s.status))) return false;
  if (!object(v.provenance) || !list(v.provenance.attribution, text, 20) || !["methodology_version", "methodology_source", "current_averaging", "tomorrow_averaging", "issue_time_basis"].every(k => text(v.provenance && (v.provenance as Record<string, unknown>)[k]))) return false;
  return list(v.track_record, trackCell, 1000);
}
