#!/usr/bin/env python3
"""Owner-name finder. Reads the pages enrich_site.py cached (About/Team/Contact/footer) and returns the
owner / founder / principal / doctor ONLY when the site shows the name next to such a title. Else "not found".

Two layers, both strict:
  1. LLM (if configured): prompt in references/owner-prompt.md, instructions first, per-business variables last.
  2. A guard that re-reads the page: the returned name must literally appear within ~80 characters of a title
     word. If not, the answer is thrown away -> "not found" (owner_method = llm_rejected_by_guard).
  Without an LLM it runs the regex layer only (owner_method = regex), with the same proximity rule.

LLM config (any OpenAI-compatible endpoint, or Anthropic):
  LLM_BASE_URL + LLM_API_KEY + LLM_MODEL   e.g. https://openrouter.ai/api/v1, Nous Portal, OpenAI, DeepSeek, local Ollama
  or OPENROUTER_API_KEY (+ LLM_MODEL)       or OPENAI_API_KEY (default model gpt-4o-mini)
  or ANTHROPIC_API_KEY (default model claude-haiku-4-5; ANTHROPIC_BASE_URL optional)
  --no-llm forces regex-only.

Usage:
  find_owner.py enriched.csv --out owners.csv [--sample 50]      # --sample: first N rows + a hand-check sheet
Adds: owner_first, owner_last, owner_title, owner_quote, owner_page, owner_method, owner_checked_at
"""
import argparse, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import env, log, now_iso, read_csv, write_csv, write_xlsx

HERE = os.path.dirname(os.path.abspath(__file__))
TITLE_WORDS = r"(?:owner|co-owner|founder|co-founder|founding|principal|president|ceo|managing partner|proprietor|dr\.?|doctor|dds|dmd|d\.d\.s\.|d\.m\.d\.|md|m\.d\.|do|dc|d\.c\.|dvm|od|esq\.?)"
TITLE_RE = re.compile(r"\b" + TITLE_WORDS + r"(?=\W|$)", re.I)
NAME = r"([A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)\s+(?:[A-Z]\.\s+)?((?:(?:Del|De|Da|Di|Van|Von|La|Le|St\.)\s+)?(?:Mc|Mac|O')?[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?)"
# Owner/founder patterns are tried on every page before the credential (Dr./DDS) patterns.
PATTERNS = [
    (re.compile(r"\b(?:[Ff]ounded|[Ee]stablished|[Ss]tarted)\s+(?:in\s+\d{4}\s+)?by\s+(?:Dr\.?\s+)?" + NAME), "Founder"),
    (re.compile(NAME + r",?\s+(?:is\s+)?(?:the\s+)?([Oo]wner|[Ff]ounder|[Cc]o-[Ff]ounder|[Pp]rincipal|[Pp]resident|[Pp]roprietor)\b"), None),
    (re.compile(r"\b(?:[Oo]wner|[Ff]ounder|[Cc]o-[Ff]ounder|[Pp]rincipal|[Pp]resident|[Pp]roprietor|OWNER|FOUNDER)(?:\s+(?:and|&)\s+\w+)?\s*(?:[:,\-–]|is|was)?\s*(?:Dr\.?\s+)?" + NAME), "from-context"),
    (re.compile(r"\bDr\.?\s+" + NAME), "Dr."),
    (re.compile(NAME + r",?\s+(D\.?D\.?S\.?|D\.?M\.?D\.?|M\.?D\.?|D\.?V\.?M\.?|D\.?C\.?|O\.?D\.?|Esq\.?)(?=\W|$)"), None),
]
NOT_NAMES = {"Our", "The", "Meet", "About", "Dental", "Family", "Austin", "Contact", "Read", "More", "Learn", "Schedule", "Book", "Call",
             "Smile", "Team", "Office", "Welcome", "Request", "New", "Patient", "Patients", "Privacy", "Policy", "Terms", "Home", "View", "Click",
             "Cosmetic", "General", "Pediatric", "Orthodontics", "Services", "Insurance", "Financing", "Doctor", "Doctors", "Practice", "Center",
             "Texas", "South", "North", "East", "West", "Downtown", "Street", "Suite", "Avenue", "Road", "Monday", "Friday", "Saturday", "Sunday",
             "Has", "Is", "Was", "And", "Will", "Can", "Offers", "Provides", "Received", "Earned", "Graduated", "Joined", "Practices", "Grew",
             "Loves", "Enjoys", "Believes", "Specializes", "Brings", "Also", "Who", "With", "At", "In", "Of", "Today", "Now", "Here", "Info",
             "Director", "Manager", "Hygienist", "Assistant", "Coordinator", "Owner", "Founder", "President", "Principal", "Dentist", "Ceo"}
