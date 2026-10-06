#!/usr/bin/env python3
"""Offline tests for the paid adapters' request building + response parsing (mocked responses, no network, no keys)
and for the free-path logic (owner guard, email typing, scoring, dedupe, suppression, local facts, drafts).

Run: python3 maps-lead-gen/tests/test_adapters.py      (stdlib unittest; ~1 s)
The mocked shapes follow each vendor's public docs as read on 2026-10-06. Live calls are NOT tested here.
"""
import json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import pull, email_waterfall as ew, find_owner as fo, score, local_facts as lf, draft_emails as de
from common import email_type, domain_of, norm_phone


class Resp:
    def __init__(self, j, status=200): self._j, self.status_code, self.ok, self.text = j, status, status < 400, json.dumps(j)
    def json(self): return self._j
    def raise_for_status(self):
        if self.status_code >= 400: raise Exception(f"HTTP {self.status_code}")


class TestPull(unittest.TestCase):
    def test_google_places_request_and_parse(self):
        req = pull.google_places_request("dentist in 78704", None, "K")
        self.assertEqual(req["url"], "https://places.googleapis.com/v1/places:searchText")
        self.assertEqual(req["headers"]["X-Goog-Api-Key"], "K")
        self.assertIn("places.userRatingCount", req["headers"]["X-Goog-FieldMask"])
        self.assertEqual(req["json"]["textQuery"], "dentist in 78704")
        j = {"places": [{"id": "ChIJ1", "displayName": {"text": "Bright Dental"}, "formattedAddress": "100 S Lamar Blvd, Austin, TX 78704, USA",
                         "nationalPhoneNumber": "(512) 555-0101", "websiteUri": "https://bright.example", "rating": 4.7, "userRatingCount": 212,
                         "primaryTypeDisplayName": {"text": "Dentist"}, "location": {"latitude": 30.25, "longitude": -97.76},
                         "googleMapsUri": "https://maps.google.com/?cid=1", "businessStatus": "OPERATIONAL",
                         "reviews": [{"publishTime": "2026-09-20T10:00:00Z", "rating": 2, "text": {"text": "Left two voicemails and never got a call back."}}]},
                        {"id": "ChIJ2", "displayName": {"text": "Closed Dental"}, "businessStatus": "CLOSED_PERMANENTLY"}],
             "nextPageToken": "abc"}
        rows, tok = pull.parse_google_places(j, "dentist", "78704")
        self.assertEqual(tok, "abc"); self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["business_name"], r["city"], r["state"], r["postcode"]), ("Bright Dental", "Austin", "TX", "78704"))
        self.assertEqual((r["rating"], r["review_count"]), (4.7, 212))
        self.assertEqual(json.loads(r["reviews_json"])[0]["date"], "2026-09-20")

    def test_serper_request_and_parse(self):
        req = pull.serper_places_request("roofer", "33101", 2, "K")
        self.assertEqual(req["url"], "https://google.serper.dev/places"); self.assertEqual(req["headers"]["X-API-KEY"], "K")
        self.assertEqual(req["json"], {"q": "roofer 33101", "gl": "us", "hl": "en", "page": 2})
        j = {"places": [{"title": "Top Roofing", "address": "1 Main St, Miami, FL 33101", "latitude": 25.7, "longitude": -80.2, "rating": 4.9,
                         "ratingCount": 88, "category": "Roofing contractor", "phoneNumber": "+1 305-555-0199", "website": "https://top.example", "cid": "123"}]}
        r = pull.parse_serper_places(j, "roofer", "33101")[0]
        self.assertEqual((r["review_count"], r["postcode"], r["phone"]), (88, "33101", "(305) 555-0199"))
        self.assertEqual(r["maps_url"], "https://maps.google.com/?cid=123")
        revs = pull.parse_serper_reviews({"reviews": [{"isoDate": "2026-09-01T00:00:00Z", "rating": 1, "snippet": "No one answered"}]})
        self.assertEqual(revs[0]["date"], "2026-09-01")

    def test_rapidapi_request_and_parse(self):
        req = pull.rapidapi_request("med spa", "85251", "K", "local-business-data.p.rapidapi.com")
        self.assertEqual(req["url"], "https://local-business-data.p.rapidapi.com/search")
        self.assertEqual(req["headers"]["X-RapidAPI-Key"], "K"); self.assertEqual(req["params"]["query"], "med spa in 85251")
        j = {"data": [{"business_id": "0x1", "name": "Glow Med Spa", "phone_number": "+14805550123", "full_address": "7000 E Camelback Rd, Scottsdale, AZ 85251",
                       "website": "https://glow.example", "rating": 4.6, "review_count": 340, "type": "Medical spa", "latitude": 33.5, "longitude": -111.9}]}
        r = pull.parse_rapidapi(j, "med spa", "85251")[0]
        self.assertEqual((r["business_name"], r["review_count"], r["city"], r["phone"]), ("Glow Med Spa", 340, "Scottsdale", "(480) 555-0123"))

    def test_mapsdata_body_and_row(self):
        b = pull.mapsdata_job_body("Dentist", cities=[("Austin", "TX")], limit=2000, min_reviews=20, max_reviews=400)
        self.assertEqual(b["cities"], [{"city": "Austin", "state": "Texas"}])   # MapsData wants full state names
        self.assertEqual((b["total_limit"], b["min_reviews"], b["max_reviews"], b["country"]), (2000, 20, 400, "us"))
        b2 = pull.mapsdata_job_body("Roofer", states=["FL", "Georgia"])
        self.assertEqual(b2["states"], ["Florida", "Georgia"]); self.assertNotIn("cities", b2)
        r = pull.mapsdata_map_row({"name": "Bright Smile Dental", "email": "hello@brightsmile.example", "phone": "(415) 555-0182",
                                   "website": "https://brightsmile.example", "address": "1 Market St, San Francisco, CA 94105", "rating": "4.8", "category": "Dentist"})
        self.assertEqual((r["email"], r["city"], r["postcode"], r["source"]), ("hello@brightsmile.example", "San Francisco", "94105", "mapsdata"))

    def test_review_filter(self):
        rows = [{"review_count": 3}, {"review_count": 50}, {"review_count": 2000}, {"review_count": ""}]
        self.assertEqual(len(pull.review_filter(rows, 10, 500)), 2)             # 50 + unknown kept
        self.assertEqual(len(pull.review_filter(rows, 10, 500, drop_unknown=True)), 1)

    def test_split_address(self):
        self.assertEqual(pull.split_address("12 Oak Ave Ste 4, Round Rock, TX 78664, USA")["city"], "Round Rock")


