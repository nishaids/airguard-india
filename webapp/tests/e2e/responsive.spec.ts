import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const routes = ['/', '/live', '/forecast', '/city-atlas', '/policy-simulator', '/research', '/research/track-record', '/historical-replay', '/research/historical-atlas', '/research/historical-policy', '/research/legacy', '/model-insights', '/methods', '/status'];
for (const width of [375,1280]) for (const route of routes) {
  test(`responsive ${width} ${route}`, async ({page}) => {
    await page.setViewportSize({width,height:1000});
    await page.goto(route, {waitUntil:'domcontentloaded'});
    await expect(page.locator('main')).toBeVisible();
    await expect(page.locator('h1').first()).toBeVisible();
    if (['/','/live','/forecast','/policy-simulator'].includes(route)) {
      await expect(page.getByText('CAMS-based nationwide estimate',{exact:true})).toBeVisible({timeout:60000});
      await expect(page.locator('input[type="date"]')).toHaveCount(0);
    }
    if (route==='/status') await expect(page.getByRole('heading',{name:'20:00 IST prospective issuance'})).toBeVisible({timeout:60000});
    if (['/research','/research/track-record'].includes(route)) await expect(page.getByRole('heading',{name:'Fixed 20:00 IST prospective track record'})).toBeVisible({timeout:60000});
    if(width===375) {
      await page.getByRole('button',{name:'Menu',exact:true}).click();
      await expect(page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Live air quality',exact:true})).toBeVisible();
      await page.getByRole('button',{name:'Close menu',exact:true}).click();
    }
    const overflow=await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth+1);
    expect(overflow).toBe(false);
    const folder=path.resolve('..','docs','screens');await mkdir(folder,{recursive:true});
    const name=route==='/'?'home':route.slice(1).replaceAll('/','-');
    await page.screenshot({path:path.join(folder,`${name}-${width}.png`),fullPage:true});
    if(route==='/live' && width===1280) {
      await page.screenshot({path:path.join(folder,'live-headlines-1280.png')});
      await page.getByRole('button',{name:'Show hourly chart'}).click();
      await expect(page.locator('.live-chart svg').first()).toBeVisible();
    }
  });
}

test('atlas opens real map with source distinctions and table fallback',async({page})=>{
  await page.goto('/city-atlas');
  await page.getByRole('button',{name:'Open source map'}).click();
  await expect(page.getByRole('region',{name:'Air quality source map'})).toBeVisible();
  await expect(page.getByText(/Solid circles: measured monitoring locations/)).toBeVisible();
  await expect(page.locator('table')).toBeVisible();
});
