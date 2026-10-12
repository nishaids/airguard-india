import { describe, expect, it } from "vitest";
import { isSummary } from "../app/lib/validate-summary";
import { operationalSample } from "./operational-fixture";

describe("live response contract", () => {
  it("accepts evidenced complete and explicitly unavailable AQI", () => {
    expect(isSummary(operationalSample)).toBe(true);
    expect(isSummary({ ...operationalSample, ok: false, current: { ...operationalSample.current, aqi: null, category: null }, tomorrow: { ...operationalSample.tomorrow, aqi: null, category: null } })).toBe(true);
  });
  it.each([null, [], {}, { current: {}, tomorrow: {} }, { ...operationalSample, hourly_forecast: null }, { ...operationalSample, weather_context: null }, { ...operationalSample, measured_context: { stations: [null], reason: "bad" } }, { ...operationalSample, current: { ...operationalSample.current, aqi: NaN } }, { ...operationalSample, current: { ...operationalSample.current, aqi: "120" } }, { ...operationalSample, tomorrow: { ...operationalSample.tomorrow, prediction_interval: { lower: 200, upper: 100 } } }])("rejects malformed response %j before rendering", v => expect(isSummary(v)).toBe(false));
  it("rejects duplicate hourly timestamps", () => {
    const h = { time: "2026-10-12T00:00:00Z", aqi: 120, category: operationalSample.current.category, status: "VALID", concentrations: { "PM2.5": 60 } };
    expect(isSummary({ ...operationalSample, hourly_forecast: [h, { ...h, time: "2026-10-12T00:00:00+00:00" }] })).toBe(false);
  });
});