BUSINESS_WORDS = re.compile(r"orthodont|dental|dentist|clinic|smile|studio|spa\b|roof|plumb|hvac|law\b|legal|group|salon|medical|health|"
                            r"family|cosmetic|pediatric|implant|care\b|services?\b|center|wellness|vet\b|animal|auto|realty|insurance", re.I)
PAGE_ORDER = {"team": 0, "about": 1, "home": 2, "contact": 3, "footer": 4, "careers": 5}


def load_prompt():
    with open(os.path.join(HERE, "..", "references", "owner-prompt.md"), encoding="utf-8") as f:
        t = f.read()
    return t.split("SYSTEM / INSTRUCTIONS (identical for every row):", 1)[1].split("---", 1)[0].strip()


def pages_of(row):
    p = row.get("site_cache")
    if not p or not os.path.exists(p): return []
    with open(p, encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    return sorted(((u, v["kind"], v["text"]) for u, v in pages.items()), key=lambda x: PAGE_ORDER.get(x[1], 9))


def excerpt(text, limit):
    """Keep the parts of a page around title words (cuts tokens); fall back to the page start."""
    spans = [(max(0, m.start() - 300), m.end() + 300) for m in TITLE_RE.finditer(text)]
    if not spans: return text[: min(limit, 1200)]
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]: merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else: merged.append((s, e))
    return " … ".join(text[s:e] for s, e in merged)[:limit]


def guard(first, last, pages):
    """True only if 'first last' (or 'last' after Dr.) sits within ~80 chars of a title word on a cached page."""
    if not first or not last: return None
    for url, kind, text in pages:
        for m in re.finditer(re.escape(first) + r"\s+(?:[A-Z]\.\s+)?" + re.escape(last), text):
            window = text[max(0, m.start() - 80): m.end() + 80]
            if TITLE_RE.search(window): return url if kind != "footer" else "footer"
        for m in re.finditer(r"Dr\.?\s+" + re.escape(last), text):
            if first in text: return url if kind != "footer" else "footer"
    return None


def regex_find(pages):
    for rx, fixed_title in PATTERNS:
        for url, kind, text in pages:
            for m in rx.finditer(text):
                g = [x for x in m.groups() if x]
                names = [x for x in g if x[:1].isupper() and x.lower() not in ("owner", "founder", "co-founder", "principal", "president", "proprietor")]
                if len(names) < 2: continue
                first, last = names[0], names[1]
                if first in NOT_NAMES or last in NOT_NAMES or len(first) < 2: continue
                if BUSINESS_WORDS.search(first + " " + last): continue
                if fixed_title == "from-context":
                    title = re.search(r"owner|founder|co-founder|principal|president|proprietor", m.group(0), re.I).group(0).title()
                elif fixed_title: title = fixed_title
                else: title = next((x for x in g if x not in (first, last)), "").strip()
                if not guard(first, last, pages): continue
                return {"first_name": first, "last_name": last, "title": title, "quote": m.group(0)[:120], "page": url if kind != "footer" else "footer"}
    return None


class LLM:
    def __init__(self):
        self.kind = None
        base, key, model = env("LLM_BASE_URL"), env("LLM_API_KEY"), env("LLM_MODEL")
        if base and key:
            self.kind, self.base, self.key, self.model = "openai", base.rstrip("/"), key, model or "gpt-4o-mini"
        elif env("OPENROUTER_API_KEY"):
            self.kind, self.base, self.key, self.model = "openai", "https://openrouter.ai/api/v1", env("OPENROUTER_API_KEY"), model or "openai/gpt-4o-mini"
        elif env("OPENAI_API_KEY"):
            self.kind, self.base, self.key, self.model = "openai", "https://api.openai.com/v1", env("OPENAI_API_KEY"), model or "gpt-4o-mini"
        elif env("ANTHROPIC_API_KEY"):
            self.kind, self.base, self.key, self.model = "anthropic", (env("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/"), env("ANTHROPIC_API_KEY"), model or "claude-haiku-4-5"
        self.instructions = load_prompt()

    def build(self, business, website, pages, budget=6000):
        parts = [f"Business: {business}", f"Website: {website}", "Pages:"]
        left = budget
        for url, kind, text in pages:
            ex = excerpt(text, min(left, 2500))
            if not ex: continue
            parts.append(f"### {url} ({kind})\n{ex}"); left -= len(ex)
            if left <= 300: break
        return "\n".join(parts)

    def ask(self, variables):
        if self.kind == "openai":
            r = requests.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"}, timeout=90,
                              json={"model": self.model, "temperature": 0, "max_tokens": 200,
                                    "messages": [{"role": "system", "content": self.instructions}, {"role": "user", "content": variables}]})
            r.raise_for_status(); txt = r.json()["choices"][0]["message"]["content"]
        else:
            r = requests.post(f"{self.base}/v1/messages", timeout=90,
                              headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": self.model, "max_tokens": 200, "temperature": 0,
                                    "system": [{"type": "text", "text": self.instructions, "cache_control": {"type": "ephemeral"}}],
                                    "messages": [{"role": "user", "content": variables}]})
            r.raise_for_status(); txt = "".join(b.get("text", "") for b in r.json()["content"])
        return parse_answer(txt)


