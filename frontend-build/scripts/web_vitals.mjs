#!/usr/bin/env node
// Measure how fast and stable a page is, the way a phone user feels it (a quick, local stand-in for
// Lighthouse). Loads the page in Chromium with a mid-range phone profile (4x slower CPU, fast-4G
// network) and reports: LCP (largest paint), CLS (layout shift), FCP, TBT (main-thread blocking),
// total bytes by type, JS size, oversized images (bigger files than shown), images without set
// size, render-blocking CSS/JS, font files, request count. Scores each against a budget.
//
// Usage:
//   node web_vitals.mjs URL [--desktop] [--runs 3] [--out vitals.json]
//                      [--budget-lcp 2500] [--budget-cls 0.1] [--budget-tbt 300] [--budget-js 350]
//
// Exit 0 = all within budget, 2 = something over budget, 1 = could not run.
// For the official numbers also run: npx lighthouse URL --preset=perf --view   (needs Chrome)
import fs from 'node:fs';

function parse(a) {
  const o = { url: a[0], desktop: false, runs: 1, budget: { lcp: 2500, cls: 0.1, tbt: 300, js: 350, fcp: 1800 } };
  for (let i = 1; i < a.length; i++) {
    const k = a[i], v = a[i + 1];
    if (k === '--desktop') o.desktop = true;
    else if (k === '--runs') { o.runs = Number(v); i++; }
    else if (k === '--out') { o.out = v; i++; }
    else if (k.startsWith('--budget-')) { o.budget[k.slice(9)] = Number(v); i++; }
  }
  if (!o.url) { console.error('usage: node web_vitals.mjs URL [--desktop] [--runs 3] [--out vitals.json]'); process.exit(1); }
  return o;
}

async function launch() {
  let pw;
  try { pw = await import('playwright'); } catch { pw = await import('playwright-core'); }
  const opts = { args: ['--no-sandbox'] };
  if (process.env.CHROME_PATH) opts.executablePath = process.env.CHROME_PATH;
  return pw.chromium.launch(opts);
}

const OBSERVE = () => {
  window.__v = { lcp: 0, cls: 0, fcp: 0, longTasks: [], lcpEl: '' , shifts: [] };
  new PerformanceObserver((l) => { for (const e of l.getEntries()) { window.__v.lcp = e.startTime;
    const el = e.element; window.__v.lcpEl = el ? (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.currentSrc ? ' ' + el.currentSrc.slice(0, 100) : '')) : ''; } })
    .observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__v.cls += e.value;
    window.__v.shifts.push({ value: +e.value.toFixed(4), nodes: (e.sources || []).map(s => s.node ? (s.node.nodeName || '').toLowerCase() + (s.node.className && typeof s.node.className === 'string' ? '.' + s.node.className.split(' ')[0] : '') : '').filter(Boolean).slice(0, 3) }); } })
    .observe({ type: 'layout-shift', buffered: true });
  new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__v.fcp = e.startTime; })
    .observe({ type: 'paint', buffered: true });
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__v.longTasks.push([e.startTime, e.duration]); })
    .observe({ type: 'longtask', buffered: true }); } catch {}
};

async function once(browser, o) {
  const ctx = await browser.newContext(o.desktop ? { viewport: { width: 1440, height: 900 } }
    : { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  if (!o.desktop) {
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 1.6 * 1024 * 1024 / 8 * 5, uploadThroughput: 750 * 1024 / 8 });
  }
  const bytes = {}; let requests = 0; const sizes = new Map();
  cdp.on('Network.responseReceived', (e) => sizes.set(e.requestId, { url: e.response.url, type: e.type, mime: e.response.mimeType }));
  cdp.on('Network.loadingFinished', (e) => { const r = sizes.get(e.requestId); if (!r) return; requests++;
    const t = r.type === 'Script' ? 'js' : r.type === 'Stylesheet' ? 'css' : r.type === 'Image' ? 'img' : r.type === 'Font' ? 'font' : r.type === 'Document' ? 'html' : 'other';
    bytes[t] = (bytes[t] || 0) + e.encodedDataLength; r.bytes = e.encodedDataLength; });
  await page.addInitScript(OBSERVE);
  const t0 = Date.now();
  await page.goto(o.url, { waitUntil: 'load', timeout: 90000 });
  try { await page.waitForLoadState('networkidle', { timeout: 15000 }); } catch {}
  await page.waitForTimeout(1500);
  const loadMs = Date.now() - t0;
  const v = await page.evaluate(() => {
    const d = window.__v; const fcp = d.fcp;
    const tbt = d.longTasks.filter(([s]) => s >= fcp).reduce((a, [, dur]) => a + Math.max(0, dur - 50), 0);
    const imgs = [...document.images].filter(i => i.naturalWidth && i.getBoundingClientRect().width).map(i => {
      const r = i.getBoundingClientRect(); const need = r.width * devicePixelRatio;
      return { src: (i.currentSrc || i.src).slice(0, 120), natural: i.naturalWidth, shown: Math.round(r.width), ratio: +(i.naturalWidth / need).toFixed(2),
        sized: i.hasAttribute('width') && i.hasAttribute('height') || getComputedStyle(i).aspectRatio !== 'auto', lazy: i.loading === 'lazy',
        aboveFold: r.top < innerHeight };
    });
    const blocking = [...document.querySelectorAll('head link[rel=stylesheet]:not([media=print]), head script[src]:not([async]):not([defer]):not([type=module])')].map(e => (e.href || e.src).slice(0, 120));
    return { lcp: Math.round(d.lcp), lcpEl: d.lcpEl, cls: +d.cls.toFixed(3), fcp: Math.round(fcp), tbt: Math.round(tbt), shifts: d.shifts.slice(0, 5), imgs, blocking,
      fonts: performance.getEntriesByType('resource').filter(r => /\.(woff2?|ttf|otf)(\?|$)/.test(r.name)).length };
  });
  await ctx.close();
  return { ...v, loadMs, requests, kb: Object.fromEntries(Object.entries(bytes).map(([k, b]) => [k, Math.round(b / 1024)])), sizes: [...sizes.values()] };
}

