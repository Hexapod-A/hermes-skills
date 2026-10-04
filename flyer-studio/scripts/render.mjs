#!/usr/bin/env node
// flyer-studio renderer: brand kit + layout template + content JSON -> PNGs, with a self-check report.
// Usage:
//   node render.mjs <spec.json> [--out DIR] [--sizes square,portrait,story,square-4k] [--name NAME]
//                   [--brand NAME] [--layout NAME] [--brands-dir DIR] [--sheet] [--no-fail] [--html-only]
// Exit code: 0 = all checks passed, 2 = at least one blocking error (see report.json), 1 = crash.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { render } from './lib/template.mjs';
import { pageFit, pageChecks } from './lib/page-checks.mjs';
import { pixelContrast } from './lib/contrast.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKILL = path.resolve(HERE, '..');
const TPL = path.join(SKILL, 'templates');

export const SIZES = {
  square:        { w: 1080, h: 1080, dsf: 1, ar: 'square' },
  portrait:      { w: 1080, h: 1350, dsf: 1, ar: 'portrait' },
  story:         { w: 1080, h: 1920, dsf: 1, ar: 'story' },
  'square-4k':   { w: 1080, h: 1080, dsf: 4, ar: 'square' },   // 4320x4320
  'portrait-4k': { w: 1080, h: 1350, dsf: 4, ar: 'portrait' }, // 4320x5400
  'story-4k':    { w: 1080, h: 1920, dsf: 2, ar: 'story' },    // 2160x3840 (UHD vertical)
};
const LAYOUTS = ['announcement', 'offer', 'stat', 'quote', 'carousel', 'checklist'];

function args(argv) {
  const a = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t.startsWith('--')) {
      const k = t.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) a[k] = true; else { a[k] = next; i++; }
    } else a._.push(t);
  }
  return a;
}

function loadBrand(name, brandsDir) {
  const dirs = [brandsDir, process.env.FLYER_BRANDS_DIR, path.join(SKILL, 'brands')].filter(Boolean);
  for (const d of dirs) {
    const f = path.join(d, name, 'brand.json');
    if (fs.existsSync(f)) return { dir: path.dirname(f), ...JSON.parse(fs.readFileSync(f, 'utf8')) };
  }
  throw new Error(`Brand "${name}" not found in ${dirs.join(', ')}. Create brands/${name}/brand.json (see references/brand-kit.md).`);
}

function resolveLogo(brand, warnings) {
  const L = brand.logo || {};
  const main = L.file ? path.join(brand.dir, L.file) : null;
  const fallback = L.fallback ? path.join(brand.dir, L.fallback) : null;
  let use = main && fs.existsSync(main) ? main : null;
  if (use && use.endsWith('.svg') && /data-placeholder="true"/.test(fs.readFileSync(use, 'utf8'))) {
    warnings.push({ type: 'placeholder-logo', detail: `${L.file} is still the placeholder. Using ${L.fallback || 'brand name text'} until the real SVG is dropped in.` });
    use = fallback && fs.existsSync(fallback) ? fallback : null;
  } else if (!use && fallback && fs.existsSync(fallback)) use = fallback;
  return use ? pathToFileURL(use).href : null;
}

function headCss(brand) {
  const c = brand.colors, f = brand.fonts;
  const faces = Object.values(f).filter((x) => x.file).map((x) =>
    `@font-face{font-family:"${x.family}";src:url("${pathToFileURL(path.join(brand.dir, x.file)).href}");font-weight:${x.weight_range || '100 900'};font-style:normal;font-display:block}`).join('\n');
  return `${faces}
:root{--bg:${c.bg};--fg:${c.fg};--accent:${c.accent};--muted:${c.muted || c.fg};--on-accent:${c.on_accent || c.bg};
--font-head:"${f.heading.family}",${f.heading.fallback || 'sans-serif'};--font-body:"${f.body.family}",${f.body.fallback || 'sans-serif'};
--head-weight:${f.heading.weight || 400}}`;
}

function initials(name = '') { return name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join(''); }