def parse_answer(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m: return {"status": "not found"}
    try: j = json.loads(m.group(0))
    except Exception: return {"status": "not found"}
    if str(j.get("status", "")).lower() != "found" or not j.get("first_name") or not j.get("last_name"): return {"status": "not found"}
    return j


def find(row, llm, use_llm):
    out = dict(row)
    out.update(owner_first="", owner_last="", owner_title="", owner_quote="", owner_page="", owner_method="", owner_checked_at=now_iso())
    pages = pages_of(row)
    if not pages:
        out["owner_method"] = "no site pages"; out["owner_first"] = "not found"; return out
    if use_llm and llm.kind:
        try:
            ans = llm.ask(llm.build(row.get("business_name", ""), row.get("site_final_url") or row.get("website", ""), pages))
        except Exception as e:
            ans = None; out["owner_method"] = f"llm error: {str(e)[:80]}"
        if ans and ans.get("status") == "found":
            first, last = ans["first_name"].strip(), ans["last_name"].strip()
            first = re.sub(r"^(Dr\.?|Doctor)\s+", "", first)
            page = guard(first, last, pages)
            if page:
                out.update(owner_first=first, owner_last=last, owner_title=ans.get("title", ""), owner_quote=(ans.get("quote") or "")[:160],
                           owner_page=page, owner_method="llm+guard"); return out
            out.update(owner_first="not found", owner_method=f"llm_rejected_by_guard ({first} {last})"); return out
        if ans is not None:
            out.update(owner_first="not found", owner_method="llm: not found"); return out
    hit = regex_find(pages)
    if hit:
        out.update(owner_first=hit["first_name"], owner_last=hit["last_name"], owner_title=hit["title"], owner_quote=hit["quote"],
                   owner_page=hit["page"], owner_method="regex")
    else:
        out.update(owner_first="not found", owner_method=out["owner_method"] or "regex: not found")
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True)
    ap.add_argument("--sample", type=int, default=0, help="only the first N rows, plus a hand-check XLSX (do 50 before a full run)")
    ap.add_argument("--no-llm", action="store_true"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    rows = read_csv(a.csv)
    if a.sample: rows = rows[: a.sample]
    llm = LLM()
    use = not a.no_llm and bool(llm.kind)
    log(f"owner finder: {'LLM ' + llm.model + ' + guard' if use else 'regex only (no LLM configured)'}")
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda r: find(r, llm, use), rows))
    write_csv(res, a.out)
    found = sum(1 for r in res if r["owner_first"] and r["owner_first"] != "not found")
    if a.sample:
        cols = ["business_name", "website", "owner_first", "owner_last", "owner_title", "owner_quote", "owner_page", "owner_method", "correct? (y/n)", "notes"]
        path = os.path.splitext(a.out)[0] + "_handcheck.xlsx"
        write_xlsx([("Hand-check", res, cols)], path, about_lines=[
            "Hand-check before the full run: open owner_page for each row and mark correct? y/n.",
            "A wrong name is worse than 'not found'. If more than 1-2 of 50 are wrong, tighten the prompt or switch model before running the full list.",
            "'not found' rows are fine: they get the general inbox and a 'Hi there' opener."])
        log(f"hand-check sheet -> {path}")
    print(f"{len(res)} rows, owner found for {found} ({100 * found // max(1, len(res))}%), 'not found' for {len(res) - found} -> {a.out}")


if __name__ == "__main__":
    main()
