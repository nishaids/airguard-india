import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import type { ReactNode } from 'react';
import NavBar from '../app/components/NavBar';
import SystemStatus from '../app/components/SystemStatus';
import ResearchDashboard from '../app/components/ResearchDashboard';

vi.mock('next/navigation', () => ({ usePathname: () => '/status' }));
vi.mock('next/link', () => ({ default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a> }));
vi.mock('../app/components/OperationalProvider', () => ({ useOperational: () => ({ href: (path: string) => path }) }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

test('mobile menu announces state and closes on navigation', () => {
  render(<NavBar />);
  fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
  expect(screen.getByRole('button', { name: 'Close menu' })).toHaveAttribute('aria-expanded', 'true');
  fireEvent.click(screen.getByRole('link', { name: 'Status' }));
  expect(screen.getByRole('button', { name: 'Menu' })).toHaveAttribute('aria-expanded', 'false');
});

test('status keeps source failure and no-eligible issuance distinct', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => ({ ok: true, json: async () => String(url).includes('scheduler') ? {
    ok: true, generated_at: '2026-10-11T14:31:00Z', issuance: { state: 'ATTEMPTED_NO_ELIGIBLE_FORECAST', expected_cutoff: '2026-10-11T14:30:00Z', next_cutoff: '2026-10-12T14:30:00Z', outbound_alerts: 'NOT_CONFIGURED', alert_required: false }, forecasts: 0, last_issue: null, schedules: [], heartbeats: []
  } : { ok: true, providers: [{ provider: 'CPCB', operation: 'observations', status: 'FAILED', created_at: null, record_count: 0, error_class: 'ConnectionError' }] } }) as Response);
  render(<SystemStatus />);
  expect(await screen.findByText('FAILED')).toBeInTheDocument();
  expect(await screen.findByText('ATTEMPTED NO ELIGIBLE FORECAST')).toBeInTheDocument();
  expect(screen.getByText(/Error class: ConnectionError/)).toBeInTheDocument();
});

test('research can retry after a temporary outage', async () => {
  const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false } as Response);
  render(<ResearchDashboard ledgerOnly />);
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Retry research records/ }));
  expect(fetcher.mock.calls.length).toBeGreaterThan(1);
});