function pagesFor(spec) {
  const c = spec.content || {};
  if (spec.layout === 'carousel') {
    const slides = c.slides || [];
    return slides.map((s, i) => ({ suffix: `-s${String(i + 1).padStart(2, '0')}`,
      data: { ...s, slide_index: String(i + 1).padStart(2, '0'), slide_total: String(slides.length).padStart(2, '0'), is_last: i === slides.length - 1 } }));
  }
  if (spec.layout === 'checklist' && Array.isArray(c.items)) {
    return [{ suffix: '', data: { ...c, items: c.items.map((t, i) => ({ n: i + 1, text: typeof t === 'string' ? t : t.text })) } }];
  }
  return [{ suffix: '', data: c }];
}

export async function renderSpec(spec, opt = {}) {
  const warningsGlobal = [];
  const brand = loadBrand(spec.brand || opt.brand, opt.brandsDir);
  const layout = spec.layout;
  if (!LAYOUTS.includes(layout) && !fs.existsSync(path.join(TPL, `${layout}.html`))) throw new Error(`Unknown layout "${layout}". Have: ${LAYOUTS.join(', ')}`);
  const logoUrl = resolveLogo(brand, warningsGlobal);
  const sizes = (opt.sizes || spec.sizes || ['square']).map((s) => { if (!SIZES[s]) throw new Error(`Unknown size ${s}. Have: ${Object.keys(SIZES).join(', ')}`); return s; });
  const outDir = path.resolve(opt.out || spec.out || 'out');
  fs.mkdirSync(outDir, { recursive: true });
  const name = opt.name || spec.name || layout;
  const tpl = fs.readFileSync(path.join(TPL, `${layout}.html`), 'utf8');
  const baseCss = fs.readFileSync(path.join(TPL, 'base.css'), 'utf8');
  const extraCss = spec.css || '';

  const browser = opt.htmlOnly ? null : await chromium.launch({ args: ['--font-render-hinting=none'] });
  const results = [];
  try {
    for (const page of pagesFor(spec)) {
      for (const sizeName of sizes) {
        const S = SIZES[sizeName];
        const d = { ...page.data };
        const align = d.align || spec.align || 'center';
        const decor = d.decor || spec.decor || (align === 'left' ? 'edge' : 'corner');
        const classes = [`ar-${S.ar}`, align === 'left' ? 'align-left' : 'align-center',
          decor === 'corner' ? 'reserve-bottom' : '', decor === 'edge' ? 'reserve-right' : '', decor === 'stairs' ? 'has-stairs' : ''].filter(Boolean).join(' ');
        const data = {
          ...d, classes,
          brand: { ...brand, logo_url: logoUrl, burst: brand.cta?.burst !== false },
          cta_is_url: (d.cta_style || brand.cta?.style) === 'url',
          decor_corner: decor === 'corner', decor_edge: decor === 'edge', decor_stairs: (decor === 'stairs' || (decor !== 'none' && brand.decor?.stairs !== false)),
          max_lines: d.max_lines || (S.ar === 'story' ? 4 : 3),
          initials: d.initials || initials(d.name),
          avatar_url: d.avatar ? pathToFileURL(path.resolve(path.dirname(opt.specPath || '.'), d.avatar)).href : '',
        };
        const decorH = decor === 'corner' ? 'calc(2.1 * var(--u) + 44px)' : '0px';
        const html = `<!doctype html><html><head><meta charset="utf-8"><style>${headCss(brand)}
${baseCss}
:root{--W:${S.w}px;--H:${S.h}px;--decor-h:${decorH};--decor-w:${decor === 'edge' ? 'calc(2.2 * var(--u))' : '0px'}}
.reserve-bottom .frame{bottom:max(var(--pad-bottom), var(--decor-h))}
${brand.css || ''}
${extraCss}</style></head><body>${render(tpl, data, path.join(TPL, 'partials'))}</body></html>`;
        const base = `${name}${page.suffix}-${sizeName}`;
        const htmlPath = path.join(outDir, `${base}.html`);
        fs.writeFileSync(htmlPath, html);
        const rec = { file: path.join(outDir, `${base}.png`), html: htmlPath, size: sizeName, pixels: `${S.w * S.dsf}x${S.h * S.dsf}`, errors: [], warnings: [...warningsGlobal] };
        if (browser) {
          const ctx = await browser.newContext({ viewport: { width: S.w, height: S.h }, deviceScaleFactor: S.dsf });
          const p = await ctx.newPage();
          await p.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load' });
          await p.evaluate(() => document.fonts.ready);
          await p.evaluate(pageFit);
          const families = [brand.fonts.heading.family, brand.fonts.body.family];
          const chk = await p.evaluate(pageChecks, { families, story: S.ar === 'story' });
          const png = await p.screenshot({ type: 'png', clip: { x: 0, y: 0, width: S.w, height: S.h } });
          fs.writeFileSync(rec.file, png);
          rec.errors.push(...chk.errors); rec.warnings.push(...chk.warnings);
          const cr = pixelContrast(png, S.dsf, chk.texts);
          rec.errors.push(...cr.errors); rec.warnings.push(...cr.warnings);
          rec.min_contrast = cr.min;
          await ctx.close();
        }
        // content rules that protect John from fabricated claims
        if (layout === 'stat' && !d.source) rec.errors.push({ type: 'claim-without-source', detail: 'Stat flyers need content.source (where the number comes from). No source, no stat.' });
        if (layout === 'quote' && !d.name) rec.errors.push({ type: 'quote-without-attribution', detail: 'Testimonials need a real person: content.name (and role). Never invent quotes.' });
        results.push(rec);
      }
    }
    if (opt.sheet && browser && results.length > 1) results.sheet = await contactSheet(browser, results, outDir, name);
  } finally { if (browser) await browser.close(); }
  return results;
}

