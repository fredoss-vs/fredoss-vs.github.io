---
name: swiss-job-intel
description: Candidate profiling from cv.md / bilan.md / portfolio, keyword extraction, Swiss job market search, scoring, and dual export CSV + Markdown.
version: 6.0.0
author: fredoss-vs
license: MIT
platforms: [linux, macos, wsl]
prerequisites:
  commands: [python3]
  env_vars: []
metadata:
  hermes:
    tags: [Jobs, Switzerland, CV, Matching, CSV, Career, Intelligence]
  taxonomies:
    esco:
      label: "ESCO v1.2.1 — European Skills, Competences, Qualifications and Occupations (FR)"
      url: "https://esco.ec.europa.eu/fr/use-esco/download"
    ch_isco:
      label: "CH-ISCO-19 — Classification suisse des professions (BFS/OFS)"
      url: "https://www.bfs.admin.ch/bfs/en/home.assetdetail.23530849.html"
---

# Swiss Job Market Intelligence

Skill universel pour **tout candidat sur le marché suisse** — IT, santé, agriculture, construction, sciences, social, artisanat, finance, formation, et tout autre domaine.

`cv.md`, `bilan.md` et le portfolio web servent à inférer le domaine, le niveau, le positionnement et les mots-clés **sans hypothèse préalable sur le métier**. Les données du candidat actuel sont un cas de test — pas une spécialisation du skill.

**Support files :**
- `references/job_site_technologies_ch.md` — tableau complet des sources suisses, statut vérifié mai 2026, patterns de code validés, faux positifs fréquents dans le scoring.
- `scripts/scrape_ch_jobs.py` — scraping multi-sources : Swisscom Workday · ANSAM · Admin fédéral · CIGES · Jobup.ch · Jobs.ch · SuisseTalent. Lancer via `terminal()`, jamais via `execute_code`.

```
┌─ AGENT (LLM) ──────────────────────────────┐  ┌─ PYTHON AUTONOME (0 token) ──────────────┐
│                                             │  │                                          │
│  cv.md + bilan.md + [URL]  (1 seule fois)  │  │  orchestrate.py profile_cache.json       │
│          ↓                                 │  │    → enrich ESCO/ISCO                    │
│  Analyse candidat → profile{}              │  │    → scraping sources suisses            │
│          ↓                                 │  │    → scoring + export CSV + MD           │
│  profile_cache.json  ──────────────────────┼─►│    → results/done.flag  ◄────────────┐  │
│                                             │  │                                       │  │
└─────────────────────────────────────────────┘  └───────────────────────────────────────┼─┘
                                                                                          │
┌─ AGENT (LLM) ──────────────────────────────┐                                           │
│  Lit done.flag + MD summary  ◄─────────────┼───────────────────────────────────────────┘
│  → présentation résultats                  │
└─────────────────────────────────────────────┘
```

---

## Phase 0 — Détection d'état (TOUJOURS en premier — règle absolue)

> **RÈGLE COÛT ABSOLUE :**
> `cv.md`, `bilan.md` et le site web ne sont lus **qu'une seule fois dans la vie du projet**.
> Le LLM intervient uniquement là où il est irremplaçable : **comprendre le candidat**.
> Tout le reste (scraping, scoring, tri) est délégué au script Python autonome.

```python
import json, os
from pathlib import Path

cwd        = Path.cwd()
flag_path  = cwd / "results" / "done.flag"
cache_path = cwd / "profile_cache.json"

flag_exists  = flag_path.exists()
cache_exists = cache_path.exists()
```

### État 1 — `results/done.flag` présent → résultats prêts (→ Phase 5)

```python
if flag_exists:
    with open(flag_path) as f:
        flag = json.load(f)
    print(f"✅ Pipeline terminé le {flag['timestamp']}")
    print(f"   Candidat : {flag['candidate']} | domaine : {flag['domain']}")
    print(f"   {flag['offers_collected']} offres | durée : {flag['pipeline_seconds']}s")
    print(f"   Résultats : {flag['out_dir']}/{flag['md']}")
    # → ALLER DIRECTEMENT EN PHASE 5 (présentation résultats)
    # → Ne pas lire cv.md / bilan.md / le site web
    # → Ne pas relancer le pipeline
```

