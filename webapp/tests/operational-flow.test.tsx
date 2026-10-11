import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import NationwideDashboard from "../app/components/NationwideDashboard";
import CounterfactualScenario from "../app/components/CounterfactualScenario";
import OperationalAtlas from "../app/components/OperationalAtlas";
import LivePage from "../app/live/page";
import ForecastPage from "../app/forecast/page";
import PolicyPage from "../app/policy-simulator/page";
import NavBar from "../app/components/NavBar";
import OperationalProvider, { LOCATION_STORAGE, locationFromUrl, locationHref, nextIstMidnight, useOperational } from "../app/components/OperationalProvider";
import { operationalSample } from "./operational-fixture";
vi.mock("next/navigation", () => ({ usePathname: () => "/live" }));
vi.mock("next/dynamic", () => ({ default: () => () => <div>Hourly chart</div> }));
vi.mock("next/link", () => ({ default: ({ children, href, onClick }: { children: React.ReactNode; href: string; onClick?: () => void }) => <a href={href} onClick={onClick}>{children}</a> }));
const response = (data: unknown, ok = true) => Promise.resolve({ ok, json: async () => data });
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/live"); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function Flow() {
  const [mode, setMode] = useState<"live" | "forecast" | "policy">("live"); const { href } = useOperational();
  return <><button onClick={() => setMode("forecast")}>Open Forecast & advisory</button><button onClick={() => setMode("policy")}>Open Policy scenarios</button><a href={href("/forecast")}>Share forecast</a>{mode === "live" ? <LivePage /> : mode === "forecast" ? <ForecastPage /> : <PolicyPage />}</>;
}
test("Avadi → Live → Forecast → Policy retains one summary, location and scenario baseline", async () => {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("locations/search")) return response({ results: [{ ...operationalSample.location, name: "Avadi, Tamil Nadu, India" }] });
    if (url.includes("air-quality/scenario")) { const payload = JSON.parse(String(init?.body)); expect(payload).toEqual({ forecast_run_id: 73, location_key: operationalSample.location.key, reductions: { "PM2.5": .2 } }); return response({ forecast_run_id: 73, location_key: operationalSample.location.key, baseline: operationalSample.tomorrow, scenario: { ...operationalSample.tomorrow, aqi: 148 }, notice: "Counterfactual, not causal.", methodology_version: "airguard-cpcb-2014-v1", input_reference: "fixture" }); }
    return response(operationalSample);
  }); vi.stubGlobal("fetch", fetcher);
  render(<OperationalProvider><Flow /></OperationalProvider>);
  await screen.findByText("167");
  fireEvent.change(screen.getByLabelText(/Search city/), { target: { value: "Avadi" } }); fireEvent.click(screen.getByRole("button", { name: "Search" })); fireEvent.click(await screen.findByRole("button", { name: /Avadi, Tamil Nadu/ }));
  await screen.findByText("167");
  fireEvent.click(screen.getByText("Open Forecast & advisory"));
  expect(screen.getByRole("heading", { name: "Forecast & advisory" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Avadi, Tamil Nadu, India" })).toBeInTheDocument();
  expect(screen.getByText("120")).toBeInTheDocument(); expect(screen.getAllByText("167").length).toBeGreaterThan(0);
  expect(document.querySelector('input[type="date"]')).toBeNull();
  fireEvent.change(screen.getByLabelText("Plan for"), { target: { value: "Asthma/COPD" } });
  expect(screen.getAllByText(/shorter, less strenuous outdoor/).length).toBe(2);
  fireEvent.click(screen.getByText("Open Policy scenarios"));
  fireEvent.change(screen.getByLabelText("PM2.5 reduction"), { target: { value: "20" } }); fireEvent.click(screen.getByText("Calculate scenario"));
  await screen.findByText("148");
  expect(fetcher.mock.calls.filter(([u]) => u.includes("air-quality/summary"))).toHaveLength(1);
  expect(fetcher.mock.calls.every(([u]) => !u.includes("/data/"))).toBe(true);
  expect(screen.getByText("Share forecast").getAttribute("href")).toContain("lat=13.1147&lon=80.10981");
  expect(localStorage.getItem(LOCATION_STORAGE)).toContain("Avadi");
  expect(fetcher.mock.calls.filter(([u]) => u.includes("summary")).every(([u]) => !u.includes("Asthma"))).toBe(true);
});

test("a valid deep link overrides saved location and no health preference is sent", async () => {
  localStorage.setItem(LOCATION_STORAGE, JSON.stringify(operationalSample.location)); window.history.replaceState({}, "", "/forecast?lat=9.9312&lon=76.2673&name=Kochi&region=Kerala");
  const fetcher = vi.fn(() => response(operationalSample)); vi.stubGlobal("fetch", fetcher);
  render(<OperationalProvider><NationwideDashboard mode="forecast" /></OperationalProvider>);
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("lat=9.9312&lon=76.2673&name=Kochi"), expect.anything()));
  expect(screen.getByRole("heading", { name: "Kochi" })).toBeInTheDocument();
  expect(locationFromUrl("?lat=&lon=&name=Bad")).toBeNull(); expect(locationFromUrl("?lat=0&lon=0")).toBeNull(); expect(locationFromUrl("?lat=13&lon=80&country=US")).toBeNull();
  expect(locationHref("/live", operationalSample.location)).not.toContain("cohort");
});

