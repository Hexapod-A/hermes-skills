#!/usr/bin/env node
// Load pages in a real browser at phone, tablet and desktop widths and report what is broken:
// console errors, page crashes, failed requests, sideways scroll (and which element causes it),
// broken images, missing alt text, unlabeled buttons/links/inputs, tiny tap targets, tiny text,
// low-contrast text, missing title/lang/h1, and (with --links) dead links. Saves a screenshot per width.
//
// Usage:
//   node ui_check.mjs URL [URL...] [--out DIR] [--widths 320,375,414,768,1440] [--height 900]
//                    [--links] [--max-links 60] [--wait 800] [--storage state.json] [--no-shots]
//                    [--ignore "regex for console messages to ignore"] [--axe]
//
// Exit code: 0 = no errors, 2 = errors found (warnings alone do not fail), 1 = could not run.
// Needs Playwright: `npm install playwright && npx playwright install chromium` (or set CHROME_PATH).
// --axe also runs axe-core if it is installed (`npm install axe-core`).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

function parse(argv) {
  const o = { urls: [], out: 'ui-check', widths: [320, 375, 414, 768, 1440], height: 900, links: false, maxLinks: 60,
    wait: 800, shots: true, ignore: null, axe: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i], v = argv[i + 1];
    if (k === '--out') { o.out = v; i++; }
    else if (k === '--widths') { o.widths = v.split(',').map(Number); i++; }
    else if (k === '--height') { o.height = Number(v); i++; }
    else if (k === '--max-links') { o.maxLinks = Number(v); i++; }
    else if (k === '--wait') { o.wait = Number(v); i++; }
    else if (k === '--storage') { o.storage = v; i++; }
    else if (k === '--ignore') { o.ignore = new RegExp(v); i++; }
    else if (k === '--links') o.links = true;
    else if (k === '--axe') o.axe = true;
    else if (k === '--no-shots') o.shots = false;
    else if (k.startsWith('--')) { console.error(`unknown flag ${k}`); process.exit(1); }
    else o.urls.push(k);
  }
  if (!o.urls.length) { console.error('usage: node ui_check.mjs URL [--out DIR] [--widths ...] [--links]'); process.exit(1); }
  return o;
}

async function launch() {
  let pw;
  try { pw = await import('playwright'); } catch { pw = await import('playwright-core'); }
  const opts = { args: ['--no-sandbox', '--hide-scrollbars'] };
  if (process.env.CHROME_PATH) opts.executablePath = process.env.CHROME_PATH;
  return pw.chromium.launch(opts);
}

const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

