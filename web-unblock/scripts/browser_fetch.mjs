#!/usr/bin/env node
// web-unblock browser route: open a page in headless Chromium with normal-browser settings, wait for a
// bot check to clear, then save the HTML, the visible text, image/media URLs and a screenshot.
//
//   node browser_fetch.mjs URL --out DIR [--wait 30] [--mobile] [--storage state.json] [--save-state]
//                              [--no-screenshot] [--full] [--proxy URL] [--solve]
//
// Prints one JSON line (also saved as DIR/browser.json):
//   {ok, kind, reason, status, final_url, title, html, text_file, text_chars, screenshot, images, media, notes}
// and writes DIR/browser.html, DIR/browser.txt, DIR/browser.png.
// Exit 0 = real content, 2 = still blocked / login / empty, 1 = crash.
//
// Uses the repo's `playwright` package (falls back to `playwright-core`). CHROME_PATH picks another Chrome.
// Paid options, only when set: PROXY_URL (or --proxy) = residential proxy, e.g. http://user:pass@host:port.
// --solve with CAPSOLVER_API_KEY or TWOCAPTCHA_API_KEY = send a reCAPTCHA / hCaptcha / Turnstile widget to a
// solving service (costs money per solve). Both are optional; nothing here needs them.
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : dflt; };
const flag = (name) => argv.includes(name);
const url = argv.find((a) => /^https?:\/\//.test(a));
if (!url) { console.error('usage: node browser_fetch.mjs URL --out DIR [--wait 30] [--mobile] [--storage state.json] [--solve]'); process.exit(1); }
const outDir = opt('--out', './unblock-out');
const waitS = Number(opt('--wait', '30'));
const proxyUrl = opt('--proxy', process.env.PROXY_URL || '');
fs.mkdirSync(outDir, { recursive: true });
const notes = [];

// Same ideas as blockcheck.py, checked inside the page.
const CHALLENGE = [
  [/^just a moment/i, 'Cloudflare challenge'], [/attention required! \| cloudflare/i, 'Cloudflare block'],
  [/captcha-delivery\.com/i, 'DataDome'], [/px-captcha|press (&amp;|&) hold/i, 'PerimeterX / HUMAN'],
  [/awsWafCookieDomainList|AwsWafIntegration/, 'AWS WAF'], [/_Incapsula_Resource|Pardon Our Interruption/i, 'Imperva'],
  [/validateCaptcha|Type the characters you see/i, 'Amazon captcha'], [/detected unusual traffic/i, 'Google unusual traffic'],
  [/blocked by network security/i, 'Reddit network block'], [/verify you are (a )?human|are you a robot/i, 'human check'],
  [/challenges\.cloudflare\.com\/turnstile|cf-turnstile/i, 'Turnstile widget'],
];

async function loadPlaywright() {
  for (const name of ['playwright', 'playwright-core']) { try { return await import(name); } catch {} }
  throw new Error('playwright is not installed: run `npm install` in the repo, then `npx playwright install chromium`');
}

async function launch(pw) {
  const base = { headless: true, args: ['--no-sandbox', '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage'] };
  if (proxyUrl) {
    const u = new URL(proxyUrl);
    base.proxy = { server: `${u.protocol}//${u.host}`, username: decodeURIComponent(u.username) || undefined, password: decodeURIComponent(u.password) || undefined };
    notes.push(`via proxy ${u.host}`);
  }
  if (process.env.CHROME_PATH) return pw.chromium.launch({ ...base, executablePath: process.env.CHROME_PATH });
  // Full Chromium in "new headless" mode looks more like a normal browser than the headless shell.
  try { return await pw.chromium.launch({ ...base, channel: 'chromium' }); } catch (e) { notes.push('full chromium not installed, using headless shell'); }
  return pw.chromium.launch(base);
}

const STEALTH = () => {
  Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
  Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  if (!navigator.plugins.length) Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5].map((i) => ({ name: 'PDF Viewer ' + i })) });
  window.chrome = window.chrome || { runtime: {}, app: {}, csi() {}, loadTimes() {} };
  const q = navigator.permissions && navigator.permissions.query;
  if (q) navigator.permissions.query = (p) => (p && p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : q.call(navigator.permissions, p));
  const gp = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function (x) { if (x === 37445) return 'Intel Inc.'; if (x === 37446) return 'Intel Iris OpenGL Engine'; return gp.call(this, x); };
};

