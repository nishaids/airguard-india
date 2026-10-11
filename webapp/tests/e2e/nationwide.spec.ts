import { test, expect } from "@playwright/test";

for (const query of ["Avadi", "Delhi", "Mumbai", "Chennai", "Bengaluru", "Kolkata", "Hyderabad", "Coimbatore", "Kochi"]) {
  test(`real nationwide flow: ${query}`, async ({ request }) => {
    const search = await request.get("/api/locations/search", { params: { q: query } });
    expect(search.status()).toBe(200);
    const locations = await search.json();
    expect(locations.results.length).toBeGreaterThan(0);
    const location = locations.results[0];
    const response = await request.get("/api/air-quality/summary", { params: { lat: location.lat, lon: location.lon, name: location.name, region: location.region || "" }, timeout: 85000 });
    expect(response.status()).toBe(200);
    const summary = await response.json();
    expect(summary.schema_version).toBe("1.0");
    expect(summary.current.measured_or_modelled).toMatch(/MEASURED|MODELLED/);
    expect(summary.current.aqi).toBeGreaterThanOrEqual(0);
    expect(summary.current.aqi).toBeLessThanOrEqual(500);
    expect(summary.tomorrow.aqi).toBeGreaterThanOrEqual(0);
    expect(summary.tomorrow.aqi).toBeLessThanOrEqual(500);
    expect(summary.tomorrow.model).toBe("cams_global");
    expect(summary.tomorrow.source_type).toBe("modelled_forecast");
    expect(summary.tomorrow.forecast_run_id).toBeGreaterThan(0);
    expect(new Date(summary.tomorrow.issued_at).getTime()).toBeLessThan(new Date(summary.tomorrow.window_start).getTime());
    expect(new Date(summary.refreshed_at).getTime()).toBeGreaterThan(Date.now() - 3600000);
    if (summary.tomorrow.freshness === 'FRESH') expect(new Date(summary.tomorrow.issued_at).getTime()).toBeGreaterThan(Date.now() - 3600000);
    expect(summary.provenance.methodology_version).toBe("airguard-cpcb-2014-v1");
    const day = summary.hourly_forecast.filter((h: { time: string }) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(h.time)) === summary.tomorrow.date);
    expect(day).toHaveLength(24);
  });
}
test("postal code returns provider results or an honest empty response", async ({ request }) => {
  const response = await request.get("/api/locations/search", { params: { q: "600054" } });
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(Array.isArray(result.results)).toBeTruthy();
  if (result.results.length) expect(result.results[0].country_code).toBe("IN");
  else expect(result.postal_code_support).toContain("Provider dependent");
});

test("Avadi saved live forecast is the exact Policy baseline", async ({ request }) => {
  const live = await request.get("/api/air-quality/summary?lat=13.1147&lon=80.10981&name=Avadi", { timeout: 85000 });
  expect(live.status()).toBe(200); const summary = await live.json();
  const reference = { forecast_run_id: summary.tomorrow.forecast_run_id, location_key: summary.location.key };
  const zero = await request.post("/api/air-quality/scenario", { data: { ...reference, reductions: {} } });
  expect(zero.status()).toBe(200); const unchanged = await zero.json();
  expect(unchanged.baseline.aqi).toBe(summary.tomorrow.aqi); expect(unchanged.scenario).toEqual(unchanged.baseline);
  const changed = await request.post("/api/air-quality/scenario", { data: { ...reference, reductions: { "PM2.5": .2 } } });
  expect(changed.status()).toBe(200); const result = await changed.json();
  expect(result.forecast_run_id).toBe(summary.tomorrow.forecast_run_id); expect(result.baseline.aqi).toBe(summary.tomorrow.aqi);
  expect(result.scenario.aqi).toBeLessThanOrEqual(result.baseline.aqi); expect(result.input_reference).toBe(unchanged.input_reference);
  expect((await request.post("/api/air-quality/scenario", { data: { reductions: { "PM2.5": .2 } } })).status()).toBe(400);
});
test("remote coordinate works without requiring a measured station", async ({ request }) => {
  const response = await request.get("/api/air-quality/summary", { params: { lat: 23.4, lon: 70.4, name: "Remote Gujarat coordinate" }, timeout: 85000 });
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.current.measured_or_modelled).toBe("MODELLED");
  expect(result.current.fallback_reason).toContain("no sufficiently recent");
});
test("health, malformed input and scheduler authorization", async ({ request }) => {
  expect((await request.get("/api/health")).status()).toBe(200);
  expect((await request.get("/api/air-quality/summary?lat=NaN&lon=80")).status()).toBe(400);
  expect((await request.post("/api/internal/refresh", { data: {} })).status()).toBe(401);
  expect((await request.get("/api/live_forecast")).status()).toBe(410);
});
test("research ledger separates fixed-time evidence from on-demand records", async ({ request }) => {
  const response = await request.get("/api/research/status");
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.protocol.issuance_time).toBe("20:00");
  expect(data.correction_status).toBe("NOT_VALIDATED");
  expect(Array.isArray(data.ledger)).toBeTruthy();
  expect(Array.isArray(data.on_demand_forecasts)).toBeTruthy();
  expect(data.readiness.checks.rolling_origin_complete).toBe(false);
  const invalid = await request.get("/api/research/status?token=unexpected");
  expect(invalid.status()).toBe(400);
});
