# Réalités technologiques des sites d'emploi suisses
# Mis à jour : mai 2026 — vérifié live en session

## Règle d'or réseau (WSL / Hermes)

`execute_code` BLOQUE les connexions réseau sortantes.
`terminal()` fonctionne parfaitement avec curl et python3.
**Toujours écrire les scripts dans /tmp/ et les lancer via terminal().**

---

## Tableau de sources 


| Source | URL | Type | Statut | Notes |
|--------|-----|------|--------|-------|
| ABB | abb.wd3.myworkdayjobs.com | Workday JSON POST API | ✅ À tester | Confirmé Workday via page "How to apply". Industrie/IT. Zurich |
| Admin fédéral OHWS | ohws.prospective.ch/public/v1/medium/1000625 | JSON API | ❌ Vide mai 2026 | Réponse vide, skip |
| ANSAM | carrieres.ansam.ch | Teamtailor — JSON-LD/page | ✅ Fiable | Scraper listing → follow URLs → JSON-LD |
| BCV | jobs.bcv.ch/services/rss/category/ | RSS | ❌ RSS vide | 0 offre IT |
| BCVs | bcvs.ch/la-bcvs/carriere/... | Liferay JS | ❌ Pas de JSON-LD | HTML 162KB, rien de structuré |
| CFF/SBB | company.sbb.ch/.../postes-vacants | SPA | ❌ Vide | Confirmé vide |
| CHUV | chuv.ch/fr/carriere | Cloudflare Turnstile | ❌ Bot-protégé | Challenge JS obligatoire |
| CIGES | ciges.ch/carriere | WordPress | ⚠️ 1 seule offre | JSON-LD présent mais listing quasi vide |
| Experteer | experteer.ch | Plateforme cadres supérieurs | ⚠️ À tester | Cadres 120k+ CHF. Accès limité ? |
| financejobs.ch | financejobs.ch | JobCloud spécialisé | ❌ Probablement SPA | Niche finance, même infra JobCloud |
| Glassdoor.ch | glassdoor.ch | SPA React | ❌ SPA + anti-bot | Évaluations entreprises + offres. Pas d'API publique, protection anti-scraping |
| Groupe E | job.groupe-e.ch | Redirection LinkedIn | ❌ Hors scope | Renvoie vers linkedin.com/company/groupe-e/jobs |
| Groupe Mutuel | groupemutuel.csod.com | ATS JS | ❌ Skip | JS obligatoire |
| HUG | hug.ch/emploi | Drupal | ❌ Non exploitable | 7 liens détectés, 0 JSON-LD |
| ictcareer.ch | ictcareer.ch | JobCloud spécialisé IT | ❌ Probablement SPA | Portail IT du groupe JobCloud. Même infra que jobs.ch |
| ictjobs.ch | ictjobs.ch | HTML/SPA mixte | ❌ Pas de JSON-LD | Testé, rien |
| Indeed | indeed.ch | Anti-bot | ❌ Bloqué | CAPTCHA/challenge |
| ingjobs.ch | ingjobs.ch | JobCloud spécialisé | ❌ Probablement SPA | Niche ingénierie, même infra JobCloud |
| Job-Room (arbeit.swiss) | api.job-room.ch/jobAdvertisements/v1 | REST JSON API officielle | ✅ Priorité | API SECO documentée, 80 000+ offres. Obligation d'annonce = exclusivité 5j |
| JobCourier | jobcourier.ch | WordPress BLOG | ❌ Pas d'offres | C'est un blog RH, pas un portail emploi |
| Jobtic | jobtic.ch | Agrégateur classique | ⚠️ À tester | Basé à Lausanne, agrège entreprises + agences. Vérifier JSON-LD ou flux RSS |
| jobs.ch | jobs.ch | SPA (Next.js) | ❌ SPA pure | NEXT_DATA présent mais vide côté jobs |
| jobs4sales.ch | jobs4sales.ch | JobCloud spécialisé | ❌ Probablement SPA | Niche vente, même infra JobCloud |
| Jobscout24.ch | jobscout24.ch/fr/jobs | SPA | ❌ SPA pure | HTML shell |
| JobUp | jobup.ch | SPA (React) | ❌ SPA pure | HTML shell, 0 JSON-LD, pas d'API publique |
| jobwatch.ch | jobwatch.ch | Portail horlogerie/luxe | ⚠️ À tester | Niche horlogerie, microtechnique, luxe |
| jobwinner.ch | jobwinner.ch | SPA | ❌ SPA pure | HTML shell |
| La Mobilière | jobs.mobiliar.ch | ATS HTML | ❌ Vide | Confirmé vide |
| La Poste | job.post.ch | SPA | ❌ Vide | Confirmé vide |
| LinkedIn | linkedin.com | Auth requise | ❌ Non accessible | Auth + bot-protection |
| medienjobs.ch | medienjobs.ch | Portail médias/comm | ⚠️ À tester | Niche médias/communication CH-DE |
| monster.ch | monster.ch/emploi | SPA | ❌ SPA pure | HTML shell |
| Nestlé | nestle.com/jobs/search-jobs | SPA propriétaire | ⚠️ À tester | HQ Vevey. Probablement Workday ou custom, confirmer endpoint |
| Novartis | novartis.wd3.myworkdayjobs.com/Novartis_Careers | Workday JSON POST API | ✅ Priorité | Même pattern Workday. Pharma + IT. Basel |
| OIKEN | oiken.ch/travailler-chez-oiken | HTML statique | ❌ Pas de JSON-LD | HTML 142KB, rien de structuré |
| publicjobs.ch | publicjobs.ch/fr | HTML statique | ❌ Pas de filtre IT | Offres artisanat/saisonnières uniquement |
| Roche | roche.wd3.myworkdayjobs.com/roche-ext | Workday JSON POST API | ✅ Priorité | Même pattern que Swisscom. Pharma, IT, R&D. Basel |
| romandie.com | emploi.romandie.com | SPA (Next.js) | ❌ SPA pure | NEXT_DATA présent mais jobs non exposés |
| stellenanzeiger.ch | stellenanzeiger.ch | Portail généraliste | ⚠️ À tester | Un des plus grands marchés emploi CH. Vérifier type technique |
| SUVA | jobs.suva.ch/services/rss/category/?catid=3914601 | RSS | ❌ RSS vide | 0 offre en mai 2026 |
| Sword Group | sword-group.com | WordPress custom | ❌ Non standard | WP REST API retourne articles pas jobs |
| Swiss Life | swisslife.wd3.myworkdayjobs.com/Swiss_Life_Career_Site | Workday JSON POST API | ✅ Fiable | Assurance. Division internationale + CH |
| SwissDevJobs | swissdevjobs.ch | SPA (JS required) | ⚠️ À tester | 80 000+ users/mois, spécialisé dev/IT avec salaires. Vérifier API ou sitemap structuré |
| Swisscom Workday | swisscom.wd103.myworkdayjobs.com | JSON POST API | ✅ Priorité 1 | Descriptions via enrichissement HTML |
| Tietalent | tietalent.com | Plateforme IT/marketing | ⚠️ À tester | Spécialisé IT + digital marketing CH |
| topjobs.ch | topjobs.ch | JobCloud (même groupe jobs.ch) | ❌ Probablement SPA | Écosystème JobCloud, même stack que jobs.ch/jobup.ch |
| UBS | ubs.com/global/en/careers/search-jobs.html | SPA propriétaire | ⚠️ À tester | Pas de Workday public visible. Vérifier API sous-jacente |
| WTJ | welcometothejungle.com | SPA | ❌ SPA pure | HTML shell |
| Zurich Insurance | zurich.com/careers | SPA propriétaire | ⚠️ À tester | Gros recruteur CH. Vérifier ATS sous-jacent (Workday, SuccessFactors, custom) |
| Zühlke | zuehlke.wd3.myworkdayjobs.com/Zuhlke-Careers | Workday JSON POST API | ✅ Fiable | Consulting tech/engineering, très IT. Zurich |