class TestWaterfall(unittest.TestCase):
    def test_millionverifier(self):
        req = ew.millionverifier_request("a@b.com", "K")
        self.assertEqual(req["url"], "https://api.millionverifier.com/api/v3/"); self.assertEqual(req["params"]["api"], "K")
        self.assertEqual(ew.parse_millionverifier({"result": "ok"}), "valid")
        self.assertEqual(ew.parse_millionverifier({"result": "catch_all"}), "catch_all")
        self.assertEqual(ew.parse_millionverifier({"result": "disposable"}), "invalid")
        self.assertEqual(ew.parse_millionverifier({"result": "ok", "error": "insufficient credits"}), "unknown")

    def test_bounceban(self):
        req = ew.bounceban_request("a@b.com", "K")
        self.assertEqual(req["headers"], {"Authorization": "K"})   # bare key, no Bearer
        self.assertEqual(ew.parse_bounceban({"result": "deliverable"}), "valid")
        self.assertEqual(ew.parse_bounceban({"result": "undeliverable"}), "invalid")

    def test_prospeo(self):
        req = ew.prospeo_request("Kevin", "Chang", "daybreak.example", "Daybreak Dental", "K")
        self.assertEqual(req["url"], "https://api.prospeo.io/enrich-person"); self.assertEqual(req["headers"]["X-KEY"], "K")
        self.assertEqual(req["json"]["data"]["company_website"], "daybreak.example"); self.assertTrue(req["json"]["only_verified_email"])
        self.assertEqual(ew.parse_prospeo({"error": False, "person": {"email": {"status": "VERIFIED", "revealed": True, "email": "kevin@daybreak.example"}}}), "kevin@daybreak.example")
        self.assertIsNone(ew.parse_prospeo({"error": True, "error_code": "NO_MATCH"}))
        self.assertIsNone(ew.parse_prospeo({"error": False, "person": {"email": {"revealed": False, "email": "k****@x.com"}}}))

    def test_icypeas(self):
        req = ew.icypeas_request("Kevin", "Chang", "daybreak.example", "K")
        self.assertEqual(req["url"], "https://app.icypeas.com/api/email-search"); self.assertEqual(req["headers"]["Authorization"], "K")
        self.assertEqual(req["json"], {"firstname": "Kevin", "lastname": "Chang", "domainOrCompany": "daybreak.example"})
        self.assertEqual(ew.parse_icypeas_read({"items": [{"status": "IN_PROGRESS"}]}), ("pending", None))
        done = {"items": [{"status": "DEBITED", "results": {"emails": [{"email": "kevin@daybreak.example", "certainty": "ultra_sure"}]}}]}
        self.assertEqual(ew.parse_icypeas_read(done), ("done", "kevin@daybreak.example"))
        self.assertEqual(ew.parse_icypeas_read({"items": [{"status": "NOT_FOUND", "results": {"emails": []}}]}), ("done", None))

    def test_waterfall_order_and_logging(self):
        row = {"business_name": "Daybreak Dental", "website": "https://daybreak.example", "owner_first": "Kevin", "owner_last": "Chang",
               "named_emails": "", "general_emails": "info@daybreak.example", "email": ""}
        env = {"PROSPEO_API_KEY": "P", "MILLIONVERIFIER_API_KEY": "M"}
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(url)
            return Resp({"error": False, "person": {"email": {"revealed": True, "email": "kevin@daybreak.example"}}})

        def fake_get(url, params=None, headers=None, timeout=None):
            return Resp({"result": "ok"})
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(ew, "mx_ok", return_value=True), \
                mock.patch.object(ew.requests, "post", fake_post), mock.patch.object(ew.requests, "get", fake_get):
            os.environ.pop("ICYPEAS_API_KEY", None); os.environ.pop("BOUNCEBAN_API_KEY", None)
            out = ew.run_row(row, ["site", "prospeo", "icypeas"])
        # general inbox held as fallback, Prospeo found the owner's named email -> stop there
        self.assertEqual((out["email"], out["email_source"], out["email_status"], out["email_type"]), ("kevin@daybreak.example", "prospeo", "valid", "named"))
        self.assertIn("held as fallback", out["email_trace"]); self.assertEqual(calls, ["https://api.prospeo.io/enrich-person"])

    def test_waterfall_free_only_keeps_general(self):
        row = {"business_name": "Daybreak Dental", "website": "https://daybreak.example", "owner_first": "Kevin", "owner_last": "Chang",
               "named_emails": "", "general_emails": "info@daybreak.example"}
        with mock.patch.object(ew, "mx_ok", return_value=True), mock.patch.dict(os.environ, {}, clear=False):
            for k in ("PROSPEO_API_KEY", "ICYPEAS_API_KEY", "MILLIONVERIFIER_API_KEY", "BOUNCEBAN_API_KEY"): os.environ.pop(k, None)
            out = ew.run_row(row, ["site", "prospeo", "icypeas"])
        self.assertEqual((out["email"], out["email_type"], out["email_status"]), ("info@daybreak.example", "general", "mx_only"))

    def test_catch_all_goes_to_second_check(self):
        with mock.patch.dict(os.environ, {"MILLIONVERIFIER_API_KEY": "M", "BOUNCEBAN_API_KEY": "B"}), mock.patch.object(ew, "mx_ok", return_value=True), \
                mock.patch.object(ew.requests, "get", side_effect=[Resp({"result": "catch_all"}), Resp({"result": "deliverable"})]):
            st, ca = ew.verify("dr@clinic.example", [])
        self.assertEqual((st, ca), ("valid", True))
        with mock.patch.dict(os.environ, {"MILLIONVERIFIER_API_KEY": "M"}), mock.patch.object(ew, "mx_ok", return_value=True), \
                mock.patch.object(ew.requests, "get", return_value=Resp({"result": "catch_all"})):
            os.environ.pop("BOUNCEBAN_API_KEY", None)
            self.assertEqual(ew.verify("dr@clinic.example", []), ("risky", True))


