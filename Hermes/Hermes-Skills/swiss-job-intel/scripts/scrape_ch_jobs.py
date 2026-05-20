#!/usr/bin/env python3
"""
Swiss Job Intel — scraper optimisé (mai 2026)
Usage: python3 scrape_ch_jobs.py [profile_cache.json] > /tmp/all_offers.json 2>/tmp/scrape_log.txt

Optimisations v2 :
  - Swisscom plafonné à SWISSCOM_MAX_TERMS termes (évite 175 × réseau)
  - Pages détail Jobup / Jobs.ch / ANSAM / CIGES / Swisscom enrichissement en parallèle
  - 7 sources lancées en parallèle via ThreadPoolExecutor

IMPORTANT: Lancer via terminal(), jamais via execute_code (bloque le réseau).
"""
import urllib.request, urllib.parse, re, json, sys, time, os
import concurrent.futures

UA   = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"
LANG = "fr-CH,fr;q=0.9,en;q=0.8"

SWISSCOM_MAX_TERMS  = 20   # cap : évite 175 termes ESCO × réseau Workday
MAX_DETAIL_WORKERS  = 8    # threads pour les pages détail
MAX_SOURCE_WORKERS  = 5    # threads pour les sources

# ── Parser les arguments ──────────────────────────────────────────────────────
_profile_arg  = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".json") and not sys.argv[1].startswith("--") else None
_sources_path = None
for _i, _a in enumerate(sys.argv):
    if _a == "--sources" and _i + 1 < len(sys.argv):
        _sources_path = sys.argv[_i + 1]
        break

# ── Charger le profil depuis cache ────────────────────────────────────────────
_profile = None
for _p in [_profile_arg, os.path.join(os.getcwd(), "profile_cache.json")]:
    if _p and os.path.exists(_p):
        try:
            with open(_p, encoding="utf-8") as _f:
                _profile = json.load(_f)
            print(f"[profile] Chargé depuis {_p}", file=sys.stderr)
            break
        except Exception:
            pass

# ── Charger les sources sélectionnées ─────────────────────────────────────────
_selected_ids = None
if _sources_path and os.path.exists(_sources_path):
    try:
        with open(_sources_path, encoding="utf-8") as _f:
            _sel = json.load(_f)
        _selected_ids = {s.get("id") for s in _sel if s.get("id")}
        print(f"[sources] {len(_selected_ids)} sources sélectionnées : {sorted(_selected_ids)}", file=sys.stderr)
    except Exception as e:
        print(f"[sources] Erreur lecture {_sources_path}: {e} — toutes les sources actives", file=sys.stderr)

def source_active(sid: str) -> bool:
    """True si la source doit être scrapée (ou si pas de liste → toutes actives)."""
    return _selected_ids is None or sid in _selected_ids

# ── Vérification profil (obligatoire pour les termes de recherche) ────────────
if not (_profile and _profile.get("primary_terms")):
    print("❌ Aucun profil candidat trouvé — impossible de déterminer les termes de recherche.", file=sys.stderr)
    print("   Fournir profile_cache.json en argument ou le placer dans le répertoire courant.", file=sys.stderr)
    print("   Générer le profil : lancer le skill swiss-job-intel (Phase 0 → Phase 2C).", file=sys.stderr)
    sys.exit(1)

print(f"[profile] {len(_profile['primary_terms'])} termes depuis le profil candidat", file=sys.stderr)

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch(url, data=None, extra_headers=None, timeout=15):
    h = {
        "User-Agent": UA,
        "Accept-Language": LANG,
        # CRITICAL: always specify Accept or Workday returns empty pages
        "Accept": "text/html,application/json,*/*",
    }
    if extra_headers:
        h.update(extra_headers)
    try:
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

def norm_snippet(text, maxlen=600):
    t = re.sub(r'<script[^>]*>.*?</script>', ' ', str(text), flags=re.DOTALL)
    t = re.sub(r'<style[^>]*>.*?</style>', ' ', t, flags=re.DOTALL)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'&[a-z]+;', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:maxlen]