### État 2 — `profile_cache.json` présent, pas de flag → lancer le pipeline (→ Phase 3)

```python
elif cache_exists:
    with open(cache_path) as f:
        profile = json.load(f)
    m = profile.get("_meta", {})
    print(f"✅ Profil en cache : {m.get('name','?')} — {m.get('recommended_title','?')}")
    print(f"   {len(profile.get('primary_terms',[]))} termes · domaine : {profile.get('domain','?')}")
    # → ALLER DIRECTEMENT EN PHASE 3 (lancer orchestrate.py)
    # → Ne pas lire cv.md / bilan.md / le site web
```

### État 3 — Rien → première analyse (→ Phase 0.5 onboarding)

```python
else:
    pass  # → continuer en Phase 0.5 : demander cv.md / bilan.md / site web
```

| État | Fichiers présents | Action |
|------|------------------|--------|
| **1** | `results/done.flag` ✅ | → Phase 5 — présenter les résultats |
| **2** | `profile_cache.json` ✅, pas de flag | → Phase 3 — lancer le pipeline Python |
| **3** | Rien | → Phase 0.5 — onboarding candidat |

> **Remettre à zéro** le pipeline (nouvelle recherche) : supprimer `results/done.flag`.  
> **Régénérer le profil** (CV mis à jour) : supprimer `profile_cache.json` + `results/done.flag`.

---

## Phase 0.5 — Onboarding candidat (État 3 uniquement)

1. Présenter le skill en 2 phrases.
2. Demander :
   - **CV** : chemin vers `cv.md` ou coller le contenu
   - **Bilan** : chemin vers `bilan.md` (optionnel mais recommandé)
   - **Portfolio** : URL site web / GitHub / LinkedIn (optionnel)
3. Attendre les réponses avant de continuer.
4. Si `bilan.md` manque → continuer avec le CV seul, noter précision réduite.

---

## Phase 1 — Lecture des sources

| Fichier | Ce qu'on en extrait |
|---------|---------------------|
| `cv.md` | Titres de postes, compétences techniques, outils, langues, certifications, niveau d'études, années d'expérience, secteurs |
| `bilan.md` | Soft skills, préférences d'environnement, direction carrière, contraintes géo, type contrat, fourchette salariale |

### Portfolio (optionnel)
Fetch HTML statique via urllib (pas curl — voir pitfalls réseau). Si HTML < 200 chars → INACCESSIBLE. Extraire le texte brut (strip scripts/styles/tags), limiter à 4000 chars.

---

## Phase 2 — Synthèse profil + dict profile{}

### 2A — Synthèse stratégique (format compact — max 150 tokens output)

```
PROFIL   | {niveau}  ·  {titre ATS recommandé}
VALEUR   | {différenciateur en 1 phrase — ce qui est rare sur le marché suisse}
FORCES   | {2-3 atouts marché, ex: "infirmier senior · trilingue · secteur public"}
RISQUES  | {1-2 blocages potentiels de candidature}
POSTES   | Maintenant: {Titre exact} ({fourchette CHF}) / 1-3 ans: {Titre} ({fourchette})
AXES     | 1. {action prioritaire}  2. {action secondaire}
TITRE CV | {titre ATS exact à inscrire sur le CV}
```

**Règle :** max 150 tokens output. Si le candidat se positionne en dessous de son niveau réel, le signaler dans VALEUR. Ne pas développer davantage — tout le détail ira dans la lettre de motivation, pas ici.

### 2B — Dict profile{}