---

## Patterns de code validés

### 1. Swisscom Workday — POST JSON + Enrichissement HTML

```python
import urllib.request, json, re, time

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"

def workday_search(term, employer="swisscom", career="SwisscomExternalCareers", host="swisscom.wd103.myworkdayjobs.com"):
    """POST search API — returns list of job dicts."""
    body = json.dumps({"limit":20,"offset":0,"searchText":term,"locations":[]}).encode()
    req = urllib.request.Request(
        f"https://{host}/wday/cxs/{employer}/{career}/jobs",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return d.get("jobPostings", [])

def workday_enrich(raw_url, career="SwisscomExternalCareers", host="swisscom.wd103.myworkdayjobs.com"):
    """Fetch job detail page — MUST use Accept: text/html or Workday returns empty."""
    m = re.search(r'myworkdayjobs\.com(/job/.+)', raw_url)
    if not m: return ""
    html_url = f"https://{host}/{career}{m.group(1)}"
    req = urllib.request.Request(html_url, headers={
        "User-Agent": UA,
        # CRITICAL: without this header Workday returns an empty page
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-CH,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")
    jobs = extract_jsonld_jobposting(html)
    return jobs[0].get("description","") if jobs else ""
```

### 2. Extracteur JSON-LD robuste (gère list/dict pour jobLocation)

