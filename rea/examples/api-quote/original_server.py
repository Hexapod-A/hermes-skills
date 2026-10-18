#!/usr/bin/env python3
"""THE ORIGINAL (treat as a black box). A small quote API for a Lagos book shop.
In a real job this is the system you study and cannot read. Here it is local so the demo is
offline and safe. Do not read this file while doing the exercise; read only its responses.

  python original_server.py --port 8701
"""
import argparse
import json
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG = {
    "BK-101": ("Physics for WAEC", 250000),
    "BK-205": ("Further Maths Workbook", 199950),
    "PN-002": ("Gel pen (blue)", 15075),
    "NB-010": ("A4 notebook, 80 pages", 89999),
    "TB-300": ("Scientific calculator", 1234567),
}
COUPONS = {"SAVE10": Decimal("0.10"), "BULK": Decimal("0.15")}
VAT = Decimal("0.075")
EXPRESS_FLAT = 1500


def r(x):
    return int(Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def naira(kobo):
    return "\u20a6" + f"{kobo // 100:,}.{kobo % 100:02d}"


def quote(body):
    if not isinstance(body, dict):
        return 422, {"error": {"code": "bad_type", "field": "$"}}
    for f in ("sku", "qty"):
        if f not in body or body[f] is None:
            return 422, {"error": {"code": "missing_field", "field": f}}
    sku, qty = body["sku"], body["qty"]
    if not isinstance(sku, str):
        return 422, {"error": {"code": "bad_type", "field": "sku"}}
    if isinstance(qty, bool) or not isinstance(qty, int):
        return 422, {"error": {"code": "bad_type", "field": "qty"}}
    if qty < 1:
        return 422, {"error": {"code": "out_of_range", "field": "qty", "min": 1}}
    if qty > 500:
        return 422, {"error": {"code": "out_of_range", "field": "qty", "max": 500}}
    if sku not in CATALOG:
        return 404, {"error": {"code": "unknown_sku", "sku": sku}}
    name, unit = CATALOG[sku]
    subtotal = unit * qty
    coupon = body.get("coupon") or ""
    if not isinstance(coupon, str):
        return 422, {"error": {"code": "bad_type", "field": "coupon"}}
    coupon = coupon.strip().upper()
    discount = 0
    if coupon:
        if coupon not in COUPONS:
            return 422, {"error": {"code": "bad_coupon", "coupon": coupon}}
        if coupon == "BULK" and qty < 50:
            return 422, {"error": {"code": "coupon_not_applicable", "coupon": coupon, "min_qty": 50}}
        discount = r(subtotal * COUPONS[coupon])
    after = subtotal - discount
    express = body.get("express", False)
    if not isinstance(express, bool):
        return 422, {"error": {"code": "bad_type", "field": "express"}}
    fee = EXPRESS_FLAT + r(after * Decimal("0.02")) if express else 0
    vat = r((after + fee) * VAT)
    total = after + fee + vat
    return 200, {
        "sku": sku, "name": name, "qty": qty, "unit_kobo": unit, "subtotal_kobo": subtotal,
        "coupon": coupon or None, "discount_kobo": discount, "express_fee_kobo": fee, "vat_kobo": vat,
        "total_kobo": total, "total_display": naira(total), "currency": "NGN",
        "quote_id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
    }


class H(BaseHTTPRequestHandler):
    server_version = "shop/2.3"

    def log_message(self, *a):
        pass

    def send(self, code, obj, extra=None):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Request-Id", uuid.uuid4().hex)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/v1/health":
            return self.send(200, {"ok": True})
        if self.path == "/v1/skus":
            return self.send(200, {"items": [{"sku": k, "name": v[0], "unit_kobo": v[1]} for k, v in sorted(CATALOG.items())]})
        if self.path.split("?")[0] == "/v1/quote":
            return self.send(405, {"error": {"code": "method_not_allowed"}}, {"Allow": "POST"})
        return self.send(404, {"error": {"code": "not_found"}})

    def do_POST(self):
        if self.path.split("?")[0] != "/v1/quote":
            return self.send(404, {"error": {"code": "not_found"}})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self.send(400, {"error": {"code": "bad_json"}})
        code, obj = quote(body)
        return self.send(code, obj)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8701)
    a = ap.parse_args()
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
