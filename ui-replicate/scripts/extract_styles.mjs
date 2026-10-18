#!/usr/bin/env node
// Read the real design tokens of a live page from its computed styles.
//
// Usage:
//   node extract_styles.mjs URL --out DIR [--width 1440] [--height 900] [--fonts] [--storage state.json]
//
// Writes DIR/styles.json (everything) and DIR/styles.md (a short summary to paste into the spec):
//   fonts       families actually used by visible text (by character count), @font-face sources
//   type scale  font-size / weight / line-height / letter-spacing combos, by character count
//   colours     text, background (by painted area), border colours; gradients
//   radii, shadows, spacing (padding/margin/gap values) with counts; the base unit guess (4 or 8)
//   css vars    custom properties on :root (often the site's own tokens)
//   layout      the largest visible boxes (x, y, w, h, bg, radius) to sketch the grid
//   images      <img> sources with rendered and natural size
// Popups, overlays and bottom-stuck badges are hidden first (listed under hidden_layers).
// --fonts downloads the woff2/woff/ttf files named in @font-face rules to DIR/fonts/.
// Only use downloaded fonts in a product when their licence allows it (Google Fonts / OFL: yes;
// paid foundry fonts on someone's site: no; pick the closest free font instead).
import fs from 'node:fs';
import path from 'node:path';
import { launch, contextFor, settle, cleanPage } from './browser.mjs';

const argv = process.argv.slice(2);
const o = { url: argv[0], width: 1440, height: 900, fonts: false };
for (let i = 1; i < argv.length; i++) {
  const k = argv[i], v = argv[i + 1];
  if (k === '--out') { o.out = v; i++; }
  else if (k === '--width') { o.width = Number(v); i++; }
  else if (k === '--height') { o.height = Number(v); i++; }
  else if (k === '--storage') { o.storage = v; i++; }
  else if (k === '--fonts') o.fonts = true;
  else throw new Error('unknown flag ' + k);
}
if (!o.url || !o.out) throw new Error('usage: node extract_styles.mjs URL --out DIR [--width 1440] [--fonts]');
fs.mkdirSync(o.out, { recursive: true });

const browser = await launch();
const ctx = await browser.newContext(contextFor(o.width, o.height, { storage: o.storage }));
const page = await ctx.newPage();
const cssUrls = new Set();
page.on('response', (r) => { if ((r.request().resourceType() === 'stylesheet')) cssUrls.add(r.url()); });
await settle(page, o.url, { wait: 800 });
const hiddenLayers = await cleanPage(page); // popups and badges are not part of the design