async function main() {
  const o = parse(process.argv.slice(2));
  const browser = await launch();
  const runs = [];
  for (let i = 0; i < o.runs; i++) runs.push(await once(browser, o));
  await browser.close();
  const med = (k) => { const a = runs.map(r => r[k]).sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; };
  const r = runs[0];
  const res = { url: o.url, profile: o.desktop ? 'desktop' : 'mobile (4x CPU, fast 4G)', runs: o.runs,
    lcp_ms: med('lcp'), cls: med('cls'), fcp_ms: med('fcp'), tbt_ms: med('tbt'), load_ms: med('loadMs'),
    lcp_element: r.lcpEl, requests: r.requests, kb: r.kb, fonts: r.fonts, layout_shifts: r.shifts };
  const issues = [];
  const warn = [];
  if (res.lcp_ms > o.budget.lcp) issues.push(`LCP ${res.lcp_ms} ms > ${o.budget.lcp} (largest element: ${res.lcp_element || '?'})`);
  if (res.cls > o.budget.cls) issues.push(`CLS ${res.cls} > ${o.budget.cls} (shifting: ${r.shifts.flatMap(s => s.nodes).slice(0, 4).join(', ') || '?'})`);
  if (res.tbt_ms > o.budget.tbt) issues.push(`TBT ${res.tbt_ms} ms > ${o.budget.tbt}: too much JavaScript work on load`);
  if ((r.kb.js || 0) > o.budget.js) issues.push(`JS ${r.kb.js} KB > ${o.budget.js} KB (compressed)`);
  if (res.fcp_ms > o.budget.fcp) warn.push(`FCP ${res.fcp_ms} ms > ${o.budget.fcp}`);
  for (const i of r.imgs) {
    if (i.ratio > 2.2 && i.natural > 400) warn.push(`image ${i.natural}px wide shown at ${i.shown}px (${i.ratio}x too big): ${i.src}`);
    if (!i.sized) warn.push(`image without width/height or aspect-ratio (layout shift risk): ${i.src}`);
    if (i.aboveFold && i.lazy) warn.push(`above-the-fold image is lazy-loaded (slower LCP): ${i.src}`);
    if (!i.aboveFold && !i.lazy && i.natural > 300) warn.push(`below-the-fold image not lazy-loaded: ${i.src}`);
  }
  const bigImgs = r.sizes.filter(s => s.type === 'Image' && s.bytes > 250 * 1024);
  bigImgs.forEach(s => warn.push(`image file ${Math.round(s.bytes / 1024)} KB: ${s.url.slice(0, 120)} (use WebP/AVIF, resize)`));
  r.blocking.forEach(b => warn.push(`render-blocking: ${b}`));
  if (r.fonts > 4) warn.push(`${r.fonts} font files: keep to 2-4 (subset, woff2)`);
  res.over_budget = issues; res.warnings = warn.slice(0, 25);
  console.log(`${o.url} [${res.profile}]`);
  console.log(`  LCP ${res.lcp_ms} ms | CLS ${res.cls} | FCP ${res.fcp_ms} ms | TBT ${res.tbt_ms} ms | ${res.requests} requests | ${JSON.stringify(res.kb)} KB`);
  issues.forEach(i => console.log(`  OVER  ${i}`));
  res.warnings.forEach(w => console.log(`  warn  ${w}`));
  if (o.out) fs.writeFileSync(o.out, JSON.stringify(res, null, 2));
  console.log(JSON.stringify({ lcp_ms: res.lcp_ms, cls: res.cls, tbt_ms: res.tbt_ms, over_budget: issues.length, warnings: warn.length }));
  process.exit(issues.length ? 2 : 0);
}
main().catch((e) => { console.error(e); process.exit(1); });