// Runs inside the page. Everything here must be self-contained.
function audit({ phone }) {
  const W = document.documentElement.clientWidth;
  const vis = (el) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0.05 && r.width > 0 && r.height > 0; };
  const label = (el) => { const id = el.id ? `#${el.id}` : ''; const cls = typeof el.className === 'string' && el.className.trim()
    ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''; return `${el.tagName.toLowerCase()}${id}${cls}`.slice(0, 80); };
  const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.value ||
    (el.querySelector('img[alt]') && el.querySelector('img[alt]').alt) ||
    (el.getAttribute('aria-labelledby') && document.getElementById(el.getAttribute('aria-labelledby'))?.innerText) || '').trim();
  const out = { scrollWidth: document.documentElement.scrollWidth, clientWidth: W, overflow: [], brokenImages: [], noAlt: [],
    unnamedControls: [], unlabeledInputs: [], smallTargets: [], smallText: 0, lowContrast: [], meta: {} };
  out.meta = { title: document.title, lang: document.documentElement.lang, h1: document.querySelectorAll('h1').length,
    viewportMeta: !!document.querySelector('meta[name=viewport]') };
  // sideways scroll: elements whose right edge passes the viewport and are not inside a clipping parent
  const clipped = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const s = getComputedStyle(p); if (/(hidden|clip|auto|scroll)/.test(s.overflowX)) return true; } return false; };
  if (out.scrollWidth > W + 1) {
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > W + 1 || r.left < -1) && getComputedStyle(el).position !== 'fixed' && !clipped(el))
        out.overflow.push({ el: label(el), right: Math.round(r.right), width: Math.round(r.width) });
      if (out.overflow.length >= 8) break;
    }
  }
  for (const img of document.images) {
    if (img.complete && img.naturalWidth === 0 && (img.currentSrc || img.src)) out.brokenImages.push((img.currentSrc || img.src).slice(0, 160));
    if (!img.hasAttribute('alt') && vis(img)) out.noAlt.push((img.currentSrc || img.src).slice(0, 120));
  }
  for (const el of document.querySelectorAll('a[href], button, [role=button], [role=link]')) {
    if (!vis(el)) continue;
    if (!name(el) && !el.querySelector('svg title')) out.unnamedControls.push(label(el));
    if (phone) { const r = el.getBoundingClientRect(); if ((r.width < 32 || r.height < 32) && el.innerText.trim().length < 40 &&
      getComputedStyle(el).display !== 'inline') out.smallTargets.push(`${label(el)} ${Math.round(r.width)}x${Math.round(r.height)}`); }
  }
  for (const el of document.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), select, textarea')) {
    if (!vis(el)) continue;
    const ok = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.id && document.querySelector(`label[for="${el.id}"]`)) || el.closest('label') || el.getAttribute('title');
    if (!ok) out.unlabeledInputs.push(label(el) + (el.placeholder ? ` (placeholder only: "${el.placeholder.slice(0, 30)}")` : ''));
  }
  // text size and contrast on elements that hold their own text
  const lum = (c) => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r, g, b] = m.slice(0, 3).map(Number).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const alpha = (c) => { const m = c.match(/[\d.]+/g); return m && m.length > 3 ? Number(m[3]) : 1; };
  const bgOf = (el) => { for (let p = el; p; p = p.parentElement) { const s = getComputedStyle(p);
    if (s.backgroundImage !== 'none') return null; if (alpha(s.backgroundColor) > 0.9) return s.backgroundColor; } return 'rgb(255,255,255)'; };
  let checked = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (checked > 1500) break;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (!own || !vis(el)) continue;
    checked++;
    const s = getComputedStyle(el); const fs = parseFloat(s.fontSize);
    if (fs < 12) out.smallText++;
    const bg = bgOf(el); if (!bg || alpha(s.color) < 0.9) continue;
    const L1 = lum(s.color), L2 = lum(bg); if (L1 == null || L2 == null) continue;
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const large = fs >= 24 || (fs >= 18.66 && Number(s.fontWeight) >= 700);
    if (ratio < (large ? 3 : 4.5) && out.lowContrast.length < 10)
      out.lowContrast.push(`${label(el)} "${el.innerText.trim().slice(0, 30)}" ${ratio.toFixed(2)}:1`);
  }
  out.links = [...document.querySelectorAll('a[href]')].map(a => a.href).filter(h => /^https?:/.test(h));
  return out;
}

async function settle(page, url, wait) {
  const resp = await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch {}
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < h; y += 600) { await page.evaluate((yy) => window.scrollTo(0, yy), y); await page.waitForTimeout(80); }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(wait);
  return resp;
}

async function checkLinks(links, max) {
  const uniq = [...new Set(links.map(l => l.split('#')[0]))].slice(0, max);
  const bad = [];
  await Promise.all(uniq.map(async (u) => {
    for (const method of ['HEAD', 'GET']) {
      try {
        const r = await fetch(u, { method, redirect: 'follow', signal: AbortSignal.timeout(15000), headers: { 'user-agent': 'Mozilla/5.0 link-check' } });
        if (r.status < 400) return;
        if (method === 'GET') { if (![401, 403, 429, 999].includes(r.status)) bad.push(`${r.status} ${u}`); return; }
      } catch (e) { if (method === 'GET') bad.push(`ERR ${u} (${String(e.cause?.code || e.name)})`); }
    }
  }));
  return { checked: uniq.length, broken: bad };
}