async function pageState(page) {
  return page.evaluate(() => ({
    title: document.title || '',
    html: document.documentElement ? document.documentElement.outerHTML.slice(0, 400000) : '',
    textLen: (document.body && document.body.innerText || '').trim().length,
  })).catch(() => ({ title: '', html: '', textLen: 0 }));
}

function challengeOf(st) {
  const hay = st.title + '\n' + (st.textLen < 3000 ? st.html : st.html.slice(0, 20000));
  for (const [re, label] of CHALLENGE) {
    if (re.test(label === 'Cloudflare challenge' ? st.title : hay)) {
      if (label === 'Turnstile widget' && st.textLen > 1500) continue; // a form on a real page
      return label;
    }
  }
  return null;
}

// ---- optional paid captcha solving --------------------------------------------------------------------
async function findWidget(page) {
  return page.evaluate(() => {
    const el = document.querySelector('[data-sitekey]');
    if (el) {
      const c = el.className || '';
      const type = /cf-turnstile/.test(c) ? 'turnstile' : /h-captcha/.test(c) ? 'hcaptcha' : 'recaptcha';
      return { type, sitekey: el.getAttribute('data-sitekey'), callback: el.getAttribute('data-callback') };
    }
    for (const f of document.querySelectorAll('iframe[src]')) {
      const s = f.src;
      let m = s.match(/[?&]k=([\w-]+)/); if (/recaptcha/.test(s) && m) return { type: 'recaptcha', sitekey: m[1] };
      m = s.match(/sitekey=([\w-]+)/); if (/hcaptcha/.test(s) && m) return { type: 'hcaptcha', sitekey: m[1] };
      m = s.match(/\/(0x[\w-]+)\//); if (/challenges\.cloudflare\.com/.test(s) && m) return { type: 'turnstile', sitekey: m[1] };
    }
    return null;
  });
}

async function postJSON(u, body) {
  const r = await fetch(u, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}

export async function solveCaptcha(w, pageUrl) {
  const cap = process.env.CAPSOLVER_API_KEY, two = process.env.TWOCAPTCHA_API_KEY;
  if (!cap && !two) return { error: 'no CAPSOLVER_API_KEY or TWOCAPTCHA_API_KEY set' };
  const api = cap ? 'https://api.capsolver.com' : 'https://api.2captcha.com';
  const types = cap
    ? { recaptcha: 'ReCaptchaV2TaskProxyLess', hcaptcha: 'HCaptchaTaskProxyLess', turnstile: 'AntiTurnstileTaskProxyLess' }
    : { recaptcha: 'RecaptchaV2TaskProxyless', hcaptcha: 'HCaptchaTaskProxyless', turnstile: 'TurnstileTaskProxyless' };
  const clientKey = cap || two;
  const created = await postJSON(api + '/createTask', { clientKey, task: { type: types[w.type], websiteURL: pageUrl, websiteKey: w.sitekey } });
  if (created.errorId) return { error: `${created.errorCode || ''} ${created.errorDescription || ''}`.trim() };
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    const res = await postJSON(api + '/getTaskResult', { clientKey, taskId: created.taskId });
    if (res.errorId) return { error: `${res.errorCode || ''} ${res.errorDescription || ''}`.trim() };
    if (res.status === 'ready') return { token: res.solution.gRecaptchaResponse || res.solution.token, service: cap ? 'capsolver' : '2captcha' };
  }
  return { error: 'solver timed out after 120 s' };
}

async function injectToken(page, w, token) {
  await page.evaluate(({ w, token }) => {
    const names = ['g-recaptcha-response', 'h-captcha-response', 'cf-turnstile-response'];
    for (const n of names) {
      let el = document.querySelector(`[name="${n}"]`) || document.getElementById(n);
      if (!el && n.startsWith(w.type === 'turnstile' ? 'cf' : w.type === 'hcaptcha' ? 'h' : 'g')) {
        el = document.createElement('textarea'); el.name = n; el.style.display = 'none';
        (document.querySelector('form') || document.body).appendChild(el);
      }
      if (el) el.value = token;
    }
    if (w.callback && typeof window[w.callback] === 'function') { window[w.callback](token); return; }
    const f = document.querySelector('[data-sitekey]')?.closest('form') || document.querySelector('form');
    if (f) f.submit();
  }, { w, token });
}

// PerimeterX "Press & Hold": hold the button the way a person would. Free; works sometimes.
async function pressAndHold(page) {
  const el = await page.$('#px-captcha');
  if (!el) return false;
  const b = await el.boundingBox();
  if (!b) return false;
  await page.mouse.move(b.x + b.width / 2 - 7, b.y + b.height / 2 + 3, { steps: 12 });
  await page.mouse.down();
  await page.waitForTimeout(9000 + Math.random() * 3000);
  await page.mouse.up();
  return true;
}

// Cloudflare's "Verify you are human" checkbox: click it once like a person. Free; works sometimes.
async function clickTurnstile(page) {
  for (const f of page.frames()) {
    if (!/challenges\.cloudflare\.com/.test(f.url())) continue;
    try {
      const el = await f.frameElement();
      const b = await el.boundingBox();
      if (!b) continue;
      await page.mouse.move(b.x + 28 + Math.random() * 4, b.y + b.height / 2 + Math.random() * 4, { steps: 15 });
      await page.waitForTimeout(300 + Math.random() * 400);
      await page.mouse.click(b.x + 30, b.y + b.height / 2);
      return true;
    } catch {}
  }
  return false;
}

// ---- main --------------------------------------------------------------------------------------------
async function main() {
  const pw = await loadPlaywright();
  const browser = await launch(pw);
  const ver = browser.version().split('.')[0];
  const mobile = flag('--mobile');
  const ua = mobile
    ? `Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${ver}.0.0.0 Mobile Safari/537.36`
    : `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${ver}.0.0.0 Safari/537.36`;
  const ctxOpts = {
    userAgent: ua, locale: 'en-US', timezoneId: process.env.UNBLOCK_TZ || 'America/New_York',
    viewport: mobile ? { width: 412, height: 915 } : { width: 1366, height: 768 },
    deviceScaleFactor: mobile ? 2.6 : 1, isMobile: mobile, hasTouch: mobile,
    extraHTTPHeaders: { 'Accept-Language': 'en-US,en;q=0.9' },
  };
  const storage = opt('--storage');
  if (storage && fs.existsSync(storage)) { ctxOpts.storageState = storage; notes.push('loaded saved login/cookies'); }
  const ctx = await browser.newContext(ctxOpts);
  await ctx.addInitScript(STEALTH);
  const page = await ctx.newPage();
  const media = new Set();
  page.on('response', (r) => {
    const ct = r.headers()['content-type'] || '';
    const u = r.url();
    if (/\.(ts|m4s|fmp4|aac)(\?|$)/.test(u) || /\/(seg|chunk|frag)[-_]?\d/i.test(u)) return; // stream pieces, not the media
    if (/^(video|audio)\//.test(ct) || /\.(m3u8|mpd)(\?|$)/.test(u)) media.add(u);
  });

  let status = null, kind = 'ok', reason = '';
  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    status = resp ? resp.status() : null;
  } catch (e) { notes.push('navigation: ' + String(e.message).split('\n')[0]); }

  // Wait for a challenge to clear (Cloudflare and AWS WAF often clear on their own in a real browser).
  const t0 = Date.now();
  let held = false, solved = false, clicked = false, label = null;
  while (Date.now() - t0 < waitS * 1000) {
    await page.waitForTimeout(1500);
    const st = await pageState(page);
    label = challengeOf(st);
    if (!label && st.textLen > 0) break;
    if (label === 'PerimeterX / HUMAN' && !held) { held = await pressAndHold(page); notes.push('tried press-and-hold'); continue; }
    if (/Cloudflare|Turnstile/.test(label || '') && !clicked && Date.now() - t0 > 6000) { clicked = await clickTurnstile(page); if (clicked) notes.push('clicked the Cloudflare checkbox'); }
    if (label && flag('--solve') && !solved) {
      const w = await findWidget(page);
      if (w) {
        notes.push(`found ${w.type} widget, sending to solver`);
        const s = await solveCaptcha(w, page.url());
        solved = true;
        if (s.token) { await injectToken(page, w, s.token); notes.push(`solved by ${s.service}`); }
        else notes.push('solver: ' + s.error);
      }
    }
  }
  try { await page.waitForLoadState('networkidle', { timeout: 8000 }); } catch {}

  // Scroll to load lazy images, then back to top.
  try {
    for (let i = 0; i < 8; i++) { await page.mouse.wheel(0, 900); await page.waitForTimeout(250); }
    await page.evaluate(() => window.scrollTo(0, 0));
  } catch {}

  const st = await pageState(page);
  label = challengeOf(st);
  const data = await page.evaluate(() => {
    const abs = (u) => { try { return new URL(u, location.href).href; } catch { return null; } };
    const imgs = [];
    const add = (u, w, alt) => { const a = abs(u); if (a && /^https?:/.test(a)) imgs.push({ url: a, width: w || 0, alt: alt || '' }); };
    for (const m of document.querySelectorAll('meta[property="og:image"],meta[name="twitter:image"],meta[property="og:image:url"]')) add(m.content, 9999, 'og:image');
    for (const im of document.images) {
      let best = im.currentSrc || im.src, bw = im.naturalWidth;
      if (im.srcset) for (const part of im.srcset.split(',')) { const [u, d] = part.trim().split(/\s+/); const w = parseInt(d) || 0; if (w > bw) { bw = w; best = u; } }
      if (bw >= 60 || !im.complete) add(best, bw, im.alt);
    }
    const vids = [...document.querySelectorAll('video[src],video source[src],audio[src],audio source[src]')].map((v) => abs(v.src)).filter(Boolean);
    return { text: (document.body && document.body.innerText || '').trim(), images: imgs, vids, final: location.href, title: document.title };
  }).catch(() => ({ text: '', images: [], vids: [], final: page.url(), title: '' }));

  const seen = new Set();
  const images = data.images.filter((i) => !seen.has(i.url) && seen.add(i.url)).sort((a, b) => b.width - a.width);
  data.vids.forEach((v) => media.add(v));

  if (label) { kind = /captcha|Hold|human|Turnstile|DataDome/.test(label) ? 'captcha' : 'blocked'; reason = `${label} did not clear in ${waitS}s`; }
  else if (/\/(login|signin|accounts\/login|authwall|i\/flow\/login)/i.test(data.final) && data.text.length < 5000) { kind = 'login'; reason = `redirected to a login page (${data.final})`; }
  else if (data.text.length < 100) { kind = 'empty'; reason = `only ${data.text.length} characters of text`; }
  else reason = `${data.text.length} characters of text`;

  const htmlPath = path.join(outDir, 'browser.html');
  fs.writeFileSync(htmlPath, await page.content().catch(() => st.html));
  let shot = null;
  if (!flag('--no-screenshot')) {
    shot = path.join(outDir, 'browser.png');
    await page.screenshot({ path: shot, fullPage: flag('--full') }).catch(() => { shot = null; });
  }
  if (flag('--save-state')) { const statePath = path.join(outDir, 'state.json'); await ctx.storageState({ path: statePath }); fs.chmodSync(statePath, 0o600); notes.push('saved cookies to state.json (keep private)'); }
  await browser.close();

  const textPath = path.join(outDir, 'browser.txt');
  fs.writeFileSync(textPath, data.text);
  const out = { ok: kind === 'ok', kind, reason, status, final_url: data.final, title: data.title, html: htmlPath,
    text_file: textPath, text_chars: data.text.length, screenshot: shot, images: images.slice(0, 200),
    media: [...media].slice(0, 50), notes };
  fs.writeFileSync(path.join(outDir, 'browser.json'), JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out));
  process.exitCode = out.ok ? 0 : 2; // not process.exit(): a big line to a pipe can be cut off
}

main().catch((e) => { console.log(JSON.stringify({ ok: false, kind: 'error', reason: String(e.message || e).split('\n')[0], notes })); process.exitCode = 1; });
