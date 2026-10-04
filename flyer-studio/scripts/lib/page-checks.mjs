// Functions that run INSIDE the page (passed to page.evaluate). Keep them self-contained.

// Auto-fit: shrink [data-fit] text until it respects data-max-lines and the frame has room.
export function pageFit() {
  const lineCount = (el) => {
    const r = document.createRange(); r.selectNodeContents(el);
    const tops = [];
    for (const x of r.getClientRects()) {
      if (x.width < 1) continue;
      if (!tops.some((t) => Math.abs(t - x.top) < x.height * 0.5)) tops.push(x.top);
    }
    return tops.length;
  };
  const els = [...document.querySelectorAll('[data-fit]')];
  const size = (el) => parseFloat(getComputedStyle(el).fontSize);
  const wide = (el) => getComputedStyle(el).display !== 'inline' && el.scrollWidth > el.clientWidth + 1;
  for (const el of els) {
    const max = +el.dataset.maxLines || 99, min = +el.dataset.min || 20;
    let s = size(el), guard = 0;
    while ((lineCount(el) > max || wide(el)) && s > min && guard++ < 200) { s = Math.max(min, s - Math.max(1, s * 0.03)); el.style.fontSize = s + 'px'; }
  }
  // Global vertical fit: if any stack/frame overflows, shrink all fit-able text a step at a time.
  const overflowing = () => [...document.querySelectorAll('.stack, .frame')].some((b) => b.scrollHeight > b.clientHeight + 1);
  let guard = 0;
  while (overflowing() && guard++ < 60) {
    let changed = false;
    for (const el of els) {
      const min = +el.dataset.min || 20, s = size(el);
      if (s > min) { el.style.fontSize = Math.max(min, s * 0.96) + 'px'; changed = true; }
    }
    if (!changed) break;
  }
  return true;
}