async function main() {
  const o = parse(process.argv.slice(2));
  fs.mkdirSync(o.out, { recursive: true });
  const browser = await launch();
  const report = { pages: [], errors: 0, warnings: 0 };
  for (const url of o.urls) {
    const page_r = { url, widths: {} };
    let allLinks = [];
    for (const w of o.widths) {
      const phone = w <= 500;
      const ctx = await browser.newContext({ viewport: { width: w, height: o.height }, deviceScaleFactor: phone ? 2 : 1,
        isMobile: phone, hasTouch: phone, userAgent: phone ? MOBILE_UA : undefined, storageState: o.storage });
      const page = await ctx.newPage();
      const consoleErrors = [], pageErrors = [], failed = [], http = [];
      page.on('console', (m) => { if (m.type() === 'error' && !(o.ignore && o.ignore.test(m.text()))) consoleErrors.push(m.text().slice(0, 300)); });
      page.on('pageerror', (e) => pageErrors.push(String(e.message || e).slice(0, 300)));
      page.on('requestfailed', (r) => { const f = r.failure()?.errorText || ''; if (!/ERR_ABORTED/.test(f)) failed.push(`${f} ${r.url().slice(0, 160)}`); });
      page.on('response', (r) => { if (r.status() >= 400) http.push(`${r.status()} ${r.url().slice(0, 160)}`); });
      let status = null;
      try { const resp = await settle(page, url, o.wait); status = resp ? resp.status() : null; }
      catch (e) { pageErrors.push(`navigation failed: ${e.message.split('\n')[0]}`); }
      let a = {};
      try { a = await page.evaluate(audit, { phone }); } catch (e) { pageErrors.push(`audit failed: ${e.message.split('\n')[0]}`); }
      if (o.axe) {
        try {
          const req = createRequire(path.join(process.cwd(), 'x.js'));
          const src = fs.readFileSync(req.resolve('axe-core/axe.min.js'), 'utf8');
          await page.addScriptTag({ content: src });
          const res = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ['violations'] })).violations
            .map(v => `${v.impact} ${v.id}: ${v.help} (${v.nodes.length})`));
          a.axe = res;
        } catch (e) { a.axe = [`axe not run: ${e.message.split('\n')[0]}`]; }
      }
      let shot = null;
      if (o.shots) { shot = path.join(o.out, `${slug(url)}-${w}.jpg`); try { await page.screenshot({ path: shot, fullPage: true, type: 'jpeg', quality: 70 }); } catch { shot = null; } }
      allLinks = allLinks.concat(a.links || []);
      delete a.links;
      const errors = [];
      const warnings = [];
      if (status && status >= 400) errors.push(`page returned HTTP ${status}`);
      consoleErrors.forEach(x => errors.push(`console: ${x}`));
      pageErrors.forEach(x => errors.push(`js error: ${x}`));
      if (a.scrollWidth > a.clientWidth + 1) errors.push(`sideways scroll: page is ${a.scrollWidth}px wide at ${a.clientWidth}px; caused by ${a.overflow.map(x => x.el).slice(0, 4).join(', ') || 'unknown'}`);
      (a.brokenImages || []).forEach(x => errors.push(`broken image: ${x}`));
      http.filter(x => !/favicon/.test(x)).forEach(x => warnings.push(`HTTP ${x}`));
      failed.forEach(x => warnings.push(`request failed: ${x}`));
      if (a.meta && !a.meta.title) warnings.push('no <title>');
      if (a.meta && !a.meta.lang) warnings.push('no lang on <html>');
      if (a.meta && a.meta.h1 !== 1) warnings.push(`${a.meta.h1} <h1> elements (want 1)`);
      if (a.meta && !a.meta.viewportMeta) errors.push('no <meta name="viewport">: phones will show a zoomed-out desktop page');
      (a.noAlt || []).slice(0, 10).forEach(x => warnings.push(`image without alt: ${x}`));
      (a.unnamedControls || []).slice(0, 10).forEach(x => warnings.push(`button/link with no name: ${x}`));
      (a.unlabeledInputs || []).slice(0, 10).forEach(x => warnings.push(`input without label: ${x}`));
      (a.smallTargets || []).slice(0, 8).forEach(x => warnings.push(`small tap target: ${x}`));
      if (a.smallText) warnings.push(`${a.smallText} text elements under 12px`);
      (a.lowContrast || []).forEach(x => warnings.push(`low contrast: ${x}`));
      (a.axe || []).forEach(x => warnings.push(`axe: ${x}`));
      page_r.widths[w] = { status, errors, warnings, screenshot: shot };
      report.errors += errors.length; report.warnings += warnings.length;
      await ctx.close();
    }
    if (o.links) page_r.links = await checkLinks(allLinks, o.maxLinks);
    if (page_r.links) { page_r.links.broken.forEach(() => report.errors++); }
    report.pages.push(page_r);
  }
  await browser.close();
  fs.writeFileSync(path.join(o.out, 'report.json'), JSON.stringify(report, null, 2));
  for (const p of report.pages) {
    console.log(`\n${p.url}`);
    for (const [w, r] of Object.entries(p.widths)) {
      console.log(`  ${w}px: ${r.errors.length} errors, ${r.warnings.length} warnings`);
      r.errors.forEach(e => console.log(`    ERROR ${e}`));
      r.warnings.slice(0, 12).forEach(e => console.log(`    warn  ${e}`));
      if (r.warnings.length > 12) console.log(`    ... ${r.warnings.length - 12} more in report.json`);
    }
    if (p.links) { console.log(`  links: ${p.links.checked} checked, ${p.links.broken.length} broken`); p.links.broken.forEach(b => console.log(`    ERROR link ${b}`)); }
  }
  console.log(JSON.stringify({ errors: report.errors, warnings: report.warnings, report: path.join(o.out, 'report.json') }));
  process.exit(report.errors ? 2 : 0);
}

function slug(u) { return u.replace(/^https?:\/\//, '').replace(/[^a-z0-9]+/gi, '_').replace(/_+$/, '').slice(0, 60) || 'page'; }

main().catch((e) => { console.error(e); process.exit(1); });