```python
def extract_jsonld_jobposting(html):
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
        except: pass
    return jobs

def from_jsonld(ld, source):
    # jobLocation et hiringOrganization peuvent être list OU dict (Teamtailor, Workday)
    jloc = ld.get("jobLocation") or {}
    if isinstance(jloc, list): jloc = jloc[0] if jloc else {}
    loc_city = jloc.get("address",{}).get("addressLocality","") if isinstance(jloc,dict) else ""

    horg = ld.get("hiringOrganization") or {}
    if isinstance(horg, list): horg = horg[0] if horg else {}
    employer_name = horg.get("name","") if isinstance(horg,dict) else ""

    return {
        "title":    ld.get("title",""),
        "employer": employer_name or source,
        "location": loc_city,
        "url":      ld.get("url","") or ld.get("mainEntityOfPage",""),
        "date":     ld.get("datePosted",""),
        "snippet":  norm_snippet(ld.get("description",""), 600),
        "source":   source,
    }
```

### 3. ANSAM Teamtailor — pattern listing + follow

```python
def scrape_ansam():
    html = fetch("https://carrieres.ansam.ch/jobs")
    job_urls = list(set(re.findall(r'https://carrieres\.ansam\.ch/jobs/\d+[^"\'>\s]*', html)))
    results = []
    for url in job_urls:
        html2 = fetch(url)  # JSON-LD présent sur chaque page individuelle
        for ld in extract_jsonld_jobposting(html2):
            results.append(from_jsonld(ld, "ansam"))
        time.sleep(0.3)
    return results
```

### 4. Ordre d'exécution recommandé (Phase 3)

1. Swisscom Workday POST (14+ termes) → enrichissement HTML descriptions
2. ANSAM Teamtailor (listing + follow)
3. CIGES WordPress (listing jobs si disponible)
4. Admin fédéral OHWS → skip si vide (ne pas insister)
5. Autres Workday employeurs cibles (pattern identique à Swisscom)
6. Tout le reste → 1 tentative curl, si vide → skip, noter "non scrapé (SPA/JS)"

---

## Faux positifs fréquents dans le scoring ITSM

Termes qui matchent trop large sans être pertinents pour un profil IT Ops :
- "developpeur full stack" (snippet contient "système")
- "ingenieur SAP" (snippet contient "support")  
- DevOps engineer (snippet contient "operations")

Solution : mettre ces titres dans `exclude_terms` avec pénalité sur le TITRE uniquement (pas le snippet).
```python
for kw in profile["exclude_terms"]:
    if norm(kw) in title:   # titre seulement — pas le snippet
        score -= 8
```
