import { test, expect } from '@playwright/test';

const routes = ['/', '/live', '/forecast', '/city-atlas', '/model-insights', '/research', '/methods', '/policy-simulator',
  '/research/track-record', '/historical-replay', '/research/historical-atlas', '/research/historical-policy', '/research/legacy', '/status'];
for (const width of [375, 1280]) {
  for (const route of routes) {
    test(`production ${width} ${route}`, async ({ page, baseURL }) => {
      const errors: string[] = [];
      const origin = new URL(baseURL!).origin;
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => {
        if (new URL(response.url()).origin === origin && response.status() >= 400) {
          errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);
        }
      });
      await page.setViewportSize({ width, height: 1000 });
      const response = await page.goto(route, { waitUntil: 'domcontentloaded' });
      expect(response?.status()).toBe(200);
      await expect(page.locator('main')).toBeVisible();
      await expect(page.locator('h1').first()).toBeVisible();
      if (['/', '/live', '/forecast', '/policy-simulator'].includes(route)) {
        await expect(page.getByText('CAMS-based nationwide estimate', { exact: true })).toBeVisible({ timeout: 60000 });
      }
      if (route === '/research') {
        await expect(page.getByRole('heading', { name: 'Fixed 20:00 IST prospective track record' })).toBeVisible({ timeout: 60000 });
      }
      if (width === 375) {
        await page.getByRole('button', { name: 'Menu', exact: true }).click();
        await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
        await page.getByRole('button', { name: 'Close menu', exact: true }).click();
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)).toBe(false);
      expect(errors).toEqual([]);
    });
  }
}
