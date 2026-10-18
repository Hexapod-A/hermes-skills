#!/usr/bin/env python3
"""Tell a real page from a block page.

    from blockcheck import check
    v = check(status=403, body=html, url=url, headers=resp.headers)
    v.kind    -> "ok" | "blocked" | "captcha" | "login" | "js" | "empty" | "gone" | "error"
    v.reason  -> short plain reason, e.g. "Cloudflare challenge (Just a moment...)"
    v.ok      -> True only for "ok"

CLI (reads a saved file):  blockcheck.py page.html [--status 403] [--url URL]

Pure stdlib, no network. The marker lists come from real block pages seen on 2026-10-18
(Cloudflare, DataDome, PerimeterX/HUMAN, AWS WAF, Akamai, Imperva, Amazon, Reddit, Google).
"""
import argparse
import html as htmllib
import re
import sys
from dataclasses import dataclass

# (vendor label, markers). A page is a challenge when any marker is in the raw HTML.
CHALLENGE_MARKERS = [
    ("Cloudflare challenge", ["<title>Just a moment...</title>", "cf_chl_opt", "challenge-platform/h/",
                              "cf-browser-verification", "Checking your browser before accessing",
                              "Enable JavaScript and cookies to continue"]),
    ("Cloudflare block", ["Attention Required! | Cloudflare", "Sorry, you have been blocked",
                          "cf-error-details", "Cloudflare Ray ID"]),
    ("DataDome", ["captcha-delivery.com", "geo.captcha-delivery", "datadome"]),
    ("PerimeterX / HUMAN", ["px-captcha", "_pxAppId", "perimeterx", "Press &amp; Hold", "Press & Hold"]),
    ("AWS WAF", ["awsWafCookieDomainList", "AwsWafIntegration", "aws-waf-token"]),
    ("Imperva / Incapsula", ["_Incapsula_Resource", "Incapsula incident ID", "Pardon Our Interruption"]),
    ("Akamai", ["Reference&#32;&#35;", "errors.edgesuite.net", "_abck"]),
    ("Sucuri firewall", ["Sucuri WebSite Firewall", "sucuri.net/privacy-policy"]),
    ("Kasada", ["KPSDK", "ips.js?"]),
    ("Amazon captcha", ["/errors/validateCaptcha", "Type the characters you see in this image",
                        "api-services-support@amazon.com"]),
    ("Google unusual traffic", ["Our systems have detected unusual traffic", "/sorry/index"]),
    ("Reddit network block", ["blocked by network security", "whoa there, pardner", "identified as a social crawler", "submit a bug report"]),
    ("Archive rate limit", ["suspected abusive bot traffic"]),
]

# Words that only count when the page has little real text (a small page that says "verify you are human").
SOFT_BLOCK_WORDS = ["are you a robot", "verify you are human", "verify you are a human", "unusual traffic",
                    "access denied", "request blocked", "you have been blocked", "bot detection",
                    "please enable js and disable any ad blocker", "complete the security check",
                    "too many requests", "rate limit", "captcha"]
CAPTCHA_WIDGETS = ["g-recaptcha", "h-captcha", "cf-turnstile", "recaptcha/api.js", "hcaptcha.com/1/api.js",
                   "challenges.cloudflare.com/turnstile"]
LOGIN_URL_PARTS = ["/login", "/signin", "/sign-in", "/accounts/login", "/authwall", "/uas/login", "/i/flow/login",
                   "/checkpoint/", "/auth/"]
LOGIN_WORDS = ["log in to continue", "sign in to continue", "log in to see", "sign in to see", "login to continue",
               "you must be logged in", "please log in", "please sign in", "join to view", "sign in to view",
               "create an account to continue", "log in or sign up", "see more from"]
JS_WORDS = ["you need to enable javascript", "please enable javascript", "enable javascript to run this app",
            "javascript is disabled", "requires javascript", "turn on javascript"]