test("Atlas selected place uses the same current/tomorrow summary and labels grid estimates", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response(operationalSample)));
  render(<OperationalProvider><OperationalAtlas /></OperationalProvider>);
  const row = await screen.findByRole("row", { name: /Avadi.*120.*167/ });
  expect(within(row).getByRole("link", { name: "Forecast & advisory" }).getAttribute("href")).toContain("lat=13.1147");
  expect(screen.getByText(/modelled areas, not monitoring stations/)).toBeInTheDocument();
});

test("OpenAQ failure and missing pollutants remain modelled and unavailable on Forecast", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ ...operationalSample, provider_status: { openaq: { status: "FAILED" } }, current: { ...operationalSample.current, fallback_reason: "OpenAQ unavailable; using modelled current conditions." } })));
  render(<OperationalProvider><NationwideDashboard mode="forecast" /></OperationalProvider>);
  await screen.findByText(/OpenAQ unavailable/); expect(screen.getAllByText(/MODELLED/).length).toBeGreaterThan(0);
  const ozone = screen.getAllByRole("row").find(v => v.textContent?.startsWith("O3")); expect(ozone).toHaveTextContent("—");
});

test("CAMS failure preserves measured current data and unavailable tomorrow without historical fallback", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ ...operationalSample, current: { ...operationalSample.current, measured_or_modelled: "MEASURED" }, tomorrow: { ...operationalSample.tomorrow, aqi: null, category: null, freshness: "UNAVAILABLE", forecast_run_id: undefined, pollutants: {} }, provider_status: { open_meteo: { status: "FAILED" } } })));
  render(<OperationalProvider><NationwideDashboard mode="forecast"><CounterfactualScenario /></NationwideDashboard></OperationalProvider>);
  await screen.findByText("MEASURED · FRESH"); expect(screen.getByRole("button", { name: "Calculate scenario" })).toBeDisabled(); expect(screen.queryByText("167")).toBeNull();
});

test("IST midnight invalidates a fresh browser cache and requests the new tomorrow", async () => {
  const { act } = await import("@testing-library/react");
  vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-11T18:29:59Z"));
  const fetcher = vi.fn(() => response(operationalSample)); vi.stubGlobal("fetch", fetcher);
  render(<OperationalProvider><NationwideDashboard /></OperationalProvider>);
  await act(async () => { await Promise.resolve(); });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(nextIstMidnight()).toBe(new Date("2026-10-11T18:30:00Z").getTime());
  await act(async () => { vi.advanceTimersByTime(1100); await Promise.resolve(); });
  expect(fetcher).toHaveBeenCalledTimes(2);
});