const data = await page.evaluate(() => {
  const inc = (m, k, n = 1) => { if (k === undefined || k === null || k === '') return; m[k] = (m[k] || 0) + n; };
  const top = (m, n = 20) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n).map(([value, count]) => ({ value, count: Math.round(count) }));
  const toHex = (c) => {
    const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    if (!m) return c;
    const a = m[4] === undefined ? 1 : Number(m[4]);
    if (a === 0) return null;
    const h = '#' + [m[1], m[2], m[3]].map((v) => Number(Math.round(v)).toString(16).padStart(2, '0')).join('');
    return a < 1 ? `${h} @${a}` : h;
  };
  const visible = (el, r) => r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && getComputedStyle(el).visibility !== 'hidden' && Number(getComputedStyle(el).opacity) > 0.05;

  const fam = {}, combos = {}, sizes = {}, textC = {}, bgC = {}, borderC = {}, radii = {}, shadows = {}, spacing = {}, grads = {};
  const boxes = [];
  const all = document.body.querySelectorAll('*');
  for (const el of all) {
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'META', 'LINK', 'BR'].includes(el.tagName)) continue;
    const r = el.getBoundingClientRect();
    if (!visible(el, r)) continue;
    const s = getComputedStyle(el);
    let own = '';
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent.trim();
    if (own.length) {
      const f = s.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      inc(fam, f, own.length);
      inc(sizes, s.fontSize, own.length);
      inc(combos, `${f} ${s.fontSize}/${s.lineHeight} w${s.fontWeight}${s.letterSpacing !== 'normal' ? ' ls ' + s.letterSpacing : ''}${s.textTransform !== 'none' ? ' ' + s.textTransform : ''}`, own.length);
      inc(textC, toHex(s.color), own.length);
    }
    const area = r.width * r.height;
    inc(bgC, toHex(s.backgroundColor), area / 1000);
    if (s.backgroundImage.includes('gradient')) inc(grads, s.backgroundImage.slice(0, 200));
    if (parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none') inc(borderC, `${s.borderTopWidth} ${toHex(s.borderTopColor)}`);
    if (s.borderRadius !== '0px') inc(radii, s.borderRadius);
    if (s.boxShadow !== 'none') inc(shadows, s.boxShadow);
    for (const p of ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'marginTop', 'marginBottom', 'rowGap', 'columnGap']) {
      const v = s[p];
      if (v && v !== '0px' && v !== 'normal' && v !== 'auto') inc(spacing, v);
    }
    if (area > 4000 && (s.backgroundColor !== 'rgba(0, 0, 0, 0)' || s.borderRadius !== '0px' || s.boxShadow !== 'none' || ['HEADER', 'NAV', 'MAIN', 'ASIDE', 'SECTION', 'FOOTER'].includes(el.tagName))) {
      boxes.push({ tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? String(el.className) : '').split(/\s+/).slice(0, 3).join(' '),
        x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height),
        bg: toHex(s.backgroundColor), radius: s.borderRadius, shadow: s.boxShadow !== 'none' });
    }
  }
  // base unit guess
  const px = Object.entries(spacing).map(([v, c]) => [parseFloat(v), c]).filter(([v]) => v > 0);
  const share = (u) => px.reduce((a, [v, c]) => a + (v % u === 0 ? c : 0), 0) / Math.max(1, px.reduce((a, [, c]) => a + c, 0));
  const base = share(8) > 0.7 ? 8 : share(4) > 0.7 ? 4 : null;

  const vars = {};
  for (const sh of document.styleSheets) {
    let rules; try { rules = sh.cssRules; } catch { continue; }
    for (const rule of rules) {
      if (rule.selectorText && /(^|,)\s*(:root|html)\s*(,|$)/.test(rule.selectorText)) {
        for (const prop of rule.style) if (prop.startsWith('--')) vars[prop] = rule.style.getPropertyValue(prop).trim();
      }
    }
  }
  const faces = [];
  for (const f of document.fonts) faces.push({ family: f.family.replace(/["']/g, ''), weight: f.weight, style: f.style, status: f.status });
  const imgs = [...document.images].filter((i) => i.getBoundingClientRect().width > 0).slice(0, 60)
    .map((i) => ({ src: i.currentSrc || i.src, alt: i.alt, w: Math.round(i.getBoundingClientRect().width), h: Math.round(i.getBoundingClientRect().height), natural: `${i.naturalWidth}x${i.naturalHeight}` }));
  boxes.sort((a, b) => b.w * b.h - a.w * a.h);
  return {
    title: document.title,
    page: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight, body_bg: toHex(getComputedStyle(document.body).backgroundColor) },
    fonts_used: top(fam, 10), font_faces: faces, font_sizes: top(sizes, 20), type_combos: top(combos, 25),
    text_colours: top(textC, 15), background_colours: top(bgC, 15), border_colours: top(borderC, 10), gradients: top(grads, 8),
    radii: top(radii, 12), shadows: top(shadows, 8), spacing: top(spacing, 20), base_unit_guess: base,
    css_variables: vars, boxes: boxes.slice(0, 40), images: imgs,
  };
});

// @font-face sources: read every stylesheet the page loaded (cross-origin sheets block cssRules)
const faceSrc = [];
for (const u of cssUrls) {
  try {
    const css = await (await fetch(u)).text();
    for (const block of css.match(/@font-face\s*{[^}]*}/g) || []) {
      const family = (block.match(/font-family:\s*["']?([^;"']+)/) || [])[1];
      const weight = (block.match(/font-weight:\s*([^;]+)/) || [])[1];
      const urls = [...block.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map((m) => new URL(m[1], u).href);
      faceSrc.push({ family, weight, urls, sheet: u });
    }
  } catch {}
}
// also inline <style> blocks
const inlineCss = await page.evaluate(() => [...document.querySelectorAll('style')].map((s) => s.textContent).join('\n'));
for (const block of inlineCss.match(/@font-face\s*{[^}]*}/g) || []) {
  const family = (block.match(/font-family:\s*["']?([^;"']+)/) || [])[1];
  const weight = (block.match(/font-weight:\s*([^;]+)/) || [])[1];
  const urls = [...block.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map((m) => new URL(m[1], page.url()).href);
  faceSrc.push({ family, weight, urls, sheet: 'inline' });
}
data.font_face_sources = faceSrc;
data.url = page.url();
data.hidden_layers = hiddenLayers;
data.viewport = { width: o.width, height: o.height };

if (o.fonts) {
  const dir = path.join(o.out, 'fonts');
  fs.mkdirSync(dir, { recursive: true });
  const used = new Set(data.fonts_used.map((f) => f.value.toLowerCase()));
  data.fonts_downloaded = [];
  for (const f of faceSrc) {
    if (f.family && !used.has(f.family.toLowerCase())) continue;
    const u = f.urls.find((x) => /\.woff2(\?|$)/.test(x)) || f.urls[0];
    if (!u || u.startsWith('data:')) continue;
    try {
      const buf = Buffer.from(await (await fetch(u)).arrayBuffer());
      const name = `${(f.family || 'font').replace(/\W+/g, '-')}-${String(f.weight || '400').replace(/\W+/g, '-')}${path.extname(new URL(u).pathname) || '.woff2'}`;
      fs.writeFileSync(path.join(dir, name), buf);
      data.fonts_downloaded.push({ family: f.family, weight: f.weight, file: path.join(dir, name), from: u });
    } catch {}
  }
}
await browser.close();

fs.writeFileSync(path.join(o.out, 'styles.json'), JSON.stringify(data, null, 2));
const L = [];
const list = (arr, n = 8) => arr.slice(0, n).map((x) => `\`${x.value}\` (${x.count})`).join(', ') || '-';
L.push(`# Styles of ${data.url}`, '', `Viewport ${o.width}x${o.height}; page ${data.page.width}x${data.page.height}; body bg ${data.page.body_bg}.`, '');
L.push(`- **Fonts used** (by characters): ${list(data.fonts_used, 6)}`);
L.push(`- **Font sizes**: ${list(data.font_sizes, 12)}`);
L.push(`- **Type combos**:`, ...data.type_combos.slice(0, 12).map((x) => `  - \`${x.value}\` (${x.count} chars)`));
L.push(`- **Text colours**: ${list(data.text_colours)}`);
L.push(`- **Backgrounds** (by area): ${list(data.background_colours)}`);
L.push(`- **Borders**: ${list(data.border_colours, 6)}`);
L.push(`- **Radii**: ${list(data.radii, 10)}`);
L.push(`- **Shadows**: ${list(data.shadows, 4)}`);
L.push(`- **Spacing**: ${list(data.spacing, 14)}; base unit guess: ${data.base_unit_guess ?? 'none'}`);
L.push(`- **Gradients**: ${data.gradients.length}`);
L.push(`- **CSS variables on :root**: ${Object.keys(data.css_variables).length}`);
{
  const usedFam = new Set(data.fonts_used.map((f) => f.value.toLowerCase()));
  const allFam = [...new Set(faceSrc.map((f) => f.family).filter(Boolean))];
  const hit = allFam.filter((f) => usedFam.has(f.toLowerCase()));
  L.push(`- **@font-face sources**: used: ${hit.join(', ') || 'none (system or fallback fonts)'}; ${allFam.length - hit.length} more declared but unused`);
}
if (data.fonts_downloaded) L.push(`- **Fonts downloaded**: ${data.fonts_downloaded.length} files in fonts/ (check the licence before shipping)`);
L.push('', '## Largest boxes (x, y, w, h)', ...data.boxes.slice(0, 15).map((b) => `- ${b.tag}${b.cls ? '.' + b.cls.replace(/ /g, '.') : ''} ${b.x},${b.y} ${b.w}x${b.h} bg ${b.bg} r ${b.radius}${b.shadow ? ' shadow' : ''}`));
fs.writeFileSync(path.join(o.out, 'styles.md'), L.join('\n') + '\n');
console.log(L.slice(0, 20).join('\n'));
console.log(`\nwrote ${path.join(o.out, 'styles.json')} and styles.md`);
