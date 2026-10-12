import { act } from 'react';
import { renderToString } from 'react-dom/server';
import { hydrateRoot, type Root } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import NavBar from '../app/components/NavBar';

vi.mock('next/navigation', () => ({ usePathname: () => '/city-atlas' }));
vi.mock('../app/components/OperationalProvider', () => ({ useOperational: () => ({ href: (path: string) => path }) }));

describe('mobile navigation hydration', () => {
  it('disables the server-rendered button until its click handler is hydrated', async () => {
    const container = document.createElement('div');
    container.innerHTML = renderToString(<NavBar />);
    document.body.append(container);
    const button = container.querySelector('button')!;
    expect(button.disabled).toBe(true);
    let root: Root | undefined;
    try {
      await act(async () => { root = hydrateRoot(container, <NavBar />); });
      expect(button.disabled).toBe(false);
      await act(async () => { button.click(); });
      expect(button.textContent).toBe('Close menu');
      expect(button.getAttribute('aria-expanded')).toBe('true');
      await act(async () => { button.click(); });
      expect(button.textContent).toBe('Menu');
    } finally {
      await act(async () => { root?.unmount(); });
      container.remove();
    }
  });
});
