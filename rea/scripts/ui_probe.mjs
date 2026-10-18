#!/usr/bin/env node
// UI probe for REA: open each case at its exact viewport, run its actions, capture what a user sees.
// Called by run_cases.py for {"kind":"ui"} targets, or directly:
//   node ui_probe.mjs target.json cases.jsonl out.jsonl
// target.json: {"base_url":"file:///abs/dir/ or http://localhost:3000/", "query":"a=1" (optional),
//               "selector_map":{"#total":".cart .sum"} (optional, when the replica uses other selectors),
//               "shots_dir":"dir", "wait_ms":150, "dpr":1}
// case input:  {"path":"index.html","viewport":[390,844],
//               "actions":[{"click":"#plus"},{"fill":["#coupon","SAVE10"]},{"press":["#coupon","Enter"]},
//                          {"hover":"#btn"},{"select":["#size","L"]},{"wait":200},{"scroll":600}],
//               "capture":{"text":["#total"],"boxes":["#card"],"styles":{"#btn":["background-color"]},
//                          "count":[".item"],"attrs":{"#buy":["disabled"]},"screenshot":true,"full_page":false,
//                          "element_shots":["#buy"]}}
// output:      {"url_path","title","text":{},"boxes":{},"styles":{},"count":{},"attrs":{},"screenshot":"file",
//               "page_errors":[...]} — keys are the ORIGINAL selectors, so outputs compare 1:1.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

async function loadPlaywright() {
  for (const name of ['playwright', 'playwright-core']) {
    try { return await import(name); } catch {}
  }
  const dirs = [process.env.PLAYWRIGHT_DIR, path.join(process.cwd(), 'node_modules'), path.join(os.homedir(), 'node_modules')].filter(Boolean);
  for (const d of dirs) {
    for (const name of ['playwright', 'playwright-core']) {
      try { return createRequire(path.join(d, 'x.js'))(name); } catch {}
    }
  }
  throw new Error('playwright not found: npm install playwright (README) or set PLAYWRIGHT_DIR');
}

const [cfgPath, casesPath, outPath] = process.argv.slice(2);
if (!outPath) { console.error('usage: node ui_probe.mjs target.json cases.jsonl out.jsonl'); process.exit(1); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const cases = fs.readFileSync(casesPath, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
const map = cfg.selector_map || {};
const sel = (s) => map[s] || s;
const shots = cfg.shots_dir || path.join(path.dirname(outPath), 'shots');
fs.mkdirSync(shots, { recursive: true });

const pw = await loadPlaywright();
const launchOpts = { args: ['--no-sandbox', '--font-render-hinting=none', '--hide-scrollbars'] };
if (process.env.CHROME_PATH) launchOpts.executablePath = process.env.CHROME_PATH;
const browser = await pw.chromium.launch(launchOpts);
const out = fs.createWriteStream(outPath);
try {
  for (const c of cases) {
    const t0 = Date.now();
    const inp = c.input || {};
    const [w, h] = inp.viewport || [1440, 900];
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: cfg.dpr || 1, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message || e)));
    let rec;
    try {
      let url = new URL(inp.path || '', cfg.base_url).href;
      if (cfg.query) url += (url.includes('?') ? '&' : '?') + cfg.query;
      await page.goto(url, { waitUntil: 'load', timeout: cfg.timeout_ms || 30000 });
      await page.evaluate(() => document.fonts && document.fonts.ready);
      for (const a of inp.actions || []) {
        if (a.click) await page.click(sel(a.click));
        else if (a.fill) await page.fill(sel(a.fill[0]), String(a.fill[1]));
        else if (a.press) await page.press(sel(a.press[0]), a.press[1]);
        else if (a.hover) await page.hover(sel(a.hover));
        else if (a.select) await page.selectOption(sel(a.select[0]), a.select[1]);
        else if (a.scroll !== undefined) await page.evaluate((y) => window.scrollTo(0, y), a.scroll);
        else if (a.wait) await page.waitForTimeout(a.wait);
      }
      await page.waitForTimeout(cfg.wait_ms ?? 150);
      const cap = inp.capture || {};
      const o = { url_path: new URL(page.url()).pathname.split('/').pop(), title: await page.title() };
      const one = async (s, fn, arg) => {
        const loc = page.locator(sel(s)).first();
        if (!(await loc.count())) return null;
        return loc.evaluate(fn, arg);
      };
      if (cap.text) { o.text = {}; for (const s of cap.text) o.text[s] = await one(s, (e) => e.innerText.replace(/\s+/g, ' ').trim()); }
      if (cap.boxes) {
        o.boxes = {};
        for (const s of cap.boxes) o.boxes[s] = await one(s, (e) => { const r = e.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height) }; });
      }
      if (cap.styles) {
        o.styles = {};
        for (const [s, props] of Object.entries(cap.styles)) o.styles[s] = await one(s, (e, ps) => Object.fromEntries(ps.map((p) => [p, getComputedStyle(e).getPropertyValue(p)])), props);
      }
      if (cap.attrs) {
        o.attrs = {};
        for (const [s, names] of Object.entries(cap.attrs)) o.attrs[s] = await one(s, (e, ns) => Object.fromEntries(ns.map((n) => [n, e.getAttribute(n)])), names);
      }
      if (cap.count) { o.count = {}; for (const s of cap.count) o.count[s] = await page.locator(sel(s)).count(); }
      if (cap.screenshot) {
        const f = path.join(shots, `${c.id}.png`);
        await page.screenshot({ path: f, fullPage: !!cap.full_page });
        o.screenshot = f;
      }
      if (cap.element_shots) {
        // Per-part screenshots: a whole-page pixel threshold can hide a small part that changed.
        o.element_shots = {};
        for (const s of cap.element_shots) {
          const loc = page.locator(sel(s)).first();
          if (!(await loc.count())) { o.element_shots[s] = null; continue; }
          const f = path.join(shots, `${c.id}__${s.replace(/[^a-z0-9]+/gi, '_')}.png`);
          await loc.screenshot({ path: f });
          o.element_shots[s] = f;
        }
      }
      o.page_errors = errors;
      rec = { id: c.id, output: o };
    } catch (e) {
      rec = { id: c.id, error: String(e.message || e).split('\n')[0] };
    }
    rec.ms = Date.now() - t0;
    out.write(JSON.stringify(rec) + '\n');
    await ctx.close();
  }
} finally {
  await browser.close();
  out.end();
}
