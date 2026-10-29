#!/usr/bin/env node
// Compare a live reference page and your build element by element, using the CSS the browser
// actually computed. Elements are paired by their visible text (headings, buttons, links,
// paragraphs, labels), then each pair's styles are compared: font family/size/weight, line height,
// letter spacing, text transform, colour, background, border radius, padding, box size and position.
// This finds the "3px too big", "#FF7A00 vs #FF9900", "600 vs 700 weight" mistakes a pixel score hides.
//
// Usage:
//   node compare_styles.mjs REF_URL BUILD_URL [--widths 1440,390] [--out DIR] [--min-chars 2]
//                           [--pos] [--clean] [--max 400]
//
//   --pos      also compare x/y position (off by default: content above may legitimately differ)
//   --clean    hide popups/cookie bars on both pages first
// Writes DIR/style-diff.json and DIR/style-diff.md. Prints a match % per width and the worst items.
// Exit 0 when every width scores >= 95% of compared properties, 2 below that, 1 on error.
import fs from 'node:fs';
import path from 'node:path';
import { launch, contextFor, settle, cleanPage } from './browser.mjs';

function parse(a) {
  const o = { ref: a[0], build: a[1], widths: [1440, 390], out: 'style-diff', minChars: 2, pos: false, clean: false, max: 400 };
  for (let i = 2; i < a.length; i++) {
    const k = a[i], v = a[i + 1];
    if (k === '--widths') { o.widths = v.split(',').map(Number); i++; }
    else if (k === '--out') { o.out = v; i++; }
    else if (k === '--min-chars') { o.minChars = Number(v); i++; }
    else if (k === '--max') { o.max = Number(v); i++; }
    else if (k === '--pos') o.pos = true;
    else if (k === '--clean') o.clean = true;
    else throw new Error('unknown flag ' + k);
  }
  if (!o.ref || !o.build) throw new Error('usage: node compare_styles.mjs REF_URL BUILD_URL [--widths 1440,390] [--out DIR]');
  return o;
}

// runs in the page: one record per element that holds its own visible text
function collect({ minChars, max }) {
  const out = [];
  const norm = (t) => t.replace(/\s+/g, ' ').trim().toLowerCase();
  for (const el of document.querySelectorAll('body *')) {
    if (out.length >= max) break;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'PATH'].includes(el.tagName)) continue;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ');
    const text = norm(own);
    if (text.length < minChars) continue;
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || r.width === 0 || r.height === 0) continue;
    // background: first non-transparent up the tree
    let bg = 'rgba(0, 0, 0, 0)';
    for (let p = el; p; p = p.parentElement) { const b = getComputedStyle(p).backgroundColor; if (!/rgba\(0, 0, 0, 0\)|transparent/.test(b)) { bg = b; break; } }
    out.push({ text: text.slice(0, 80), tag: el.tagName.toLowerCase(),
      font: s.fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase(), size: parseFloat(s.fontSize), weight: Number(s.fontWeight) || 400,
      lh: s.lineHeight === 'normal' ? +(parseFloat(s.fontSize) * 1.2).toFixed(1) : parseFloat(s.lineHeight),
      ls: s.letterSpacing === 'normal' ? 0 : parseFloat(s.letterSpacing), tt: s.textTransform, style: s.fontStyle,
      color: s.color, bg, radius: parseFloat(s.borderTopLeftRadius) || 0,
      pad: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft].map(parseFloat),
      w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY) });
  }
  return out;
}

