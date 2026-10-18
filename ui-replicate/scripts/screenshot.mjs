#!/usr/bin/env node
// Screenshot a URL (a live reference site or your own build) at exact viewports.
//
// Usage:
//   node screenshot.mjs URL --out DIR [--name page] [--widths 1440,390] [--height 900]
//                       [--viewport] [--size-of ref.png] [--wait 600] [--dpr 1] [--no-scroll]
//                       [--hide "selector, selector"] [--clean] [--storage state.json]
//
//   --widths     one PNG per width: DIR/<name>-<width>.png (default 1440,390)
//   --viewport   only the first screen (default: full page)
//   --size-of    take width AND height from a reference PNG (implies --viewport), so the shot
//                lines up 1:1 with the reference for diff_score.py
//   --hide       CSS selectors to hide first (cookie banners, chat bubbles, "made in Webflow" badges)
//   --clean      auto-hide popups/overlays and bottom-stuck badges (use for third-party sites)
//   --storage    Playwright storageState JSON for pages behind a login
//   --dpr        device scale factor (use 2 to compare against a @2x reference without scaling)
//
// Widths <= 500 get a phone context (touch, mobile user agent). Animations are reduced, fonts are
// awaited and the page is scrolled once so lazy images load.
import fs from 'node:fs';
import path from 'node:path';
import { launch, contextFor, settle, cleanPage } from './browser.mjs';

function parse(argv) {
  const o = { widths: [1440, 390], height: 900, wait: 600, scroll: true, full: true, dpr: 1, name: 'page' };
  o.url = argv[0];
  for (let i = 1; i < argv.length; i++) {
    const k = argv[i], v = argv[i + 1];
    if (k === '--out') { o.out = v; i++; }
    else if (k === '--name') { o.name = v; i++; }
    else if (k === '--widths') { o.widths = v.split(',').map(Number); i++; }
    else if (k === '--height') { o.height = Number(v); i++; }
    else if (k === '--wait') { o.wait = Number(v); i++; }
    else if (k === '--dpr') { o.dpr = Number(v); i++; }
    else if (k === '--hide') { o.hide = v; i++; }
    else if (k === '--storage') { o.storage = v; i++; }
    else if (k === '--size-of') { o.sizeOf = v; i++; }
    else if (k === '--viewport') o.full = false;
    else if (k === '--no-scroll') o.scroll = false;
    else if (k === '--clean') o.clean = true;
    else throw new Error('unknown flag ' + k);
  }
  if (!o.url || !o.out) throw new Error('usage: node screenshot.mjs URL --out DIR [flags]');
  return o;
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.toString('ascii', 1, 4) !== 'PNG') throw new Error('--size-of needs a PNG');
  return { width: b.readUInt32BE(16), height: b.readUInt32BE(20) };
}

const o = parse(process.argv.slice(2));
fs.mkdirSync(o.out, { recursive: true });
let sizes = o.widths.map((w) => ({ width: w, height: w <= 500 ? 844 : o.height }));
if (o.sizeOf) { const s = pngSize(o.sizeOf); sizes = [{ width: Math.round(s.width / o.dpr), height: Math.round(s.height / o.dpr) }]; o.full = false; }

const browser = await launch();
try {
  for (const s of sizes) {
    const ctx = await browser.newContext(contextFor(s.width, s.height, { dpr: o.dpr, storage: o.storage }));
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    await settle(page, o.url, { wait: o.wait, scroll: o.scroll });
    if (o.hide) await page.addStyleTag({ content: `${o.hide}{display:none !important}` });
    const hidden = o.clean ? await cleanPage(page) : [];
    if (o.hide || o.clean) await page.waitForTimeout(200);
    const file = path.join(o.out, `${o.name}-${s.width}.png`);
    await page.screenshot({ path: file, fullPage: o.full, animations: 'disabled' });
    const docH = await page.evaluate(() => document.documentElement.scrollHeight);
    const overflowX = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    console.log(JSON.stringify({ file, width: s.width, height: o.full ? docH : s.height, final_url: page.url(), horizontal_overflow: overflowX, hidden, page_errors: errors.slice(0, 5) }));
    await ctx.close();
  }
} finally {
  await browser.close();
}