def extract_jsonld_jobposting(html):
    """Extract all JobPosting JSON-LD blocks from HTML."""
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    )
    jobs = []
    for b in blocks:
        try:
            d = json.loads(b.strip())
            items = d if isinstance(d, list) else [d]
            for i in items:
                if i.get("@type") == "JobPosting":
                    jobs.append(i)
        except:
            pass
    return jobs

def _coerce_url(value):
    """Normalise les variantes JSON-LD d'URL en chaîne exploitable."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("@id", "") or value.get("url", "") or value.get("id", "")
    if isinstance(value, list):
        for item in value:
            url = _coerce_url(item)
            if url:
                return url
    return ""

def from_jsonld(ld, source, fallback_url=""):
    """Convert a JSON-LD JobPosting dict to our standard offer dict.
    Handles both dict and list for jobLocation / hiringOrganization.
    """
    jloc = ld.get("jobLocation") or {}
    if isinstance(jloc, list): jloc = jloc[0] if jloc else {}
    loc_city = jloc.get("address", {}).get("addressLocality", "") if isinstance(jloc, dict) else ""

    horg = ld.get("hiringOrganization") or {}
    if isinstance(horg, list): horg = horg[0] if horg else {}
    employer_name = horg.get("name", "") if isinstance(horg, dict) else ""

    return make_offer(
        title       = ld.get("title", ""),
        employer    = employer_name or source,
        location    = loc_city,
        url         = _coerce_url(ld.get("url", "")) or _coerce_url(ld.get("mainEntityOfPage", "")) or fallback_url,
        date        = ld.get("datePosted", ""),
        description = ld.get("description", ""),
        source      = source,
    )

def make_offer(title, employer, location, url, date, description, source):
    return {
        "title":    title,
        "employer": employer,
        "location": location,
        "url":      url,
        "date":     date,
        "snippet":  norm_snippet(description, 600),
        "source":   source,
    }

log = lambda msg: print(msg, file=sys.stderr)

# ═══════════════════════════════════════════════════════════════════════════════
# SOURCES — chacune retourne list[dict] (thread-safe, pas d'état global)
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_swisscom() -> list:
    if not source_active("swisscom_workday"):
        log("[Swisscom] ignoré (non sélectionné)")
        return []

    # Priorité 1 : cap à SWISSCOM_MAX_TERMS pour éviter 175 termes × réseau Workday
    terms = _profile["primary_terms"][:SWISSCOM_MAX_TERMS]
    seen: set = set()
    offers: list = []

    for term in terms:
        body = json.dumps({"limit": 20, "offset": 0, "searchText": term, "locations": []}).encode()
        raw = fetch(
            "https://swisscom.wd103.myworkdayjobs.com/wday/cxs/swisscom/SwisscomExternalCareers/jobs",
            data=body,
            extra_headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
        )
        try:
            d = json.loads(raw)
            for j in d.get("jobPostings", []):
                path = j.get("externalPath", "")
                if path in seen: continue
                seen.add(path)
                offers.append(make_offer(
                    title       = j.get("title", ""),
                    employer    = "Swisscom",
                    location    = j.get("locationsText", ""),
                    url         = "https://swisscom.wd103.myworkdayjobs.com" + path,
                    date        = j.get("postedOn", ""),
                    description = "",
                    source      = "swisscom_workday",
                ))
        except:
            pass
        time.sleep(0.3)

    log(f"[Swisscom] {len(offers)} offres — enrichissement descriptions en parallèle...")

    # Priorité 2 : enrichissement des descriptions en parallèle
    def _enrich_swisscom(o):
        m = re.search(r'myworkdayjobs\.com(/job/.+)', o["url"])
        if not m:
            return o
        html = fetch(
            "https://swisscom.wd103.myworkdayjobs.com/SwisscomExternalCareers" + m.group(1),
            extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        )
        jobs = extract_jsonld_jobposting(html)
        if jobs:
            o["snippet"] = norm_snippet(jobs[0].get("description", ""), 600)
        return o

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as ex:
        offers = list(ex.map(_enrich_swisscom, offers))

    enriched = sum(1 for o in offers if o.get("snippet", "").strip())
    log(f"   → {enriched} descriptions enrichies")
    return offers


def scrape_ansam() -> list:
    if not source_active("ansam"):
        log("[ANSAM] ignoré (non sélectionné)")
        return []

    html = fetch("https://carrieres.ansam.ch/jobs")
    ansam_urls = list(set(re.findall(r'https://carrieres\.ansam\.ch/jobs/\d+[^"\'>\s]*', html)))
    log(f"[ANSAM] {len(ansam_urls)} URLs trouvées")

    # Priorité 2 : fetch des pages détail en parallèle
    def _fetch_ansam(url):
        html2 = fetch(url)
        return [from_jsonld(ld, "ansam", fallback_url=url) for ld in extract_jsonld_jobposting(html2)]

    offers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as ex:
        for results in ex.map(_fetch_ansam, ansam_urls):
            offers.extend(results)

    log(f"   → {len(offers)} offres ANSAM")
    return offers


def scrape_admin_federal() -> list:
    if not source_active("admin_federal"):
        log("[Admin fédéral] ignoré (non sélectionné)")
        return []

    raw = fetch("https://ohws.prospective.ch/public/v1/medium/1000625?lang=fr&limit=80")
    offers = []
    try:
        data = json.loads(raw)
        jobs = data if isinstance(data, list) else data.get("items", data.get("jobs", []))
        for j in jobs:
            offers.append(make_offer(
                title       = j.get("title") or j.get("jobTitle", ""),
                employer    = j.get("company") or j.get("employer", ""),
                location    = j.get("location") or j.get("city", ""),
                url         = j.get("url") or j.get("link", ""),
                date        = j.get("date") or j.get("publicationDate", ""),
                description = str(j.get("description") or j.get("text", ""))[:300],
                source      = "admin_federal",
            ))
        log(f"[Admin fédéral] {len(offers)} offres")
    except:
        log("[Admin fédéral] Vide ou indisponible — skip")
    return offers


def scrape_ciges() -> list:
    if not source_active("ciges"):
        log("[CIGES] ignoré (non sélectionné)")
        return []

    html = fetch("https://www.ciges.ch/carriere/")
    ciges_urls = list(set(re.findall(r'https://www\.ciges\.ch/job/[^"\'>\s]+', html)))

    # Priorité 2 : fetch des pages détail en parallèle
    def _fetch_ciges(url):
        html2 = fetch(url)
        return [from_jsonld(ld, "ciges", fallback_url=url) for ld in extract_jsonld_jobposting(html2)]

    offers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as ex:
        for results in ex.map(_fetch_ciges, ciges_urls):
            offers.extend(results)

    log(f"[CIGES] {len(offers)} offres")
    return offers


def scrape_jobup() -> list:
    if not source_active("jobup"):
        log("[Jobup] ignoré (non sélectionné)")
        return []

    terms = _profile["primary_terms"][:7]
    seen: set = set()
    detail_paths: list = []

    for term in terms:
        encoded = urllib.parse.quote_plus(term)
        html = fetch(f"https://www.jobup.ch/fr/emplois/?term={encoded}")
        for p in re.findall(r'href="(/fr/emplois/detail/[a-f0-9-]+/)"', html):
            if p not in seen:
                seen.add(p)
                detail_paths.append(p)
        time.sleep(0.3)
        if len(detail_paths) >= 60:
            break

    log(f"[Jobup] {len(detail_paths)} URLs d'offres uniques")

    # Priorité 2 : fetch des pages détail en parallèle
    def _fetch_jobup(path):
        detail_url = f"https://www.jobup.ch{path}"
        html2 = fetch(detail_url)
        return [from_jsonld(ld, "jobup", fallback_url=detail_url) for ld in extract_jsonld_jobposting(html2)]

    offers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as ex:
        for results in ex.map(_fetch_jobup, detail_paths):
            offers.extend(results)

    log(f"   → {len(offers)} offres Jobup")
    return offers


def scrape_jobs_ch() -> list:
    if not source_active("jobs_ch"):
        log("[Jobs.ch] ignoré (non sélectionné)")
        return []

    terms = _profile["primary_terms"][:7]
    seen: set = set()
    detail_paths: list = []

    for term in terms:
        encoded = urllib.parse.quote_plus(term)
        html = fetch(f"https://www.jobs.ch/de/stellenangebote/?term={encoded}")
        for p in re.findall(r'href="(/de/stellenangebote/detail/[a-f0-9-]+/)"', html):
            if p not in seen:
                seen.add(p)
                detail_paths.append(p)
        time.sleep(0.3)
        if len(detail_paths) >= 60:
            break

    log(f"[Jobs.ch] {len(detail_paths)} URLs d'offres uniques")

    # Priorité 2 : fetch des pages détail en parallèle
    def _fetch_jobs_ch(path):
        detail_url = f"https://www.jobs.ch{path}"
        html2 = fetch(detail_url)
        return [from_jsonld(ld, "jobs_ch", fallback_url=detail_url) for ld in extract_jsonld_jobposting(html2)]

    offers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as ex:
        for results in ex.map(_fetch_jobs_ch, detail_paths):
            offers.extend(results)

    log(f"   → {len(offers)} offres Jobs.ch")
    return offers


def scrape_suissetalent() -> list:
    if not source_active("suissetalent"):
        log("[Suissetalent] ignoré (non sélectionné)")
        return []

    terms = _profile["primary_terms"][:8]
    seen: set = set()
    offers: list = []

    for term in terms:
        encoded = urllib.parse.quote_plus(term)
        html = fetch(f"https://www.suissetalent.ch/emplois?term={encoded}")
        for ld in extract_jsonld_jobposting(html):
            url_key = (
                _coerce_url(ld.get("url", "")) or
                _coerce_url(ld.get("mainEntityOfPage", "")) or
                (ld.get("title", "") + "|" + str(ld.get("hiringOrganization", "")))
            )
            if url_key and url_key not in seen:
                seen.add(url_key)
                offers.append(from_jsonld(ld, "suissetalent"))
        time.sleep(0.3)

    log(f"[Suissetalent] {len(offers)} offres")
    return offers


# ═══════════════════════════════════════════════════════════════════════════════
# Priorité 3 — Exécution parallèle des 7 sources
# ═══════════════════════════════════════════════════════════════════════════════

SCRAPERS = [
    scrape_swisscom,
    scrape_ansam,
    scrape_admin_federal,
    scrape_ciges,
    scrape_jobup,
    scrape_jobs_ch,
    scrape_suissetalent,
]

all_offers: list = []
seen_urls:  set  = set()

def add(offer):
    key = offer.get("url") or (offer["title"] + "|" + offer["employer"])
    if key and key not in seen_urls:
        seen_urls.add(key)
        all_offers.append(offer)

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_SOURCE_WORKERS) as _ex:
    _futures = {_ex.submit(fn): fn.__name__ for fn in SCRAPERS}
    for _future in concurrent.futures.as_completed(_futures):
        try:
            for offer in _future.result():
                add(offer)
        except Exception as _e:
            log(f"[err] {_futures[_future]}: {_e}")

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

by_source = {}
for o in all_offers:
    by_source[o["source"]] = by_source.get(o["source"], 0) + 1

log(f"\n{'='*60}")
log(f"TOTAL: {len(all_offers)} offres uniques")
for s, n in sorted(by_source.items()):
    with_desc = sum(1 for o in all_offers if o["source"] == s and o.get("snippet", "").strip())
    log(f"  {s}: {n} offres ({with_desc} avec description)")

print(json.dumps(all_offers, ensure_ascii=False, indent=2))