```python
profile = {
    "name":                "",
    "level":               "",   # "junior" | "mid" | "senior" | "expert"

    # ── Domaine et codes ISCO ─────────────────────────────────────────────────
    # domain : string unique — "it" | "sante" | "agriculture" | "construction" | "science" |
    #          "finance" | "formation" | "social" | "artisanat" | "administration" | "autre"
    # Profil hybride : choisir le domaine PRINCIPAL. Les sources multi_domain et generalist
    # sont toujours incluses ; le scoring offre gère la diversité métier.
    # (Support liste multi-domaines : P2 — non implémenté)
    "domain":              "",
    "isco_major_group":    "",   # 1 chiffre ISCO-08 :
                                 # 1=cadres 2=professionnels 3=techniciens 4=employés
                                 # 5=services 6=agriculture 7=artisans 8=opérateurs 9=élémentaires
    "isco_codes":          [],   # 4 chiffres si identifiables — laisser [] si incertain

    # ── Titre et positionnement ───────────────────────────────────────────────
    "recommended_title":   "",   # titre ATS pour le marché suisse

    # ── Rôles cibles (optionnel) ──────────────────────────────────────────────
    "target_roles":        [],   # postes spécifiques visés, ex: ["chef de projet", "product owner"]

    # ── Localisation et conditions ────────────────────────────────────────────
    "preferred_locations": [],   # villes ou cantons, lowercase
    "contract":            "",   # "CDI" | "CDD" | "interim" | "independant" | "apprentissage"
    "remote_policy":       "",   # "on-site" | "hybrid" | "remote" | ""
    "availability":        "",   # "immediate" | "1 mois" | "3 mois" | date ISO | ""
    "salary_range_chf":    [],   # [min, max] annuel brut CHF, ex: [80000, 110000] — [] si inconnu
    "languages":           [],

    # ── Niveau de formation ───────────────────────────────────────────────────
    "education_level":     "",   # "cfc" | "maturite" | "bachelor" | "master" | "phd" | ""

    # ── Compétences ───────────────────────────────────────────────────────────
    "hard_skills":         [],
    "soft_skills":         [],

    # ── Termes de recherche — cœur du matching ────────────────────────────────
    # Dérivés du positionnement de 2A, PAS des titres actuels du CV.
    # Exemples multi-domaines :
    #   infirmier    → ["soins infirmiers", "soins intensifs", "HES-S2", "CFC soins"]
    #   maçon        → ["maçonnerie", "gros œuvre", "chantier", "béton armé"]
    #   viticulteur  → ["viticulture", "vigne", "cave", "arboriculteur", "vendanges"]
    #   data analyst → ["data analysis", "sql", "power bi", "reporting", "tableau"]
    "primary_terms":       [],   # 8-20 termes reflétant la VRAIE valeur marché du candidat

    "exclude_terms":       [],   # faux positifs — pénalité sur TITRE uniquement
}
```

**Quality check avant de continuer :**
- `domain` cohérent avec le CV — choisir le domaine principal si profil hybride
- `primary_terms` reflète le positionnement de 2A, pas l'intitulé actuel du CV
- `isco_codes` : ne pas halluciner — laisser `[]` si incertain
- `salary_range_chf` : laisser `[]` si non mentionné dans les documents
- Si le candidat se sous-vend, `primary_terms` reflète ce qu'il DEVRAIT cibler

### 2C — Sérialisation du cache profil

Après validation du profil, écrire dans le répertoire de travail courant :

```python
import json, datetime, hashlib, os

def _src_hash(path):
    try: return hashlib.md5(open(path,"rb").read()).hexdigest()[:12]
    except: return ""

profile_cache = dict(profile)
profile_cache["_meta"] = {
    "name":              profile.get("name", ""),
    "recommended_title": profile.get("recommended_title", ""),
    "generated":         datetime.date.today().isoformat(),
    "skill_version":     "6.0.0",
    # Signature des documents source — orchestrate.py avertit si cv.md/bilan.md ont changé
    "source_hash":       _src_hash("cv.md") + "+" + _src_hash("bilan.md"),
}
with open("profile_cache.json", "w", encoding="utf-8") as f:
    json.dump(profile_cache, f, ensure_ascii=False, indent=2)
print("✅ profile_cache.json sauvegardé — Phase 1+2 ignorées au prochain run.")
```

> Régénérer : supprimer `profile_cache.json` et relancer le skill.

### 2D — Enrichissement ESCO/ISCO (optionnel — améliore la qualité du matching)

Le script utilise **deux stratégies par ordre de priorité** :