class TestOwner(unittest.TestCase):
    PAGES = [("https://x.example/about", "about", "Meet our team. Dr. Kevin Chang, DDS, founded Daybreak Dental in 2009. Maria Lopez is our office manager."),
             ("footer", "footer", "© 2026 Daybreak Dental. 1 Main St, Austin TX")]

    def test_guard_accepts_name_next_to_title(self):
        self.assertEqual(fo.guard("Kevin", "Chang", self.PAGES), "https://x.example/about")

    def test_guard_rejects_name_without_title_or_absent(self):
        self.assertIsNone(fo.guard("Maria", "Lopez", [("u", "about", "Maria Lopez answers the phones and books visits.")]))
        self.assertIsNone(fo.guard("John", "Smith", self.PAGES))   # invented name -> rejected

    def test_regex_layer(self):
        hit = fo.regex_find(self.PAGES)
        self.assertEqual((hit["first_name"], hit["last_name"]), ("Kevin", "Chang"))
        self.assertIsNone(fo.regex_find([("u", "home", "Family dentistry in Austin. Call us today to book.")]))

    def test_llm_answer_parsing(self):
        self.assertEqual(fo.parse_answer('{"status":"not found"}'), {"status": "not found"})
        self.assertEqual(fo.parse_answer("garbage"), {"status": "not found"})
        a = fo.parse_answer('Sure: {"status":"found","first_name":"Kevin","last_name":"Chang","title":"DDS","quote":"Dr. Kevin Chang, DDS","page":"u"}')
        self.assertEqual(a["last_name"], "Chang")

    def test_prompt_order(self):
        llm = fo.LLM()
        self.assertTrue(llm.instructions.startswith("You read text copied from a local business"))
        v = llm.build("Daybreak Dental", "https://x.example", self.PAGES)
        self.assertTrue(v.startswith("Business: Daybreak Dental"))   # variables go in the user turn, after the fixed instructions

    def test_llm_hallucination_is_rejected(self):
        row = {"business_name": "Daybreak Dental", "website": "https://x.example"}
        llm = fo.LLM(); llm.kind = "openai"; llm.model = "test"
        with mock.patch.object(fo, "pages_of", return_value=self.PAGES), \
                mock.patch.object(llm, "ask", return_value={"status": "found", "first_name": "Robert", "last_name": "Chang", "title": "Owner"}):
            out = fo.find(row, llm, True)
        self.assertEqual(out["owner_first"], "not found"); self.assertIn("rejected_by_guard", out["owner_method"])