async function contactSheet(browser, results, outDir, name) {
  const cells = results.map((r) => `<figure><img src="${pathToFileURL(r.file).href}"><figcaption>${path.basename(r.file)} ${r.errors.length ? '❌' : '✅'}</figcaption></figure>`).join('');
  const html = `<!doctype html><style>body{margin:0;background:#222;font:20px sans-serif;color:#ddd;display:flex;flex-wrap:wrap;gap:24px;padding:24px;width:2000px;align-items:flex-start}
figure{margin:0;width:470px}img{width:470px;display:block}figcaption{padding:8px 0;word-break:break-all}</style>${cells}`;
  const f = path.join(outDir, `${name}-sheet.html`); fs.writeFileSync(f, html);
  const ctx = await browser.newContext({ viewport: { width: 2048, height: 800 } });
  const p = await ctx.newPage(); await p.goto(pathToFileURL(f).href); await p.waitForLoadState('load');
  const out = path.join(outDir, `${name}-sheet.png`);
  await p.screenshot({ path: out, fullPage: true }); await ctx.close();
  return out;
}

async function main() {
  const a = args(process.argv.slice(2));
  if (!a._[0] && !a.layout) {
    console.error('usage: node render.mjs <spec.json> [--out DIR] [--sizes square,portrait,story,square-4k] [--sheet]');
    process.exit(1);
  }
  const specPath = a._[0] ? path.resolve(a._[0]) : null;
  const spec = specPath ? JSON.parse(fs.readFileSync(specPath, 'utf8')) : {};
  if (a.layout) spec.layout = a.layout;
  if (a.brand) spec.brand = a.brand;
  if (a.content) spec.content = JSON.parse(a.content);
  const res = await renderSpec(spec, { specPath, out: a.out, name: a.name, brandsDir: a['brands-dir'], sizes: a.sizes ? String(a.sizes).split(',') : undefined, sheet: !!a.sheet, htmlOnly: !!a['html-only'] });
  const outDir = path.dirname(res[0].file);
  const report = { ok: res.every((r) => r.errors.length === 0), outputs: res.map((r) => ({ ...r })), sheet: res.sheet || null };
  const reportPath = path.join(outDir, `${a.name || spec.name || spec.layout}-report.json`);
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  for (const r of res) {
    console.log(`${r.errors.length ? 'FAIL' : 'ok  '} ${r.file} (${r.pixels})${r.min_contrast ? ` min contrast ${r.min_contrast.toFixed(1)}:1` : ''}`);
    for (const e of r.errors) console.log(`     ERROR ${e.type}: ${e.detail}`);
    for (const w of r.warnings) console.log(`     warn  ${w.type}: ${w.detail}`);
  }
  if (report.sheet) console.log(`sheet ${report.sheet}`);
  console.log(`report ${reportPath}`);
  process.exit(report.ok || a['no-fail'] ? 0 : 2);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(e.stack || String(e)); process.exit(1); });
}
