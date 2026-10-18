#!/usr/bin/env python3
"""THE REPLICA. Rebuilt only from observed responses of the original (see results/evidence.jsonl).
Written on purpose in a different style: integer maths, a rule table, no Decimal.

  python replica_server.py --port 8702            # faithful rebuild
  REA_BUG=vat_round python replica_server.py ...   # deliberate mismatch for the demo:
                                                   # VAT rounded with float + banker's rounding
"""
import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BUG = os.environ.get("REA_BUG", "")

# E002: GET /v1/skus lists 5 items, prices in kobo (integers)
PRICES = {"BK-101": 250000, "BK-205": 199950, "PN-002": 15075, "NB-010": 89999, "TB-300": 1234567}
NAMES = {"BK-101": "Physics for WAEC", "BK-205": "Further Maths Workbook", "PN-002": "Gel pen (blue)",
         "NB-010": "A4 notebook, 80 pages", "TB-300": "Scientific calculator"}
# H001 (supported): coupons are trimmed + upper-cased; SAVE10 = 10 %, BULK = 15 % from qty 50
COUPON_PCT = {"SAVE10": 10, "BULK": 15}


def half_up(num, den):
    """round(num / den) with .5 going up, for num >= 0, exact integer maths."""
    return (2 * num + den) // (2 * den)


def err(status, **e):
    return status, {"error": e}


def build_quote(b):
    if not isinstance(b, dict):
        return err(422, code="bad_type", field="$")
    for f in ("sku", "qty"):
        if b.get(f) is None:
            return err(422, code="missing_field", field=f)
    sku, qty = b["sku"], b["qty"]
    if not isinstance(sku, str):
        return err(422, code="bad_type", field="sku")
    if type(qty) is not int:
        return err(422, code="bad_type", field="qty")
    if qty < 1:
        return err(422, code="out_of_range", field="qty", min=1)
    if qty > 500:
        return err(422, code="out_of_range", field="qty", max=500)
    if sku not in PRICES:
        return err(404, code="unknown_sku", sku=sku)
    unit = PRICES[sku]
    sub = unit * qty
    raw = b.get("coupon") or ""        # E011: coupon false/0/"" behave like no coupon
    if not isinstance(raw, str):
        return err(422, code="bad_type", field="coupon")
    code = raw.strip().upper()
    disc = 0
    if code:
        if code not in COUPON_PCT:
            return err(422, code="bad_coupon", coupon=code)
        if code == "BULK" and qty < 50:
            return err(422, code="coupon_not_applicable", coupon=code, min_qty=50)
        disc = half_up(sub * COUPON_PCT[code], 100)
    net = sub - disc
    exp = b.get("express", False)
    if type(exp) is not bool:
        return err(422, code="bad_type", field="express")
    fee = 1500 + half_up(net * 2, 100) if exp else 0
    base = net + fee
    if BUG == "vat_round":
        vat = round(base * 0.075)       # the deliberate mismatch
    else:
        vat = half_up(base * 75, 1000)  # H002 (supported): VAT 7.5 % half-up on net + fee
    total = base + vat
    return 200, {
        "sku": sku, "name": NAMES[sku], "qty": qty, "unit_kobo": unit, "subtotal_kobo": sub,
        "coupon": code or None, "discount_kobo": disc, "express_fee_kobo": fee, "vat_kobo": vat,
        "total_kobo": total, "total_display": "\u20a6{:,}.{:02d}".format(total // 100, total % 100),
        "currency": "NGN", "quote_id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
    }


class Replica(BaseHTTPRequestHandler):
    server_version = "shop/2.3"

    def log_message(self, *a):
        pass

    def reply(self, status, obj, headers=()):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Request-Id", uuid.uuid4().hex)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = self.path.split("?")[0]
        if self.path == "/v1/health":
            self.reply(200, {"ok": True})
        elif self.path == "/v1/skus":
            self.reply(200, {"items": [{"sku": s, "name": NAMES[s], "unit_kobo": PRICES[s]} for s in sorted(PRICES)]})
        elif route == "/v1/quote":
            self.reply(405, {"error": {"code": "method_not_allowed"}}, [("Allow", "POST")])
        else:
            self.reply(404, {"error": {"code": "not_found"}})

    def do_POST(self):
        if self.path.split("?")[0] != "/v1/quote":
            return self.reply(404, {"error": {"code": "not_found"}})
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {"error": {"code": "bad_json"}})
        self.reply(*build_quote(parsed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8702)
    ThreadingHTTPServer(("127.0.0.1", ap.parse_args().port), Replica).serve_forever()
