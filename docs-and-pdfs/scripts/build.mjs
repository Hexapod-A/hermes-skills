#!/usr/bin/env node
// Notes (Markdown or HTML) -> branded PDF (+ optional DOCX, PNG page previews) with checks.
// Usage: node build.mjs input.md --out out.pdf [--brand 3xagentic] [--brands-dir DIR] [--page Letter|A4]
//                     [--var client="Acme Dental" --var date=2026-10-04] [--docx] [--preview] [--strict]
// Markdown may start with front matter:  ---\ntitle: ...\nsubtitle: ...\nclient: ...\ndate: ...\n---
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { marked } from 'marked';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKILL = path.resolve(HERE, '..');

function args(argv) {
  const a = { _: [], var: [] };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t.startsWith('--')) {
      const k = t.slice(2), n = argv[i + 1];
      const v = n === undefined || n.startsWith('--') ? true : (i++, n);
      if (k === 'var') a.var.push(v); else a[k] = v;
    } else a._.push(t);
  }
  return a;
}
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function frontMatter(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return [{}, src];
  const fm = {};
  for (const line of m[1].split('\n')) { const i = line.indexOf(':'); if (i > 0) fm[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^["']|["']$/g, ''); }
  return [fm, src.slice(m[0].length)];
}

function loadBrand(name, dir) {
  const dirs = [dir, process.env.FLYER_BRANDS_DIR, path.resolve(SKILL, '..', 'flyer-studio', 'brands')].filter(Boolean);
  for (const d of dirs) { const f = path.join(d, name, 'brand.json'); if (fs.existsSync(f)) return { dir: path.dirname(f), ...JSON.parse(fs.readFileSync(f, 'utf8')) }; }
  throw new Error(`brand ${name} not found in ${dirs.join(', ')}`);
}
function logoFor(brand) {
  const L = brand.logo || {}; const main = L.file && path.join(brand.dir, L.file); const fb = L.fallback && path.join(brand.dir, L.fallback);
  if (main && fs.existsSync(main) && !/data-placeholder="true"/.test(fs.readFileSync(main, 'utf8'))) return pathToFileURL(main).href;
  if (fb && fs.existsSync(fb)) return pathToFileURL(fb).href;
  return null;
}

async function main() {
  const a = args(process.argv.slice(2));
  const input = a._[0];
  if (!input) { console.error('usage: node build.mjs input.md --out out.pdf [--docx] [--preview]'); process.exit(1); }
  const out = path.resolve(a.out || input.replace(/\.(md|markdown|html?)$/i, '') + '.pdf');
  const brand = loadBrand(a.brand || '3xagentic', a['brands-dir']);
  let src = fs.readFileSync(input, 'utf8');
  let [fm, body] = /\.html?$/i.test(input) ? [{}, src] : frontMatter(src);
  const vars = { date: new Date().toISOString().slice(0, 10), ...fm };
  for (const kv of a.var) { const i = String(kv).indexOf('='); vars[kv.slice(0, i)] = kv.slice(i + 1); }
  const today = new Date().toISOString().slice(0, 10);
  for (const k of Object.keys(vars)) vars[k] = String(vars[k]).replace(/{{\s*([\w.-]+)\s*}}/g, (m, kk) => (kk in vars && !/{{/.test(vars[kk]) ? vars[kk] : (kk === 'date' ? today : m)));
  body = body.replace(/{{\s*([\w.-]+)\s*}}/g, (m, k) => (k in vars ? vars[k] : m));
  const html = /\.html?$/i.test(input) ? body : marked.parse(body);
  const c = brand.colors, f = brand.fonts;
  const faces = Object.values(f).filter((x) => x.file).map((x) => `@font-face{font-family:"${x.family}";src:url("${pathToFileURL(path.join(brand.dir, x.file)).href}");font-weight:${x.weight_range || '100 900'}}`).join('\n');
  const logo = logoFor(brand);
  const metaBits = ['client', 'prepared_by', 'date', 'valid_until'].filter((k) => vars[k]).map((k) => `<div>${esc(k.replace('_', ' ').replace(/^./, (s) => s.toUpperCase()))}<b>${esc(vars[k])}</b></div>`).join('');
  const cover = vars.title ? `<header class="cover">${logo ? `<img class="logo" src="${logo}" alt="${esc(brand.name)}">` : `<div class="brandname">${esc(brand.name)}</div>`}
<h1>${esc(vars.title)}</h1>${vars.subtitle ? `<p class="subtitle">${esc(vars.subtitle)}</p>` : ''}<div class="meta">${metaBits}</div>
<div class="blocks"><i style="right:0;bottom:0;width:16mm;height:22mm"></i><i style="right:20mm;bottom:0;width:14mm;height:11mm"></i><i style="right:16mm;bottom:11mm;width:4mm;height:4mm;background:var(--fg)"></i></div></header>` : '';
  const doc = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(vars.title || path.basename(input))}</title><style>${faces}
:root{--bg:${c.bg};--fg:${c.fg};--accent:${c.accent};--muted:${c.muted || '#999'};--font-head:"${f.heading.family}",sans-serif;--font-body:"${f.body.family}",sans-serif;--page-size:${a.page || 'Letter'}}
${fs.readFileSync(path.join(SKILL, 'templates', 'doc.css'), 'utf8')}</style></head><body>${cover}<main>${html}</main></body></html>`;
  const htmlOut = out.replace(/\.pdf$/i, '.html');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(htmlOut, doc);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(pathToFileURL(htmlOut).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const checks = await page.evaluate((fams) => {
    const errors = [], warnings = [];
    const used = new Set([...document.querySelectorAll('body *')].map((e) => getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim()));
    for (const fam of fams) if (used.has(fam) && ![...document.fonts].some((x) => x.family.replace(/"/g, '') === fam && x.status === 'loaded')) errors.push(`font not loaded: ${fam}`);
    const main = document.querySelector('main'); const W = main.clientWidth;
    for (const el of main.querySelectorAll('table, img, pre')) if (el.scrollWidth > W + 2 || el.getBoundingClientRect().width > W + 2) warnings.push(`${el.tagName.toLowerCase()} wider than the page: shrink columns or split it`);
    for (const img of document.querySelectorAll('img')) if (!img.complete || !img.naturalWidth) errors.push(`image failed to load: ${img.getAttribute('src')}`);
    const lum = (s) => { const m = (s.match(/[\d.]+/g) || [0, 0, 0]).slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; };
    const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const b = getComputedStyle(e).backgroundColor; if (b && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)|transparent/.test(b)) return b; } return 'rgb(255,255,255)'; };
    for (const el of document.querySelectorAll('body *')) {
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
      const a = lum(getComputedStyle(el).color), b = lum(bgOf(el)); const r = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (r < 4.5) errors.push(`low contrast ${r.toFixed(2)}:1 on "${el.textContent.trim().slice(0, 40)}"`);
    }
    const text = document.body.innerText;
    const left = text.match(/{{\s*[\w.-]+\s*}}|\[(?:REPLACE|TODO|TBD)[^\]]*\]/gi);
    if (left) warnings.push(`unfilled placeholders: ${[...new Set(left)].slice(0, 8).join(', ')}`);
    return { errors, warnings };
  }, [f.heading.family, f.body.family]);
  const foot = `<div style="width:100%;font-size:7.5pt;color:#888;padding:0 20mm;display:flex;justify-content:space-between;font-family:Helvetica,Arial,sans-serif"><span>${esc(brand.name)}${brand.website ? ' · ' + esc(brand.website) : ''}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;
  await page.pdf({ path: out, format: a.page || 'Letter', printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true, headerTemplate: '<span></span>', footerTemplate: foot });
  await browser.close();

  let pages = null;
  try { pages = Number((execFileSync('pdfinfo', [out]).toString().match(/Pages:\s+(\d+)/) || [])[1]); } catch { pages = null; }
  const result = { pdf: out, html: htmlOut, pages, errors: checks.errors, warnings: checks.warnings };
  if (a.preview) {
    try { execFileSync('pdftoppm', ['-png', '-r', '60', out, out.replace(/\.pdf$/i, '-page')]); result.previews = fs.readdirSync(path.dirname(out)).filter((x) => x.startsWith(path.basename(out, '.pdf') + '-page') && x.endsWith('.png')).map((x) => path.join(path.dirname(out), x)); }
    catch { result.warnings.push('preview needs pdftoppm (apt install poppler-utils)'); }
  }
  if (a.docx) {
    try {
      const docx = out.replace(/\.pdf$/i, '.docx');
      if (/\.html?$/i.test(input)) execFileSync('pandoc', [htmlOut, '-o', docx]);
      else { const tmp = out.replace(/\.pdf$/i, '.filled.md'); fs.writeFileSync(tmp, (vars.title ? `# ${vars.title}\n\n${vars.subtitle ? `_${vars.subtitle}_\n\n` : ''}` : '') + body); execFileSync('pandoc', [tmp, '-o', docx]); fs.unlinkSync(tmp); }
      result.docx = docx;
    } catch (e) { result.warnings.push('DOCX needs pandoc (apt install pandoc): ' + String(e.message).slice(0, 120)); }
  }
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.errors.length || (a.strict && result.warnings.length) ? 2 : 0);
}
main().catch((e) => { console.error(e.stack || String(e)); process.exit(1); });
