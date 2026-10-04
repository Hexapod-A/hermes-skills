// Pixel-based contrast check: compares each text element's colour against the pixels actually
// rendered behind it (so text over a shape, photo or gradient is caught, not just CSS backgrounds).
import { PNG } from 'pngjs';

const parse = (s) => { const m = String(s).match(/[\d.]+/g) || [0, 0, 0]; return m.slice(0, 3).map(Number); };
const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
export const luminance = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
export const ratio = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

export function pixelContrast(pngBuf, dsf, texts) {
  const img = PNG.sync.read(pngBuf);
  const errors = [], warnings = [];
  let min = Infinity;
  for (const t of texts) {
    const fg0 = parse(t.color);
    const x0 = Math.max(0, Math.floor(t.rect.x * dsf)), y0 = Math.max(0, Math.floor(t.rect.y * dsf));
    const x1 = Math.min(img.width, Math.ceil((t.rect.x + t.rect.w) * dsf)), y1 = Math.min(img.height, Math.ceil((t.rect.y + t.rect.h) * dsf));
    if (x1 <= x0 || y1 <= y0) continue;
    const step = Math.max(1, Math.floor(Math.sqrt(((x1 - x0) * (y1 - y0)) / 6000)));
    const bins = new Map(); let total = 0;
    for (let y = y0; y < y1; y += step) for (let x = x0; x < x1; x += step) {
      const i = (y * img.width + x) * 4;
      const p = [img.data[i], img.data[i + 1], img.data[i + 2]];
      total++;
      const d = Math.hypot(p[0] - fg0[0], p[1] - fg0[1], p[2] - fg0[2]);
      if (d < 90) continue; // text pixels and anti-aliasing close to the text colour
      const k = (p[0] >> 4) + ',' + (p[1] >> 4) + ',' + (p[2] >> 4);
      const e = bins.get(k) || { n: 0, s: [0, 0, 0] };
      e.n++; e.s[0] += p[0]; e.s[1] += p[1]; e.s[2] += p[2]; bins.set(k, e);
    }
    // background candidates: (a) non-text pixels inside the box, (b) a ring just outside the box
    const bgPixels = [...bins.values()].reduce((s, e) => s + e.n, 0);
    const majors = bgPixels >= total * 0.05 ? [...bins.values()].filter((e) => e.n >= bgPixels * 0.12).map((e) => e.s.map((v) => v / e.n)) : [];
    const ring = new Map(); let rn = 0;
    const pad = Math.round(8 * dsf), th = Math.max(2, Math.round(6 * dsf));
    const rx0 = x0 - pad - th, ry0 = y0 - pad - th, rx1 = x1 + pad + th, ry1 = y1 + pad + th;
    const rstep = Math.max(1, Math.floor(step / 2));
    for (let y = Math.max(0, ry0); y < Math.min(img.height, ry1); y += rstep) for (let x = Math.max(0, rx0); x < Math.min(img.width, rx1); x += rstep) {
      const inner = x >= x0 - pad && x < x1 + pad && y >= y0 - pad && y < y1 + pad;
      if (inner) continue;
      const i = (y * img.width + x) * 4;
      const p = [img.data[i], img.data[i + 1], img.data[i + 2]];
      const k = (p[0] >> 4) + ',' + (p[1] >> 4) + ',' + (p[2] >> 4);
      const e = ring.get(k) || { n: 0, s: [0, 0, 0] };
      e.n++; e.s[0] += p[0]; e.s[1] += p[1]; e.s[2] += p[2]; ring.set(k, e); rn++;
    }
    // the ring is only a fallback for when the text colour swallows its own background
    if (rn && !majors.length) majors.push(...[...ring.values()].filter((e) => e.n >= rn * 0.3).map((e) => e.s.map((v) => v / e.n)));
    if (!majors.length) continue;
    // element opacity blends the text toward the background
    let worst = Infinity;
    for (const bg of majors) {
      const fg = fg0.map((c, i) => c * t.opacity + bg[i] * (1 - t.opacity));
      worst = Math.min(worst, ratio(fg, bg));
    }
    min = Math.min(min, worst);
    const large = t.fontSize >= 48 || (t.fontSize >= 40 && t.weight >= 600);
    const need = large ? 3 : 4.5;
    if (worst < need) errors.push({ type: 'low-contrast', detail: `${t.sel} contrast ${worst.toFixed(2)}:1 (needs ${need}:1)` });
    else if (worst < need + 1) warnings.push({ type: 'contrast-marginal', detail: `${t.sel} contrast ${worst.toFixed(2)}:1` });
  }
  return { errors, warnings, min: Number.isFinite(min) ? min : null };
}
