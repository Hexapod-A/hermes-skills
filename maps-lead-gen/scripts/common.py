"""Shared helpers for the maps-lead-gen scripts (CSV I/O, HTTP, normalising, XLSX)."""
import csv, datetime as dt, json, os, re, sys, time
from urllib.parse import urlparse

UA_BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
UA_OSM = {"User-Agent": os.environ.get("OSM_USER_AGENT", "hermes-maps-lead-gen/1.0 (set OSM_USER_AGENT with your email)")}

US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
             "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
             "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
             "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
             "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
             "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
             "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
             "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}

# Mailboxes that are a shared/general inbox rather than a named person.
GENERAL_LOCALPARTS = {"info", "contact", "office", "hello", "hi", "team", "admin", "frontdesk", "front.desk", "reception", "appointments",
                      "appointment", "booking", "bookings", "schedule", "scheduling", "service", "services", "support", "sales", "help",
                      "mail", "email", "inquiries", "inquiry", "enquiries", "questions", "care", "customerservice", "billing", "staff",
                      "smile", "smiles", "dental", "dentist", "clinic", "practice", "manager", "office.manager", "officemanager", "hr", "jobs",
                      "careers", "marketing", "accounts", "accounting", "patients", "patientcare", "newpatients", "welcome", "general"}


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows, path, fieldnames=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames: fieldnames.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows: w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames})
    return path


def domain_of(url_or_email):
    s = (url_or_email or "").strip().lower()
    if not s: return ""
    if "@" in s and "/" not in s: return s.split("@", 1)[1]
    if not s.startswith("http"): s = "http://" + s
    return urlparse(s).netloc.split(":")[0].removeprefix("www.")


def norm_name(name):
    s = (name or "").lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(llc|inc|pllc|pc|pa|dds|dmd|md|co|corp|company|the|ltd)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_phone(p):
    d = re.sub(r"\D", "", p or "")
    if len(d) == 11 and d.startswith("1"): d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else (p or "").strip()


LOCATION_WORDS = ("downtown", "north", "south", "east", "west", "central", "uptown", "midtown", "office", "front", "desk", "team", "main")


def email_type(email, business_name=""):
    """'general' for shared inboxes (info@, office@, downtown@, <businessname>@gmail.com ...), else 'named'.
    'named' means "looks like a person's mailbox", not that we know whose it is."""
    if not email or "@" not in email: return ""
    lp = email.split("@")[0].lower()
    if lp in GENERAL_LOCALPARTS or re.fullmatch(r"(info|office|contact|hello)\d*", lp): return "general"
    if any(w in lp for w in LOCATION_WORDS): return "general"
    words = [x for x in norm_name(business_name).split() if len(x) > 3]
    if words and any(x in lp for x in words): return "general"
    if len(lp) > 18 and "." not in lp and "_" not in lp: return "general"   # e.g. downtowndentaldesign@
    return "named"


def to_int(x, default=None):
    try: return int(float(str(x).replace(",", "")))
    except Exception: return default


def to_float(x, default=None):
    try: return float(str(x).replace(",", ""))
    except Exception: return default


def env(name):
    v = os.environ.get(name, "").strip()
    return v or None


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def write_xlsx(sheets, path, about_lines=None):
    """sheets: list of (title, rows[, columns]). Black header, frozen row, filters, clickable URLs."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); wb.remove(wb.active)
    for sheet in sheets:
        title, rows = sheet[0], sheet[1]
        cols = sheet[2] if len(sheet) > 2 and sheet[2] else (list(rows[0].keys()) if rows else ["(empty)"])
        ws = wb.create_sheet(title[:31]); ws.append(cols)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="000000"); c.alignment = Alignment(vertical="center", wrap_text=True)
        for r in rows: ws.append([("" if r.get(c) is None else str(r.get(c)) if isinstance(r.get(c), (list, dict)) else r.get(c)) for c in cols])
        for i, c in enumerate(cols, 1):
            width = min(60, max([10, len(c)] + [len(str(r.get(c, ""))) for r in rows[:200]]) + 2)
            ws.column_dimensions[get_column_letter(i)].width = width
            for cell in ws[get_column_letter(i)][1:]:
                if isinstance(cell.value, str) and cell.value.startswith("http") and " " not in cell.value:
                    cell.hyperlink = cell.value; cell.font = Font(color="0563C1", underline="single")
        ws.freeze_panes = "B2"; ws.auto_filter.ref = ws.dimensions
    if about_lines:
        info = wb.create_sheet("About")
        for line in about_lines: info.append([line])
        info.column_dimensions["A"].width = 130
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)
    return path