1. **`source/taxonomy_db.json`** (couverture totale — 484 groupes ISCO, 36 K métiers CH, 12 K synonymes ESCO)  
   → lookup instantané, **aucune dépendance externe**  
   → construire une fois : `python3 {SKILL_DIR}/scripts/build_taxonomy_db.py`  
   → sources requises : CH-ISCO-19 xlsx + ESCO v1.2.1 CSVs (voir entête du script)

2. **`source/taxonomies/*.yaml`** (fallback partiel — IT, santé, social, bâtiment, agriculture)  
   → utilisé si `taxonomy_db.json` absent  
   → requiert PyYAML : `pip install pyyaml`

```bash
python3 {SKILL_DIR}/scripts/enrich_profile_esco.py profile_cache.json
# → stratégie 1 si taxonomy_db.json présent, sinon stratégie 2
# → détecte le domaine depuis profile_cache.json (champ "domain" + "isco_codes")
# → étend primary_terms : titres officiels CH-ISCO + synonymes ESCO + compétences essentielles
# → plafond : 200 nouveaux termes max (top groupes ISCO par score)
# → écrit /tmp/profile_enriched.json
```

Afficher uniquement les lignes `+ terme ajouté` — pas le contenu de /tmp/profile_enriched.json.

---

## Phase 3 — Lancement pipeline Python (0 token LLM)

> **Le LLM ne touche pas aux résultats bruts. Il lance le script et attend le sentinel.**

**Règle absolue réseau (WSL / Hermes) :**
- `execute_code` BLOQUE le réseau → toujours via `terminal()`

```bash
python3 {SKILL_DIR}/scripts/orchestrate.py profile_cache.json
# Sortie dans ./results/ (créé automatiquement)
# Le script écrit results/done.flag à la fin — signal que les résultats sont prêts
```

Le script est **totalement autonome** :
- Enrich ESCO/ISCO (taxonomy_db.json)
- Sélection des sources selon disponibilité technique (sources_registry.yaml)
- Scraping séquentiel multi-sources via `scrape_ch_jobs.py` → `/tmp/jobs_raw.json`
- Scoring + export → `results/DD-MM-YYYY_output.csv` + `results/DD-MM-YYYY_output.md`
- Écriture de `results/done.flag`

> Scraping parallèle (P2) : non encore implémenté — chaque source tourne séquentiellement.

**Lire uniquement les dernières lignes de log** (résumé terminal) — **jamais** le contenu de `jobs_raw.json` ni du CSV.

Une fois le terminal rendu → `results/done.flag` existe → **aller directement en Phase 5**.

### Modèle de sources (mai 2026)

> **Principe fondamental : l'employeur ne définit jamais le métier publié.**  
> CIGES (école IT) peut publier un poste de concierge. L'Hôpital du Valais publie des postes IT, RH, cuisine, logistique. EPFL recrute des électriciens et des secrétaires.  
> **La collecte est large. Le tri est précis — au niveau de chaque offre, jamais à la source.**

Une source est incluse si et seulement si elle est **techniquement scrapable** (statut actif). Le domaine du candidat n'intervient pas dans la sélection.

| Statut | Sélectionnée | Raison |
|--------|-------------|--------|
| `active` / `active_sparse` | ✅ oui | Connecteur fonctionnel |
| `needs_connector` | ⛔ non | Accessible mais connecteur pas encore écrit |
| `js_dynamic` | ⛔ non | Données chargées côté client (SPA, Liferay, ServiceNow, WordPress JS) |
| `tls_error` | ⛔ non | Erreur TLS/SSL lors du handshake — inaccessible réseau |
| `blocked_cloudflare` | ⛔ non | Cloudflare Turnstile — inaccessible automatiquement |
| `spa_no_api` / `spa_manual` | ⛔ non | SPA sans API publique — ouverture manuelle uniquement |

**Sources actives (mai 2026) — 7 sources :**

| Source | Connecteur | Notes |
|--------|-----------|-------|
| Admin fédéral ⚠️ | json_api | Souvent vide |
| Swisscom | workday_api | 33+ offres typiques |
| ANSAM | teamtailor_jsonld | Agence insertion, tous niveaux |
| CIGES ⚠️ | wordpress_jsonld | École IT, peu d'offres |
| **Jobup.ch** | html_jsonld | Listing → UUID → JSON-LD détail |
| **Jobs.ch** | html_jsonld | Endpoint DE → UUID → JSON-LD détail |
| **SuisseTalent.ch** | html_jsonld_inline | JSON-LD directement dans listing |

