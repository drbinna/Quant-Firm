# api/facts.py
# ---------------------------------------------------------------------------
# Live SEC EDGAR XBRL proxy for the margin-trend chart. Stdlib only.
# Pulls the SAME ground truth the auditor reconciles against (data.sec.gov),
# server-side (SEC sets no CORS header and requires a User-Agent the browser
# can't set), and returns a compact gross-margin-by-fiscal-year series.
#
#   GET /api/facts            -> Apple (CIK 0000320193)
#   GET /api/facts?cik=789019 -> any CIK (zero-padded automatically)
#   200 -> {"entity": "...", "cik": "...", "series": [{"fy":2022,"end":"...",
#           "revenue":..., "grossProfit":..., "margin":43.31}, ...]}
# ---------------------------------------------------------------------------

import os, re, json, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
UA  = os.environ.get("SEC_USER_AGENT",
                     "Quant Firm verification console (contact obinnaamadie@gmail.com)")
DEFAULT_CIK = "0000320193"  # Apple Inc.
GP_CONCEPT  = "GrossProfit"
REV_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
CY = re.compile(r"^CY\d{4}$")   # full-year frames only (excludes CY2022Q3 etc.)


def _get(cik, concept):
    req = urllib.request.Request(URL.format(cik=cik, concept=concept),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _annual(doc):
    out = {}
    for u in ((doc.get("units") or {}).get("USD") or []):
        fr = u.get("frame")
        if fr and CY.match(fr):
            out[int(fr[2:])] = {"end": u.get("end"), "val": u.get("val")}
    return out


def build(cik):
    gp_doc = _get(cik, GP_CONCEPT)
    entity = gp_doc.get("entityName")
    gp = _annual(gp_doc)
    rev = {}
    for c in REV_CONCEPTS:
        try:
            doc = _get(cik, c)
        except Exception:
            continue
        entity = entity or doc.get("entityName")
        a = _annual(doc)
        for y, v in a.items():
            rev.setdefault(y, v)
        if rev:
            break
    series = []
    for y in sorted(set(gp) & set(rev)):
        r = rev[y]["val"]; g = gp[y]["val"]
        if not r:
            continue
        series.append({"fy": y, "end": rev[y]["end"], "revenue": r,
                       "grossProfit": g, "margin": round(g / r * 100, 2)})
    return {"entity": entity or "", "cik": cik, "series": series}


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, cache=False):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control",
                             "public, s-maxage=86400, stale-while-revalidate=604800")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        cik = DEFAULT_CIK
        if "?" in self.path:
            for kv in self.path.split("?", 1)[1].split("&"):
                if kv.startswith("cik="):
                    digits = "".join(ch for ch in kv[4:] if ch.isdigit())
                    if digits:
                        cik = digits.zfill(10)
        try:
            data = build(cik)
            if not data["series"]:
                raise RuntimeError("no annual gross-margin facts for this CIK")
            self._send(200, data, cache=True)
        except Exception as e:
            self._send(502, {"error": str(e)})