function rgb(c) { const m = String(c).match(/[\d.]+/g); return m ? m.slice(0, 4).map(Number) : [0, 0, 0, 1]; }
function hex(c) { const [r, g, b, a = 1] = rgb(c); if (a === 0) return 'transparent'; return '#' + [r, g, b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('') + (a < 1 ? `@${a}` : ''); }
// CIE76 delta-E between two rgb strings (alpha-blended on white)
function dE(c1, c2) {
  const lab = (c) => { let [r, g, b, a = 1] = rgb(c); [r, g, b] = [r, g, b].map(v => (v * a + 255 * (1 - a)) / 255)
    .map(v => v > 0.04045 ? ((v + 0.055) / 1.055) ** 2.4 : v / 12.92);
    let x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047, y = r * 0.2126 + g * 0.7152 + b * 0.0722, z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883;
    const f = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116; [x, y, z] = [f(x), f(y), f(z)];
    return [116 * y - 16, 500 * (x - y), 200 * (y - z)]; };
  const a = lab(c1), b = lab(c2); return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function pair(ref, build) {
  const pool = new Map();
  build.forEach((b, i) => { const k = b.text; if (!pool.has(k)) pool.set(k, []); pool.get(k).push(i); });
  const used = new Set(); const pairs = []; const missing = [];
  for (const r of ref) {
    let idx = (pool.get(r.text) || []).find(i => !used.has(i));
    if (idx === undefined) { // loose match: same first 24 chars
      idx = build.findIndex((b, i) => !used.has(i) && b.text.slice(0, 24) === r.text.slice(0, 24) && r.text.length >= 8);
      if (idx < 0) idx = undefined;
    }
    if (idx === undefined) { missing.push(r.text); continue; }
    used.add(idx); pairs.push([r, build[idx]]);
  }
  const extra = build.filter((_, i) => !used.has(i)).map(b => b.text);
  return { pairs, missing, extra };
}

function diff(r, b, o) {
  const d = [];
  const num = (name, a, c, tol, unit = 'px') => { if (Math.abs(a - c) > tol) d.push({ prop: name, ref: `${a}${unit}`, build: `${c}${unit}`, off: +(c - a).toFixed(2) }); };
  if (r.font !== b.font) d.push({ prop: 'font-family', ref: r.font, build: b.font });
  num('font-size', r.size, b.size, 0.5);
  num('font-weight', r.weight, b.weight, 50, '');
  num('line-height', r.lh, b.lh, 1.5);
  num('letter-spacing', r.ls, b.ls, 0.3);
  if (r.tt !== b.tt) d.push({ prop: 'text-transform', ref: r.tt, build: b.tt });
  if (r.style !== b.style) d.push({ prop: 'font-style', ref: r.style, build: b.style });
  const ce = dE(r.color, b.color); if (ce > 3) d.push({ prop: 'color', ref: hex(r.color), build: hex(b.color), dE: +ce.toFixed(1) });
  const be = dE(r.bg, b.bg); if (be > 3) d.push({ prop: 'background', ref: hex(r.bg), build: hex(b.bg), dE: +be.toFixed(1) });
  num('border-radius', r.radius, b.radius, 1);
  ['padding-top', 'padding-right', 'padding-bottom', 'padding-left'].forEach((n, i) => num(n, r.pad[i], b.pad[i], 2));
  if (['a', 'button', 'input', 'label', 'span', 'li'].includes(r.tag) || r.w < 600) { num('width', r.w, b.w, Math.max(3, r.w * 0.03)); }
  num('height', r.h, b.h, Math.max(3, r.h * 0.05));
  if (o.pos) { num('x', r.x, b.x, 4); num('y', r.y, b.y, 8); }
  return d;
}
const PROPS_COMPARED = 16;

async function grab(browser, url, w, o) {
  const ctx = await browser.newContext(contextFor(w, w <= 500 ? 844 : 900, {}));
  const page = await ctx.newPage();
  await settle(page, url, { wait: 500 });
  if (o.clean) await cleanPage(page);
  const recs = await page.evaluate(collect, { minChars: o.minChars, max: o.max });
  await ctx.close();
  return recs;
}

const o = parse(process.argv.slice(2));
fs.mkdirSync(o.out, { recursive: true });
const browser = await launch();
const report = { ref: o.ref, build: o.build, widths: {} };
let worstScore = 100;
try {
  for (const w of o.widths) {
    const [ref, build] = await Promise.all([grab(browser, o.ref, w, o), grab(browser, o.build, w, o)]);
    const { pairs, missing, extra } = pair(ref, build);
    const items = pairs.map(([r, b]) => ({ text: r.text, tag: r.tag, diffs: diff(r, b, o) })).filter(x => x.diffs.length);
    const total = pairs.length * PROPS_COMPARED;
    const bad = items.reduce((a, x) => a + x.diffs.length, 0);
    const score = total ? +(100 * (1 - bad / total)).toFixed(1) : 0;
    const coverage = ref.length ? +(100 * pairs.length / ref.length).toFixed(1) : 0;
    worstScore = Math.min(worstScore, coverage < 80 ? Math.min(score, coverage) : score);
    // most common fixes: the same prop/ref/build combination across many elements = one token to change
    const tally = {};
    for (const it of items) for (const d of it.diffs) { const k = `${d.prop}: ${d.ref} -> ${d.build}`; tally[k] = (tally[k] || 0) + 1; }
    const common = Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, n]) => `${n}x ${k}`);
    report.widths[w] = { score, text_coverage: coverage, ref_elements: ref.length, paired: pairs.length, mismatched: items.length,
      common_fixes: common, missing_in_build: missing.slice(0, 40), extra_in_build: extra.slice(0, 40), items: items.slice(0, 150) };
    console.log(`${w}px: style match ${score}% of compared properties, text coverage ${coverage}% (${pairs.length}/${ref.length} paired, ${items.length} with differences)`);
    common.slice(0, 6).forEach(c => console.log(`   fix  ${c}`));
    if (missing.length) console.log(`   missing in build: ${missing.slice(0, 5).map(t => JSON.stringify(t)).join(', ')}${missing.length > 5 ? ' ...' : ''}`);
  }
} finally { await browser.close(); }
fs.writeFileSync(path.join(o.out, 'style-diff.json'), JSON.stringify(report, null, 2));
let md = `# Style diff\n\nReference: ${o.ref}\nBuild: ${o.build}\n`;
for (const [w, r] of Object.entries(report.widths)) {
  md += `\n## ${w}px: ${r.score}% match, ${r.text_coverage}% text coverage\n\nMost common fixes:\n${r.common_fixes.map(c => `- ${c}`).join('\n') || '- none'}\n`;
  if (r.missing_in_build.length) md += `\nText in the reference but not in the build:\n${r.missing_in_build.map(t => `- ${t}`).join('\n')}\n`;
  md += `\n| Element | Property | Reference | Build |\n|---|---|---|---|\n`;
  for (const it of r.items.slice(0, 60)) for (const d of it.diffs) md += `| ${it.tag} "${it.text.slice(0, 30)}" | ${d.prop} | ${d.ref} | ${d.build} |\n`;
}
fs.writeFileSync(path.join(o.out, 'style-diff.md'), md);
console.log(JSON.stringify({ worst_score: worstScore, report: path.join(o.out, 'style-diff.md') }));
process.exit(worstScore >= 95 ? 0 : 2);