**Sources inaccessibles automatiquement :**

| Source | Statut | Raison |
|--------|--------|--------|
| Hôpital du Valais | `js_dynamic` | ServiceNow — données client-side uniquement |
| État du Valais | `js_dynamic` | Liferay + React — HTML statique vide |
| État de Vaud | `js_dynamic` | Connexion refusée WSL / chargement JS |
| HES-SO | `js_dynamic` | Page carrières inaccessible (403) |
| EPFL | `js_dynamic` | WordPress JS — shell HTML uniquement |
| Romandie.com | `tls_error` | Erreur TLS SNI — inaccessible Python/curl |
| CHUV | `blocked_cloudflare` | Cloudflare Turnstile |
| Jobup manuel | `spa_no_api` | SPA React — plan recherche manuelle |
| Jobs.ch manuel | `spa_no_api` | SPA Next.js — plan recherche manuelle |

> ⚠️ = active_sparse (ne bloque pas le pipeline si vide)  
> `preferred_domains` = annotation documentaire uniquement, jamais une règle d'exclusion.  
> Voir `source/sources_registry.yaml` pour le détail complet.

---

## Phase 4 — Scoring (Python pur — 0 token LLM)

> **Cette phase est entièrement gérée par `score_export.py` — aucune intervention LLM.**  
> Seuils : Tier A ≥ 20 pts · Tier B 12–19 · Tier C 6–11 · Rejeté < 6.  
>  
> **Pondération :**  
> titre cible exact (recommended_title) `+6` · target_role dans titre `+4`  
> primary_terms dans titre `+5` / dans snippet `+2`  
> hard_skills dans titre `+3` / dans snippet `+2`  
> soft_skills spécifiques dans titre `+1` (cap `+3` · termes génériques ignorés · snippet : 0)  
> localisation préférée `+3` · récence `+1/+2/+3` (Workday + ISO 8601)  
> exclude_terms dans titre `−8` · aucun primary_term nulle part `−5`

---

## Phase 5 — Présentation résultats (Agent 2 — entrée via done.flag)

> **Tokens lus : done.flag (~100 tokens) + fichier MD (~1 500 tokens) = ~1 600 tokens total.**  
> Ne jamais lire le CSV brut ni `jobs_raw.json` dans la conversation.

```python
import json
from pathlib import Path

cwd         = Path.cwd()
flag_path   = cwd / "results" / "done.flag"

with open(flag_path) as f:
    flag = json.load(f)

# Lire summary.json (~200 tokens) — jamais le CSV ni le MD complet (~1500 tokens)
summary_path = Path(flag["out_dir"]) / flag.get("summary", flag["md"].replace("_output.md","_summary.json"))
if summary_path.exists():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
else:
    # fallback: lire le MD si summary.json absent (ancienne version)
    summary = {"_fallback_md": (Path(flag["out_dir"]) / flag["md"]).read_text(encoding="utf-8")}
```

**Format de présentation attendu :**

1. **En-tête** : `{candidate} · {domain} · {total} offres · pipeline {pipeline_seconds}s`
2. **Tier A** — tableau : titre · employeur · localisation · score · mots-clés matchés
3. **Tier B** — tableau compact (titre · employeur · score · URL)
4. **Tier C** — liste simple (titre + URL)
5. **Recommandations** : titre cible ATS + compétences absentes des Tier A/B + sources manuelles

> Ne lire ni le CSV ni le MD complet — `summary.json` contient tout le nécessaire.

**Cycle de vie candidat :**

| Situation | Action |
|-----------|--------|
| Relancer une recherche, même candidat | `python3 orchestrate.py profile_cache.json --force-refresh` |
| CV ou bilan modifiés | `python3 orchestrate.py profile_cache.json --force-profile` puis relancer le skill Hermes |
| Changer complètement de candidat | Supprimer `profile_cache.json` + `results/` puis relancer le skill Hermes |
| Voir les résultats existants | Relancer le skill Hermes (Phase 0 détecte done.flag → Phase 5) |

