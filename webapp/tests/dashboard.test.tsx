import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from "@testing-library/react";
import OperationalProvider from "../app/components/OperationalProvider";
const render = (value: React.ReactNode) => rtlRender(<OperationalProvider>{value}</OperationalProvider>);
vi.mock("next/navigation", () => ({ usePathname: () => "/live" }));
import NationwideDashboard from "../app/components/NationwideDashboard";

vi.mock("next/dynamic", () => ({ default: () => () => <div>Hourly chart</div> }));
vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }));
const aqi = { aqi: 120, category: { label: "Moderate", colour: "#e8b500", index: 2 }, status: "VALID", dominant_pollutant: "PM2.5", freshness: "FRESH", pollutants: {}, source: "Open-Meteo / CAMS", timestamp: "2026-10-10T10:30:00Z", measured_or_modelled: "MODELLED" };
const sample = { ok: true, current: aqi, tomorrow: { ...aqi, date: "2026-10-11", issued_at: "2026-10-10T10:30:00Z", peak_hour: "2026-10-11T11:30:00Z", peak_aqi: 130 }, hourly_forecast: [], measured_context: { stations: [], reason: "No complete station" }, weather_context: { hourly: [], units: {} }, fire_context: { detections: [] }, track_record: [], provider_status: {}, provenance: { methodology_version: "test", attribution: [] }, refreshed_at: "2026-10-10T10:30:00Z" };
const response = (data: unknown, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(data) });
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/live"); vi.stubGlobal("fetch", vi.fn(() => response(sample))); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("nationwide dashboard", () => {
  it("shows loading, current and tomorrow with modelled evidence", async () => {
    render(<NationwideDashboard />);
    expect(screen.getByText(/Loading current conditions/)).toBeInTheDocument();
    expect(await screen.findByText(/Tomorrow’s AirGuard/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("120")).toHaveLength(2));
    expect(screen.getAllByText(/MODELLED/).length).toBeGreaterThan(0);
    expect(screen.getByText(/No eligible forecast/)).toBeInTheDocument();
  });
  it("renders measured and stale labels", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({ ...sample, current: { ...aqi, measured_or_modelled: "MEASURED", freshness: "DELAYED" }, tomorrow: { ...sample.tomorrow, freshness: "STALE" } })));
    render(<NationwideDashboard />);
    expect(await screen.findByText("MEASURED · DELAYED")).toBeInTheDocument();
    expect(screen.getByText(/MODELLED · STALE/)).toBeInTheDocument();
  });
  it("searches and chooses a place without a training-city list", async () => {
    const fetcher = vi.fn((url: string) => response(url.includes("locations/search") ? { results: [{ key: "new", name: "Kochi, Kerala, India", lat: 9.93, lon: 76.26 }] } : sample));
    vi.stubGlobal("fetch", fetcher);
    render(<NationwideDashboard />);
    fireEvent.change(screen.getByLabelText(/Search city/), { target: { value: "Kochi" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    fireEvent.click(await screen.findByRole("button", { name: /Kochi, Kerala/ }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("lat=9.93"), expect.anything()));
  });
  it("handles denied location without blocking search", async () => {
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition: (_success: unknown, fail: () => void) => fail() } });
    render(<NationwideDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Use my location" }));
    expect(await screen.findByText(/permission was denied/)).toBeInTheDocument();
  });
  it("uses granted location only after a user click", async () => {
    const getCurrentPosition = vi.fn((success: (value: unknown) => void) => success({ coords: { latitude: 11.0, longitude: 77.0 } }));
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: { getCurrentPosition } });
    render(<NationwideDashboard />);
    expect(getCurrentPosition).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Use my location" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /Your selected coordinates/ })).toBeInTheDocument());
  });
  it("shows a provider error and no invented AQI", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({ message: "Sources unavailable" }, false)));
    render(<NationwideDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sources unavailable");
    expect(screen.getAllByText("—")).toHaveLength(2);
  });
});