@dataclass
class Verdict:
    kind: str
    reason: str
    text_chars: int = 0

    @property
    def ok(self):
        return self.kind == "ok"

    def __str__(self):
        return f"{self.kind}: {self.reason}"


def visible_text(body):
    """Rough visible text of an HTML page (scripts, styles and tags removed)."""
    if not body:
        return ""
    s = re.sub(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1>", " ", body)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = htmllib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def title_of(body):
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body or "")
    return htmllib.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


def check(status=200, body="", url="", headers=None, min_chars=100):
    """Classify a fetched page. `body` is text (HTML, markdown or JSON)."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    body = body or ""
    head = body
    low = head.lower()
    text = visible_text(head) if "<" in head[:2000] else head.strip()
    n = len(text)
    title = title_of(head)

    if status in (404, 410):
        return Verdict("gone", f"HTTP {status}: the page is gone; try an archived copy", n)

    for label, markers in CHALLENGE_MARKERS:
        for m in markers:
            if m.lower() in low:
                # a big real page can mention a vendor name in passing; only small pages or bad status count
                if status >= 400 or n < 3000 or m.startswith("<title>"):
                    kind = "captcha" if any(w in low for w in CAPTCHA_WIDGETS) or "captcha" in m.lower() else "blocked"
                    return Verdict(kind, f"{label} (marker: {m!r}, HTTP {status})", n)

    if headers.get("cf-mitigated") == "challenge":
        return Verdict("blocked", f"Cloudflare challenge (cf-mitigated header, HTTP {status})", n)

    if status in (401, 407):
        return Verdict("login", f"HTTP {status}: login required", n)
    if status in (403, 429, 451, 503) or status == 202 and n < min_chars:
        return Verdict("blocked", f"HTTP {status}" + (f" ({title})" if title else ""), n)
    if status >= 400:
        return Verdict("error", f"HTTP {status}", n)

    url_l = (url or "").lower()
    if any(p in url_l for p in LOGIN_URL_PARTS) and n < 5000:
        return Verdict("login", f"redirected to a login page ({url})", n)

    small = n < 1500
    tl = text.lower()
    if small and any(w in tl for w in SOFT_BLOCK_WORDS):
        w = next(w for w in SOFT_BLOCK_WORDS if w in tl)
        kind = "captcha" if "captcha" in tl or any(c in low for c in CAPTCHA_WIDGETS) else "blocked"
        return Verdict(kind, f"block words on a small page: {w!r}", n)
    if small and 'youtube about press copyright contact us creators' in tl and 'video' not in tl[:60]:
        return Verdict('js', 'YouTube page rendered only navigation/footer; use yt-dlp metadata', n)
    if small and any(c in low for c in CAPTCHA_WIDGETS):
        return Verdict("captcha", "captcha widget on a page with little text", n)
    if n < 3000 and any(w in tl for w in LOGIN_WORDS):
        return Verdict("login", "login wall: " + next(w for w in LOGIN_WORDS if w in tl), n)
    if n < min_chars:
        if any(w in tl for w in JS_WORDS) or re.search(r'<div id="(root|app|__next|__nuxt)"[^>]*>\s*</div>', head):
            return Verdict("js", "empty app shell: needs a browser to run its JavaScript", n)
        if not body.strip():
            return Verdict("empty", f"empty body (HTTP {status})", 0)
        return Verdict("empty", f"only {n} characters of text (HTTP {status})", n)
    return Verdict("ok", f"HTTP {status}, {n} characters of text" + (f", title {title[:60]!r}" if title else ""), n)


def main():
    ap = argparse.ArgumentParser(description="Classify a saved page as ok / blocked / captcha / login / js / empty.")
    ap.add_argument("file")
    ap.add_argument("--status", type=int, default=200)
    ap.add_argument("--url", default="")
    a = ap.parse_args()
    body = open(a.file, encoding="utf-8", errors="replace").read()
    v = check(a.status, body, a.url)
    print(v)
    sys.exit(0 if v.ok else 2)


if __name__ == "__main__":
    main()