// Layout checks. Returns {errors, warnings, texts:[{sel,rect,color,fontSize,weight,opacity}]}
export function pageChecks({ families, story }) {
  const errors = [], warnings = [];
  const canvas = document.querySelector('.canvas') || document.body;
  const C = canvas.getBoundingClientRect();
  const W = C.width, H = C.height;
  const name = (el) => {
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\s+/).join('.') : '';
    const t = (el.textContent || '').trim().replace(/\s+/g, ' ');
    return `${el.tagName.toLowerCase()}${cls} "${t.slice(0, 40)}${t.length > 40 ? '…' : ''}"`;
  };
  // Visible text box from the element's OWN text nodes (children are checked separately), with each
  // line clamped to the line-height so tall font ascent/descent boxes don't count as collisions.
  const textRect = (el) => {
    const lh = parseFloat(getComputedStyle(el).lineHeight) || parseFloat(getComputedStyle(el).fontSize) * 1.2;
    const rs = [];
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const x of r.getClientRects()) {
        if (x.width <= 0.5 || x.height <= 0.5) continue;
        const h = Math.min(x.height, lh), cy = x.top + x.height / 2;
        rs.push({ left: x.left, right: x.right, top: cy - h / 2, bottom: cy + h / 2, width: x.width, height: h });
      }
    }
    if (!rs.length) return null;
    const x1 = Math.min(...rs.map((x) => x.left)), y1 = Math.min(...rs.map((x) => x.top));
    const x2 = Math.max(...rs.map((x) => x.right)), y2 = Math.max(...rs.map((x) => x.bottom));
    return { x: x1 - C.left, y: y1 - C.top, w: x2 - x1, h: y2 - y1, lines: rs };
  };
  const lines = (rs) => { const tops = []; for (const x of rs) if (!tops.some((t) => Math.abs(t - x.top) < x.height * 0.5)) tops.push(x.top); return tops.length; };
  const inter = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  const overlaps = (a, b) => (Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) > 3 && (Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)) > 3;
  const effOpacity = (el) => { let o = 1; for (let e = el; e && e !== document.documentElement; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };

  // 2. collect text elements: anything with its own visible text
  const all = [...canvas.querySelectorAll('*')].filter((el) => {
    if (['SCRIPT', 'STYLE', 'svg', 'SVG'].includes(el.tagName)) return false;
    if (el.closest('svg')) return false;
    return [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  });
  // 1. fonts actually loaded for every family the text uses (no silent fallback to a system font)
  const used = new Set(all.map((el) => getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim()));
  for (const f of families) {
    if (!used.has(f)) continue;
    const loaded = [...document.fonts].some((ff) => ff.family.replace(/"/g, '') === f && ff.status === 'loaded');
    if (!loaded) errors.push({ type: 'font-not-loaded', detail: `"${f}" did not load; text is rendering in a fallback font. Check the font file path in brand.json.` });
  }
  const texts = [];
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const rect = textRect(el); if (!rect) continue;
    const fs = parseFloat(cs.fontSize);
    const t = { el, sel: name(el), rect, color: cs.color, fontSize: fs, weight: parseInt(cs.fontWeight, 10) || 400, opacity: effOpacity(el), bleed: !!el.closest('[data-bleed]') };
    texts.push(t);

    // overflow inside its own box
    if (cs.display !== 'inline' && (el.scrollWidth > el.clientWidth + 2)) errors.push({ type: 'overflow-x', detail: `${t.sel} is wider than its box by ${el.scrollWidth - el.clientWidth}px` });
    if (cs.overflow !== 'visible' && el.scrollHeight > el.clientHeight + 2) errors.push({ type: 'overflow-y', detail: `${t.sel} is clipped vertically` });
    // off-canvas / too close to the edge
    const m = 24;
    if (!t.bleed && (rect.x < m || rect.y < m || rect.x + rect.w > W - m || rect.y + rect.h > H - m))
      errors.push({ type: 'out-of-bounds', detail: `${t.sel} runs past the safe margin (x=${rect.x.toFixed(0)}, y=${rect.y.toFixed(0)}, w=${rect.w.toFixed(0)}, h=${rect.h.toFixed(0)})` });
    // story safe zones (platform UI covers ~200px top / ~250px bottom)
    if (story && !t.bleed && (rect.y < 200 || rect.y + rect.h > H - 250))
      warnings.push({ type: 'story-safe-zone', detail: `${t.sel} sits under the story UI area` });
    // readable size on a phone
    if (fs < 22) errors.push({ type: 'text-too-small', detail: `${t.sel} is ${fs.toFixed(0)}px on a 1080px canvas (min 22)` });
    else if (fs < 26) warnings.push({ type: 'text-small', detail: `${t.sel} is ${fs.toFixed(0)}px; fine for footnotes only` });
    // widows on multi-line copy
    if (el.hasAttribute('data-fit')) {
      const full = document.createRange(); full.selectNodeContents(el);
      const allLines = [...full.getClientRects()].filter((x) => x.width > 0.5);
      const n = lines(allLines);
      const maxL = +el.dataset.maxLines || 99;
      if (n > maxL) errors.push({ type: 'too-many-lines', detail: `${t.sel} wraps to ${n} lines (max ${maxL}) even at its minimum size. Shorten the copy.` });
      const min = +el.dataset.min || 0;
      if (min && fs <= min + 0.5) warnings.push({ type: 'shrunk-to-min', detail: `${t.sel} had to shrink to its minimum size (${min}px). Consider shorter copy.` });
      if (n > 1) {
        const lastTop = Math.max(...allLines.map((x) => x.top));
        const lastW = allLines.filter((x) => Math.abs(x.top - lastTop) < 2).reduce((s, x) => s + x.width, 0);
        if (lastW < rect.w * 0.18) warnings.push({ type: 'widow', detail: `${t.sel} ends with a very short last line; rebalance with \\n or shorter copy` });
      }
    }
  }
  // 3. frame/stack overflow
  for (const b of document.querySelectorAll('.stack, .frame')) {
    if (b.scrollHeight > b.clientHeight + 2) errors.push({ type: 'content-too-tall', detail: `${b.className} content is ${b.scrollHeight - b.clientHeight}px taller than its area. Cut copy or use a taller size.` });
  }
  // 4. collisions: text vs text, text vs decor
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i], b = texts[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    if (overlaps(a.rect, b.rect)) errors.push({ type: 'text-overlap', detail: `${a.sel} overlaps ${b.sel}` });
  }
  const decor = [...canvas.querySelectorAll('[data-decor] *, svg[data-decor], [data-decor] svg, .burst')]
    .map((d) => { const r = d.getBoundingClientRect(); return { d, rect: { x: r.left - C.left, y: r.top - C.top, w: r.width, h: r.height } }; })
    .filter((x) => x.rect.w > 0 && x.rect.h > 0);
  for (const t of texts) {
    if (t.el.hasAttribute('data-allow-overlap')) continue;
    for (const d of decor) {
      if (d.d.classList.contains('burst') && t.el.classList.contains('pill')) continue; // intended: burst tucks over the pill's left end
      if (overlaps(t.rect, d.rect)) { errors.push({ type: 'decor-overlap', detail: `${t.sel} collides with a decor shape` }); break; }
    }
  }
  // 5. images that failed to load
  for (const img of canvas.querySelectorAll('img')) if (!img.complete || img.naturalWidth === 0) errors.push({ type: 'image-missing', detail: `image failed to load: ${img.getAttribute('src')}` });

  return { errors, warnings, texts: texts.map(({ el, ...t }) => ({ ...t, rect: { x: t.rect.x, y: t.rect.y, w: t.rect.w, h: t.rect.h } })) };
}
