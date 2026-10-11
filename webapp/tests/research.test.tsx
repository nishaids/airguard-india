import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import OperationalProvider from "../app/components/OperationalProvider";
import { operationalSample } from "./operational-fixture";
vi.mock("next/navigation", () => ({ usePathname: () => "/research" }));
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, "", "/research"); });
import ResearchDashboard from "../app/components/ResearchDashboard";

afterEach(() => vi.restoreAllMocks());
const response = {
  ok: true, protocol: { protocol_version: "test-protocol", issuance_time: "20:00", timezone: "Asia/Kolkata", rationale: "Known inputs only." },
  readiness: { status: "COLLECTING", checks: { uncertainty_complete: false }, claims_supported: [], claims_not_supported: [] },
  prospective: { forecasts: 0, outcomes: 0, valid_days: 0, started_at: null, fixed_issuance_logging_active: false },
  ledger: [], on_demand_forecasts: [], on_demand_notice: "Variable issuance; excluded from fixed protocol.", archive_experiment: "PENDING — ADS credential/terms required"
};

test("research shows pending evidence without invented performance", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async url => ({ ok: true, json: async () => String(url).includes("air-quality/summary") ? operationalSample : response }) as Response);
  render(<OperationalProvider><ResearchDashboard /></OperationalProvider>);
  await waitFor(() => expect(screen.getByText("No fixed-time research forecast has been issued yet. Past forecasts are never backdated into this protocol.")).toBeInTheDocument());
  expect(screen.getByText(/Pending: uncertainty complete/)).toBeInTheDocument();
  expect(screen.getByText(/30-day evaluation: Collecting/)).toBeInTheDocument();
});

test("research API outage shows a readable error", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false } as Response);
  render(<ResearchDashboard ledgerOnly />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Research records are temporarily unavailable");
});