test("an old location response cannot overwrite a newly selected location", async () => {
  let finishOld: (value: unknown) => void = () => {};
  const old = new Promise(resolve => { finishOld = resolve; });
  const fetcher = vi.fn((url: string) => url.includes("locations/search") ? response({ results: [{ key: "9.9312,76.2673", name: "Kochi", lat: 9.9312, lon: 76.2673 }] }) : url.includes("lat=9.9312") ? response({ ...operationalSample, current: { ...operationalSample.current, aqi: 88 } }) : old);
  vi.stubGlobal("fetch", fetcher); render(<OperationalProvider><NationwideDashboard /></OperationalProvider>);
  fireEvent.change(screen.getByLabelText(/Search city/), { target: { value: "Kochi" } }); fireEvent.click(screen.getByRole("button", { name: "Search" })); fireEvent.click(await screen.findByRole("button", { name: /Kochi/ }));
  await screen.findByText("88"); const { act } = await import("@testing-library/react");
  await act(async () => { finishOld({ ok: true, json: async () => operationalSample }); });
  expect(screen.getByText("88")).toBeInTheDocument(); expect(screen.queryByText("120")).toBeNull();
});

test("a pre-midnight in-flight summary cannot populate tomorrow after IST rollover", async () => {
  const { act } = await import("@testing-library/react"); vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-11T18:29:59Z"));
  let finishOld: (value: unknown) => void = () => {}; const old = new Promise(resolve => { finishOld = resolve; });
  const fetcher = vi.fn().mockImplementationOnce(() => old).mockImplementation(() => response({ ...operationalSample, tomorrow: { ...operationalSample.tomorrow, aqi: 188, date: "2026-10-13" } }));
  vi.stubGlobal("fetch", fetcher); render(<OperationalProvider><NationwideDashboard /></OperationalProvider>);
  await act(async () => { await Promise.resolve(); });
  await act(async () => { vi.advanceTimersByTime(1100); await Promise.resolve(); });
  expect(fetcher).toHaveBeenCalledTimes(2); expect(screen.getByText("188")).toBeInTheDocument();
  await act(async () => { finishOld({ ok: true, json: async () => operationalSample }); });
  expect(screen.getByText("188")).toBeInTheDocument(); expect(screen.queryByText("167")).toBeNull();
});

test("real navigation links share location while Historical Replay has its own route", async () => {
  window.history.replaceState({}, "", "/live?lat=9.9312&lon=76.2673&name=Kochi"); vi.stubGlobal("fetch", vi.fn(() => response(operationalSample)));
  render(<OperationalProvider><NavBar /></OperationalProvider>);
  await waitFor(() => expect(screen.getByRole("link", { name: "Forecast & advisory" }).getAttribute("href")).toContain("lat=9.9312&lon=76.2673"));
  expect(screen.getByRole("link", { name: "Policy scenarios" }).getAttribute("href")).toContain("name=Kochi");
  expect(screen.getByRole("link", { name: "Historical replay" })).toHaveAttribute("href", "/historical-replay");
});

test("browser back clears the previous place's AQI while the new location loads", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => url.includes("lat=9.9312") ? new Promise(() => {}) : response(operationalSample)));
  render(<OperationalProvider><NationwideDashboard /></OperationalProvider>); await screen.findByText("120");
  const { act } = await import("@testing-library/react");
  act(() => { window.history.replaceState({}, "", "/live?lat=9.9312&lon=76.2673&name=Kochi"); window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(screen.getByRole("heading", { name: "Kochi" })).toBeInTheDocument(); expect(screen.queryByText("120")).toBeNull(); expect(screen.queryByText("167")).toBeNull();
});