> `--force-profile` supprime `profile_cache.json` et quitte proprement.  
> La régénération du profil nécessite ensuite le LLM (skill Hermes Phase 0 → 2C).

---

## Contrat des fichiers produits (P1-6 — format stable v6.0.0)

| Fichier | Producteur | Consommateur | Format |
|---------|-----------|-------------|--------|
| `profile_cache.json` | LLM Phase 2C | orchestrate.py, score_export.py, scrape_ch_jobs.py | JSON — schéma Phase 2B |
| `/tmp/jobs_raw.json` | scrape_ch_jobs.py | score_export.py | JSON array `[{title,employer,location,url,date,snippet,source}]` |
| `results/DD-MM-YYYY_output.csv` | score_export.py | Excel / utilisateur | CSV utf-8-sig, colonnes fixes v6 |
| `results/DD-MM-YYYY_output.md` | score_export.py | Lecture humaine | Markdown Tier A/B/C + Recommandations |
| `results/DD-MM-YYYY_summary.json` | score_export.py | LLM Phase 5 | JSON compact ~200 tokens |
| `results/done.flag` | orchestrate.py | LLM Phase 0 (État 1) | JSON `{timestamp,candidate,domain,offers_collected,out_dir,csv,md,summary,pipeline_seconds}` |

**Colonnes CSV figées (ne pas modifier sans incrémenter la version) :**
`date_export · tier · score · titre · employeur · localisation · source · url · date_offre · mots_cles_matches · gaps`

**Champs done.flag figés :**
`timestamp · candidate · domain · offers_collected · out_dir · csv · md · summary · pipeline_seconds`

---

## Pitfalls

- **execute_code bloque le réseau (WSL)** : ne jamais utiliser `execute_code` pour des requêtes HTTP. Toujours écrire le script dans `/tmp/nom.py` et lancer via `terminal()`. Vérifier la connectivité avec `curl -s --max-time 5 https://httpbin.org/get | head -3` avant tout scraping.
- **pipe `curl | python3` via terminal** : déclenche une alerte sécurité HIGH (pipe to interpreter). L'utilisateur peut approuver, mais préférer un script Python autonome dans `/tmp/` pour éviter l'interruption.
- **Workday enrichissement — Accept header obligatoire** : fetch sans `Accept: text/html,...` renvoie une page vide. URL d'enrichissement = `/SwisscomExternalCareers/job/<City>/<Slug>` (pas `/job/<City>/<Slug>` seul).
- **from_jsonld — jobLocation peut être une liste** : Teamtailor et Workday retournent parfois une liste. Toujours faire `if isinstance(jloc, list): jloc = jloc[0]` avant `.get("address")`. Idem pour `hiringOrganization`.
- **Teamtailor (ANSAM)** : JSON-LD sur chaque PAGE JOB INDIVIDUELLE, PAS sur le listing. Pattern obligatoire : scraper URLs du listing → fetch chaque URL → JSON-LD.
- **Workday 403** : si le POST retourne 403, skip immédiatement — c'est une protection CSRF, ne pas retry.
- **Admin fédéral OHWS vide** : réponse vide depuis mai 2026. Skip sans bloquer.
- **exclude_terms sur titre seulement** : appliquer la pénalité `-8` uniquement sur le titre, pas le snippet. Les descriptions mentionnent beaucoup de faux positifs ("notre plateforme supporte les développeurs" → pénalise "développeur" à tort).
- **Accents** : toujours passer par `norm()` avant de comparer — "système" ≠ "systeme" sans normalisation NFD.
- **CSV encoding** : `utf-8-sig` (avec BOM) obligatoire — Excel Windows interprète mal `utf-8` sans BOM.
- **Doublons cross-source** : dédupliquer par URL avant de scorer.
- **Sites vides mai 2026** : ne pas re-tenter SUVA, BCV, BCVs, HUG, CHUV, Groupe E, Sword, JobCourier, publicjobs.ch, OIKEN avant 3 mois.
