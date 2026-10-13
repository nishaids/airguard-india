// Capture the two application panels from the deployed production site.
//
// Read-only page views of the public site at a compact viewport (650 CSS px, above the
// 640 px breakpoint, so desktop type sizes are kept) and a device scale factor of 3 for
// print resolution. Nothing is clicked, typed or submitted. Element boxes are written to
// capture.json so that the figure script crops by measured geometry, not by eye.
//
// Run from the webapp directory (for module resolution):
//   node ../paper/conference_final/scripts/capture_application.cjs
const path = require('path');
const fs = require('fs');
const { chromium } = require(require.resolve('@playwright/test', { paths: [process.cwd()] }));

const OUT = path.resolve(__dirname, '..', 'figures', 'app_capture');
const SITE = 'https://webapp-phi-taupe.vercel.app';
const PLACE = '?lat=13.1147&lon=80.10981&name=Avadi%2C+Tamil+Nadu%2C+India&region=Tamil+Nadu&country=IN';
const VIEWPORT = { width: 650, height: 1500 };
const SCALE = 3;

async function boxes(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    const rect = (node) => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
    const out = { element: rect(el), scrollY: window.scrollY, text: el.innerText };
    let previous = el.previousElementSibling;
    out.previous = previous ? { ...rect(previous), text: previous.innerText.slice(0, 120) } : null;
    let next = el.nextElementSibling;
    out.next = next ? { ...rect(next), text: next.innerText.slice(0, 160) } : null;
    return out;
  }, selector);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: SCALE, locale: 'en-IN', timezoneId: 'Asia/Kolkata' });
  const page = await context.newPage();
  const meta = { site: SITE, captured_at_utc: new Date().toISOString(), viewport: VIEWPORT, device_scale_factor: SCALE, panels: {} };

  await page.goto(SITE + '/live' + PLACE, { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForFunction(() => { const el = document.querySelector('.live-headlines'); return el && /Issued/.test(el.innerText); }, null, { timeout: 90000 });
  await page.waitForTimeout(1200);
  meta.panels.live = { url: page.url(), ...(await boxes(page, '.live-headlines')) };
  await page.screenshot({ path: path.join(OUT, 'live_full.png') });

  await page.goto(SITE + '/research' + PLACE, { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForFunction(() => { const el = document.querySelector('dl.research-details'); return el && /IST \//.test(el.innerText) && /Prospective verification/.test(el.innerText); }, null, { timeout: 90000 });
  await page.waitForTimeout(1200);
  meta.panels.research = { url: page.url(), ...(await boxes(page, 'dl.research-details')) };
  await page.screenshot({ path: path.join(OUT, 'research_full.png') });

  await browser.close();
  fs.writeFileSync(path.join(OUT, 'capture.json'), JSON.stringify(meta, null, 1));
  for (const [name, panel] of Object.entries(meta.panels)) {
    console.log(name, JSON.stringify(panel.element), 'prev', JSON.stringify(panel.previous && { y: panel.previous.y, h: panel.previous.height, t: panel.previous.text }),
      'next', JSON.stringify(panel.next && { y: panel.next.y, h: panel.next.height, t: panel.next.text.slice(0, 60) }));
    console.log(panel.text.replace(/\n+/g, ' | ').slice(0, 700));
  }
})().catch((error) => { console.error(error); process.exit(1); });
