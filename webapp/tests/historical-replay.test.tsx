import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import HistoricalReplay from "../app/historical-replay/page";
vi.mock("../app/components/ui", () => ({ Loading: () => <p>Loading historical data</p>, Metric: () => null, Banner: ({ children }: { children: React.ReactNode }) => <div>{children}</div>, Table: () => null, Badge: () => null }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test("Historical Replay retains the city/cohort and 2015–2020 date controls", async () => {
  const meta = { cities: ["Delhi"], date_bounds: { Delhi: { min: "2015-01-01", max: "2020-07-01" } }, hai_pollutants: ["PM2.5"], cohorts: ["healthy_adult"], cohort_labels: { healthy_adult: "Healthy adult" }, aqi_buckets: [] };
  const fetcher = vi.fn((url: string) => Promise.resolve({ ok: true, json: async () => url.includes("meta.json") ? meta : { ok: false, messages: ["Historical mock"] } }));
  vi.stubGlobal("fetch", fetcher); render(<HistoricalReplay />);
  const date = await screen.findByLabelText("Date"); expect(date).toHaveAttribute("type", "date"); expect(date).toHaveAttribute("min", "2015-01-01"); expect(date).toHaveAttribute("max", "2020-07-01"); expect(date).toHaveValue("2020-07-01");
  expect(screen.getByText(/HISTORICAL REPLAY · 2015–2020 DATA · NOT CURRENT/)).toBeInTheDocument(); expect(screen.getByLabelText("City")).toHaveValue("Delhi"); expect(screen.getByLabelText("Cohort")).toHaveValue("healthy_adult");
});
