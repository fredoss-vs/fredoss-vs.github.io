#!/usr/bin/env python3
"""
Swisscom Workday scraper — écrire dans /tmp/, exécuter via mcp_terminal.
Retourne JSON sur stdout, logs sur stderr.

Usage:
    python3 /tmp/scrape_swisscom_workday.py > /tmp/jobs_swisscom.json

IMPORTANT (WSL): Ne pas exécuter via execute_code — le réseau est bloqué.
Toujours via mcp_terminal après write_file dans /tmp/.
"""
import urllib.request, json, re, sys, time

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"

SEARCH_TERMS = [
    "service delivery", "incident manager", "ITSM", "IT operations", "support IT",
    "coordinateur IT", "technicien IT", "helpdesk", "service desk", "operation engineer",
    "IT specialist", "application manager", "operation manager", "support specialist",
]

def post_workday(term):
    url = "https://swisscom.wd103.myworkdayjobs.com/wday/cxs/swisscom/SwisscomExternalCareers/jobs"
    body = json.dumps({"limit": 20, "offset": 0, "searchText": term, "locations": []}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [SKIP] '{term}': {e}", file=sys.stderr)
        return {}

def fetch_description(external_path):
    """
    Fetch real job description from Workday HTML page.
    external_path example: /job/Fribourg/ICT-Operational-Engineer-II_R-0005331
    Returns plain-text description (up to 800 chars) or ''.
    """
    url = f"https://swisscom.wd103.myworkdayjobs.com/SwisscomExternalCareers{external_path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-CH,fr;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return ""

    # Extract JSON-LD JobPosting
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    )
    for b in blocks:
        try:
            d = json.loads(b.strip())
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                desc = d.get("description", "")
                # Strip HTML tags from description
                desc = re.sub(r'<[^>]+>', ' ', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()
                return desc[:800]
        except:
            pass
    return ""

# ── Main scrape ───────────────────────────────────────────────────────────────
all_results = []
seen = set()

for term in SEARCH_TERMS:
    data = post_workday(term)
    for j in data.get("jobPostings", []):
        path = j.get("externalPath", "")
        if path in seen:
            continue
        seen.add(path)
        all_results.append({
            "title":    j.get("title", ""),
            "employer": "Swisscom",
            "location": j.get("locationsText", ""),
            "url":      "https://swisscom.wd103.myworkdayjobs.com" + path,
            "date":     j.get("postedOn", ""),
            "snippet":  "",  # filled below
            "source":   "swisscom_workday",
            "_path":    path,
        })
    time.sleep(0.4)

print(f"[Swisscom] {len(all_results)} offres uniques trouvées", file=sys.stderr)

# ── Enrich descriptions for top candidates (optional — takes ~0.4s/offer) ────
# Set ENRICH=True to fetch descriptions. Add title keywords to filter which ones.
ENRICH = True
ENRICH_KEYWORDS = [
    "support", "incident", "operation", "itsm", "helpdesk", "service desk",
    "ict", "coordinator", "escalation", "application manager",
]

if ENRICH:
    enriched = 0
    for o in all_results:
        title_low = o["title"].lower()
        if not any(kw in title_low for kw in ENRICH_KEYWORDS):
            continue
        desc = fetch_description(o["_path"])
        if desc:
            o["snippet"] = desc
            enriched += 1
        time.sleep(0.35)
    print(f"[Enrich] {enriched} descriptions récupérées", file=sys.stderr)

# Clean internal field
for o in all_results:
    o.pop("_path", None)

print(json.dumps(all_results, ensure_ascii=False))
print(f"[TOTAL] {len(all_results)} offres", file=sys.stderr)
