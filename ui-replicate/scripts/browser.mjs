// Shared Chromium launcher: uses `playwright` (repo dependency), falls back to `playwright-core`.
// Set CHROME_PATH to use a system Chrome / headless shell instead of Playwright's download.
export async function launch() {
  let pw;
  try { pw = await import('playwright'); } catch { pw = await import('playwright-core'); }
  const opts = { args: ['--no-sandbox', '--font-render-hinting=none', '--hide-scrollbars'] };
  if (process.env.CHROME_PATH) opts.executablePath = process.env.CHROME_PATH;
  return pw.chromium.launch(opts);
}

export const DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';
export const MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

// Context options for a viewport width: <= 500px is treated as a phone (touch, mobile UA, DPR 3 unless set).
export function contextFor(width, height, { dpr, storage } = {}) {
  const phone = width <= 500;
  const o = {
    viewport: { width, height },
    deviceScaleFactor: dpr ?? 1,
    userAgent: phone ? MOBILE_UA : DESKTOP_UA,
    isMobile: phone,
    hasTouch: phone,
    reducedMotion: 'reduce',
  };
  if (storage) o.storageState = storage;
  return o;
}

// Load a page the way a person sees it: wait for load, scroll through to trigger lazy images and
// in-view animations, wait for web fonts, go back to the top.
export async function settle(page, url, { wait = 600, scroll = true, timeout = 60000 } = {}) {
  await page.goto(url, { waitUntil: 'load', timeout });
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch {}
  if (scroll) {
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    const vh = page.viewportSize().height;
    for (let y = 0; y < h; y += Math.max(300, vh * 0.7)) {
      await page.evaluate((yy) => window.scrollTo(0, yy), y);
      await page.waitForTimeout(150);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
  }
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(wait);
}

// Hide what is not part of the design: modals and overlays (fixed/absolute layers covering > 25% of
// the screen), and fixed things stuck to the bottom (cookie bars, chat bubbles, "made in" badges).
// A fixed header at the top stays. Returns a list of what was hidden so the report can say so.
export async function cleanPage(page) {
  return page.evaluate(() => {
    const vw = innerWidth, vh = innerHeight, hidden = [];
    for (const el of document.querySelectorAll('body *')) {
      const s = getComputedStyle(el);
      if (s.position !== 'fixed' && s.position !== 'sticky' && !(s.position === 'absolute' && Number(s.zIndex) >= 100)) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const cover = (Math.min(r.right, vw) - Math.max(r.left, 0)) * (Math.min(r.bottom, vh) - Math.max(r.top, 0)) / (vw * vh);
      const bottomThing = s.position === 'fixed' && r.top > vh * 0.6 && r.height < 220;
      const overlay = cover > 0.25 && s.position !== 'sticky' && !(r.top <= 0 && r.height < vh * 0.3);
      if (overlay || bottomThing) {
        hidden.push(`${el.tagName.toLowerCase()}.${String(el.className).split(/\s+/).slice(0, 2).join('.')} (${Math.round(cover * 100)}% of screen)`);
        el.style.setProperty('display', 'none', 'important');
      }
    }
    document.documentElement.style.setProperty('overflow', 'auto', 'important');
    document.body.style.setProperty('overflow', 'auto', 'important');
    return hidden;
  });
}