class TestScoringAndDrafts(unittest.TestCase):
    def test_email_type(self):
        self.assertEqual(email_type("info@x.com"), "general"); self.assertEqual(email_type("kevin.chang@x.com"), "named")
        self.assertEqual(email_type("downtown@austincosmetic.com"), "general")
        self.assertEqual(email_type("daybreakdental@gmail.com", "Daybreak Dental"), "general")

    def test_score_signals(self):
        import datetime as dt
        row = {"reviews_json": json.dumps([{"date": "2026-09-30", "text": "Left 3 voicemails, nobody called back"}, {"date": "2026-09-01", "text": "great"},
                                           {"date": "2026-08-20", "text": "ok"}, {"date": "2025-01-01", "text": "old"}]),
               "hiring_signal": "True", "hiring_evidence": "careers page: front desk receptionist opening", "site_status": "200",
               "has_chat_widget": "False", "has_online_booking": "True", "phone": "(512) 555-0101", "email_status": "valid", "email_type": "general",
               "owner_first": "Kevin"}
        pts, why = score.score_row(row, dt.date(2026, 10, 6))
        self.assertEqual(pts, 15 + 20 + 15 + 10 + 5 + 5 + 5)
        self.assertTrue(any("slow-response" in w for w in why))

    def test_dedupe_and_suppression(self):
        a = {"business_name": "Daybreak Dental, PLLC", "city": "Austin", "email": "info@daybreak.example"}
        b = {"business_name": "Daybreak Dental", "city": "austin", "website": "https://www.daybreak.example/"}
        self.assertEqual(score.dedupe_key(a), score.dedupe_key(b))
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("email,domain,phone,business_name,city\ninfo@daybreak.example,,,,\n,,,Gordon Dental,Austin\n")
        s = score.load_suppression([f.name])
        self.assertEqual(score.suppressed(a, s), "email")
        self.assertEqual(score.suppressed({"business_name": "Gordon Dental", "city": "Austin"}, s), "name+city")
        self.assertFalse(score.suppressed({"business_name": "New Dental", "city": "Austin"}, s))

    def test_local_fact_rules(self):
        me = {"business_name": "A Dental", "lat": "30.25", "lon": "-97.75", "review_count": "40", "rating": "4.6", "source": "google_places"}
        big = {"business_name": "B Dental", "lat": "30.255", "lon": "-97.75", "review_count": "400", "source": "google_places", "maps_url": "u"}
        out = lf.facts_for(me, [me, big], 2, "dental offices")
        self.assertEqual(out["fact_kind"], "competitor_reviews"); self.assertIn("400 Google reviews", out["local_fact"])
        low = dict(me, rating="3.6", review_count="900")
        out2 = lf.facts_for(low, [low], 2, "dental offices")
        self.assertEqual(out2["fact_kind"], "")            # 3.6 stars is never used as a fact
        self.assertEqual(lf.facts_for(dict(me, rating="4.6"), [me], 2, "x")["fact_kind"], "own_rating")

    def test_draft_is_three_sentences_and_never_guesses(self):
        r = {"business_name": "Daybreak Dental - South", "category": "dentist", "email": "kari@daybreak.example", "email_type": "named",
             "email_status": "valid", "owner_first": "Kevin", "owner_last": "Chang", "owner_title": "DDS", "fact_kind": "density",
             "local_fact": "at least 8 other dental offices within 2 miles of you", "has_online_booking": "False", "has_chat_widget": "False"}
        d = de.draft(r, "John", "3xAgentic", "123 Example St")
        self.assertTrue(d["body"].startswith("Hi there,"))     # named mailbox that isn't the owner's -> no name
        core = d["body"].split("\n\n")[1]
        self.assertEqual(core.count(". ") + core.count("? "), 2)
        self.assertTrue(core.endswith("?")); self.assertIn("Daybreak Dental ", core); self.assertNotIn("Google listing", core)
        d2 = de.draft(dict(r, email="info@daybreak.example", email_type="general"), "John", "3xAgentic", "123 Example St")
        self.assertTrue(d2["body"].startswith("Hi Dr. Chang,"))
        self.assertIsNone(de.draft(dict(r, fact_kind="", local_fact=""), "John", "3xAgentic", "x"))   # no true fact, no email
        self.assertIn("123 Example St", d2["body"]); self.assertIn('Reply "no"', d2["body"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
