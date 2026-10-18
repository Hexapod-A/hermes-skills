#!/usr/bin/env python3
"""Download a design reference at full resolution.

Works with:
  - Dribbble shot pages   https://dribbble.com/shots/<id>-<slug>
  - Behance project pages https://www.behance.net/gallery/<id>/<slug>
  - any page with og:image / twitter:image (Webflow showcase, portfolios, blog posts)
  - a direct image URL (png/jpg/webp/gif) or video (mp4)

Usage:
  fetch_ref.py URL --out refs/ [--all] [--video] [--name dash]

Dribbble and Behance resize their CDN images with query strings (?resize=752x...). The script strips
those to get the original upload. Dribbble pages sit behind a bot wall (HTTP 202, empty body); the
script then reads the page through the public r.jina.ai reader. If both fail, open the page in a real
browser and copy the image URL by hand.

Only the shot's own media are kept; "more by this designer" thumbnails (400x300, {width}x{height}
templates) are skipped. --all keeps every upload found; --video also saves mp4s (motion shots).
Prints one line per saved file with its pixel size. Reference images are for study only: do not ship
another designer's artwork or photos in the product.
"""
import argparse
import os
import re
import sys
import urllib.parse

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def get(url, **kw):
    kw.setdefault("timeout", 45)
    return requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en"}, **kw)


def page_text(url):
    """Page HTML, or the r.jina.ai reader's markdown when the site walls bots."""
    try:
        r = get(url)
        if r.status_code == 200 and len(r.text) > 2000 and "awsWafCookieDomainList" not in r.text:
            return r.text, "direct"
    except requests.RequestException:
        pass
    r = get("https://r.jina.ai/" + url, timeout=60)
    if r.status_code == 200 and len(r.text) > 500:
        return r.text, "r.jina.ai"
    raise SystemExit(f"could not read {url} (direct and reader both failed: HTTP {r.status_code})")


def dribbble_media(text, keep_all=False, video=False):
    found = re.findall(r"https?://cdn\.dribbble\.com/userupload/[^\s\"')<>\]]+", text)
    found += ["https://" + u for u in re.findall(r"(?<![/\w])cdn\.dribbble\.com/userupload/[^\s\"')<>\]]+", text)]
    out, seen = [], set()
    for u in found:
        base, _, query = u.partition("?")
        if base in seen:
            continue
        q = urllib.parse.unquote(query)
        is_video = base.lower().endswith((".mp4", ".webm", ".mov"))
        if is_video and not video:
            continue
        if not keep_all and not is_video:
            m = re.search(r"resize=(\d+)x", q)
            if "{width}" in q or (m and int(m.group(1)) < 700):
                continue  # thumbnails of other shots
        seen.add(base)
        out.append(base)
    return out


def behance_media(text, keep_all=False):
    found = re.findall(r"https?://mir-s3-cdn-cf\.behance\.net/project_modules/[^\s\"')<>]+", text)
    out, seen = [], set()
    for u in found:
        m = re.match(r"(https?://mir-s3-cdn-cf\.behance\.net/project_modules/)([^/]+)/(.+)", u.split("?")[0])
        if not m:
            continue
        key = m.group(3)
        if key in seen:
            continue
        seen.add(key)
        # largest first; the first one that answers 200 wins
        out.append([m.group(1) + size + "/" + key for size in ("source", "fs", "max_3840", "2800_opt_1", "1400", "max_1200")])
    return out


def og_images(text):
    pats = [r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)']
    urls = []
    for p in pats:
        urls += re.findall(p, text, re.I)
    return list(dict.fromkeys(urls))


def save(url, out_dir, name):
    r = get(url, stream=True, timeout=120)
    if r.status_code != 200:
        return None
    ctype = r.headers.get("content-type", "")
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() or (
        ".png" if "png" in ctype else ".jpg" if "jpeg" in ctype else ".webp" if "webp" in ctype else ".bin")
    path = os.path.join(out_dir, name + ext)
    with open(path, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    return path


def describe(path):
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            return f"{im.size[0]}x{im.size[1]}"
    except Exception:
        return f"{os.path.getsize(path) // 1024} KB"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", help="file name stem (default: from the URL)")
    ap.add_argument("--all", action="store_true", help="keep every upload found on the page")
    ap.add_argument("--video", action="store_true", help="also save mp4/webm (motion shots)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stem = a.name or (re.search(r"/(\d+)", a.url) or re.search(r"([\w-]+)/?$", a.url)).group(1)

    path_l = urllib.parse.urlparse(a.url).path.lower()
    if path_l.endswith(IMG_EXT + (".mp4",)):
        p = save(a.url.split("?")[0] if "dribbble" in a.url or "behance" in a.url else a.url, a.out, stem)
        print(p, describe(p)) if p else sys.exit("download failed")
        return

    text, via = page_text(a.url)
    print(f"read page via {via}")
    saved = []
    if "dribbble.com" in a.url:
        for i, u in enumerate(dribbble_media(text, a.all, a.video), 1):
            p = save(u, a.out, f"{stem}-{i}")
            if p:
                saved.append(p)
    elif "behance.net" in a.url:
        for i, cands in enumerate(behance_media(text, a.all), 1):
            for u in cands:
                p = save(u, a.out, f"{stem}-{i}")
                if p:
                    saved.append(p)
                    break
    if not saved:
        for i, u in enumerate(og_images(text), 1):
            p = save(urllib.parse.urljoin(a.url, u), a.out, f"{stem}-og{i}")
            if p:
                saved.append(p)
    if not saved:
        sys.exit("no images found; open the page in a browser and take the image URL by hand, "
                 "or screenshot the live site with screenshot.mjs")
    for p in saved:
        print(p, describe(p))


if __name__ == "__main__":
    main()
