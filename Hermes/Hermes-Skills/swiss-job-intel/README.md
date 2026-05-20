# swiss-job-intel

**Skill Hermes — Veille emploi Suisse pour tout profil candidat.**

Scrape les principales plateformes d'emploi suisses, enrichit les termes candidat via la taxonomie ESCO/ISCO, score chaque offre par rapport au profil, et exporte les résultats classés en CSV + Markdown — avec un coût LLM nul après l'étape de profilage initial.

---

## Qu'est-ce qu'un skill Hermes ?

[Hermes](https://github.com/NousResearch/hermes-agent) est un framework d'agent LLM qui invoque des skills structurés depuis un fichier d'instructions `SKILL.md`. Chaque skill définit des phases exécutées dans l'ordre : lecture des entrées, exécution de scripts autonomes, présentation des résultats.

Ce skill est invoqué en plaçant `SKILL.md` dans le répertoire des skills de l'agent. L'agent lit le fichier, profile le candidat une seule fois, puis passe entièrement la main au pipeline Python.

```
L'utilisateur fournit cv.md + bilan.md
        ↓
L'agent Hermes lit SKILL.md → profile le candidat → écrit profile_cache.json
        ↓
Le pipeline Python s'exécute de façon autonome (0 token LLM) :
  enrich_profile_esco.py → scrape_ch_jobs.py → score_export.py
        ↓
L'agent lit done.flag + summary.json → présente les résultats à l'utilisateur
```

---

## Architecture

```
┌─ Agent Hermes (LLM) ────────────────────────┐   ┌─ Pipeline Python (0 token) ────────────────┐
│                                              │   │                                            │
│  Phase 0  — détection d'état (flag / cache) │   │  orchestrate.py profile_cache.json         │
│  Phase 1  — lecture cv.md + bilan.md        │   │    1. enrich_profile_esco.py               │
│  Phase 2  — construction profile{} + cache  │   │    2. scrape_ch_jobs.py                    │
│  Phase 3  — lancement pipeline  ───────────►│   │    3. score_export.py                      │
│  Phase 5  — présentation résultats  ◄───────│   │    → results/done.flag                    │
│             (done.flag + summary.json)       │   │    → results/JJ-MM-AAAA_output.csv         │
└──────────────────────────────────────────────┘   │    → results/JJ-MM-AAAA_output.md          │
                                                   │    → results/JJ-MM-AAAA_summary.json       │
                                                   └────────────────────────────────────────────┘
```

**Modèle de coût :** le LLM lit `cv.md` et `bilan.md` exactement une fois. Tous les runs suivants (même candidat, nouvelle recherche) sautent directement à la Phase 3 via `profile_cache.json`. La présentation des résultats coûte ~300 tokens (`done.flag` + `summary.json`).

---

## Installation

Copier le skill dans le répertoire des skills Hermes :

```bash
tar -xzf swiss-job-intel-v1.tar.gz -C ~/.hermes/skills/swiss-job-intel/
```

Puis invoquer le skill depuis une session agent Hermes.

---

## Ce que définit SKILL.md

`SKILL.md` est le jeu d'instructions de l'agent. Il spécifie :

- **Phase 0** — détection d'état : `done.flag` présent → aller aux résultats ; `profile_cache.json` présent → lancer le pipeline ; rien → onboarder le candidat
- **Phase 1** — lecture de `cv.md`, `bilan.md`, URL portfolio optionnelle
- **Phase 2** — profilage candidat : synthèse stratégique + dict `profile{}` + enrichissement ESCO
- **Phase 3** — lancement du pipeline via `orchestrate.py` (autonome, 0 token)
- **Phase 5** — présentation des résultats depuis `summary.json`

L'agent **ne lit jamais les données brutes** (`jobs_raw.json`, CSV complet). Seul `summary.json` (~200 tokens) atteint la conversation.

---

## Pipeline Python (backend autonome)

### Scripts

| Script | Rôle |
|--------|------|
| `orchestrate.py` | Point d'entrée — exécute le pipeline complet de bout en bout |
| `enrich_profile_esco.py` | Étend les termes candidat via la taxonomie ESCO/ISCO |
| `scrape_ch_jobs.py` | Scrape toutes les sources suisses actives |
| `score_export.py` | Score les offres + exporte CSV / Markdown / JSON |
| `manual_search_plan.py` | Génère un plan de recherche manuelle si les résultats automatiques sont insuffisants |
| `build_taxonomy_db.py` | Compilation unique de `source/taxonomy_db.json` depuis les CSV ESCO bruts |

### Exécution manuelle (hors Hermes)

```bash
# Pipeline complet
python3 scripts/orchestrate.py profile_cache.json --out results/

# Forcer un nouveau scraping (même profil)
python3 scripts/orchestrate.py profile_cache.json --force-refresh

# Régénérer le profil (CV modifié)
python3 scripts/orchestrate.py profile_cache.json --force-profile
```

> **Note WSL :** toujours exécuter via un terminal natif. Les sandboxes d'exécution de code (kernels Jupyter, certains IDE) bloquent le réseau sortant sous WSL.

---

## Sources de données

### Sources actives (mai 2026)

| Source | Connecteur | Notes |
|--------|-----------|-------|
| [Jobup.ch](https://www.jobup.ch) | `html_jsonld` | Listing → UUID → détail JSON-LD |
| [Jobs.ch](https://www.jobs.ch) | `html_jsonld` | Endpoint DE → UUID → détail JSON-LD |
| [SuisseTalent.ch](https://www.suissetalent.ch) | `html_jsonld_inline` | JSON-LD inline dans le listing |
| [Admin fédérale (OHWS)](https://www.stelle.admin.ch) | `json_api` | Intermittent |

> La sélection des sources est purement technique — le domaine candidat ne filtre jamais les sources. Une école technique peut publier des postes RH ; un hôpital recrute des ingénieurs. La pertinence est gérée au niveau du scoring individuel de chaque offre.

---

## Limites du scraping

**Pages rendues par JavaScript :** La plupart des pages carrières institutionnelles suisses (gouvernements cantonaux, hôpitaux, universités) utilisent des frameworks JS côté client. Le scraping HTTP standard retourne une coquille vide. Le support navigateur headless (Playwright/Selenium) n'est pas encore implémenté.

**Protection Cloudflare / anti-bot :** Les sites avec protection active sont ignorés automatiquement.

**Erreurs TLS :** Certains sous-domaines ne disposent pas de certificats SSL valides. `urllib` de Python échoue lors de la négociation TLS ; aucun contournement sans proxy.

**Volume :** Les profils de niche (archivistique, bibliothéconomie, métiers spécialisés) peuvent retourner moins de 15 offres pertinentes automatiquement. Un plan de recherche manuelle est généré si les résultats sont en dessous du seuil.

---

## Scoring

Chaque offre est scorée par rapport au profil candidat — aucun mot-clé hardcodé.

| Signal | Titre | Snippet |
|--------|-------|---------|
| Titre recommandé (exact) | +6 | — |
| Rôle cible | +4 | — |
| Termes primaires | +5 | +2 |
| Hard skills | +3 | +2 |
| Soft skills spécifiques (cap +3) | +1 | — |
| Localisation préférée | +3 | — |
| Récence (≤7j / ≤14j / ≤30j) | +3 / +2 / +1 | — |
| Terme exclu dans le titre | −8 | — |
| Aucun terme primaire nulle part | −5 | — |

Les soft skills génériques (autonomie, rigueur, esprit d'équipe…) sont ignorées pour éviter les faux positifs boilerplate.

**Tiers :** A ≥ 20 · B 12–19 · C 6–11 · rejeté < 6

---

## Enrichissement ESCO / ISCO

Les termes candidat sont étendus de ~16 à ~175 grâce à :

- **[ESCO v1.2.1](https://esco.ec.europa.eu/fr/use-esco/download)** (Commission européenne, CC BY 4.0) — plus de 36 000 intitulés de postes suisses et synonymes professionnels
- **[CH-ISCO-19](https://www.bfs.admin.ch/bfs/en/home.assetdetail.23530849.html)** (OFS/BFS) — classification professionnelle suisse

La base de données compilée (`source/taxonomy_db.json`) couvre 484 groupes ISCO et plus de 12 000 synonymes, construite une seule fois depuis les CSV bruts via `scripts/build_taxonomy_db.py`.

---

## Fichiers de sortie

| Fichier | Description |
|---------|-------------|
| `results/JJ-MM-AAAA_output.csv` | Liste classée complète — UTF-8 BOM, compatible Excel |
| `results/JJ-MM-AAAA_output.md` | Rapport Markdown lisible (Tier A/B/C) |
| `results/JJ-MM-AAAA_summary.json` | JSON compact pour la Phase 5 agent (~200 tokens) |
| `results/done.flag` | Sentinelle de fin de pipeline (lue par la Phase 0 Hermes) |

Colonnes CSV : `date_export · tier · score · titre · employeur · localisation · source · url · date_offre · mots_cles_matches · gaps`

---

## Tests

```bash
python3 tests/test_pipeline.py
# 121 ✅  0 ❌  (121 tests)
```

Couvre l'enrichissement ESCO, le scoring, le registre des sources, les variantes d'extraction d'URL, la détection de faux positifs multi-profils, la récence (Workday + ISO 8601), le contrat pipeline et la logique du plan de recherche manuelle.

---

## Lacunes connues

| Lacune | Piste d'amélioration |
|--------|---------------------|
| Pas de navigateur headless | Connecteur Playwright pour les sources `js_dynamic` |
| Biais langue française dans le scoring | Normalisation multilingue |
| Pas de planification | Intégration Cron / GitHub Actions |

---

## Avis légal

Requêtes HTTP en lecture seule vers des pages d'offres d'emploi accessibles publiquement. Ne contourne aucune authentification ni protection anti-bot. Les sites protégés par Cloudflare sont ignorés automatiquement. Consulter les Conditions d'utilisation de chaque plateforme avant tout usage commercial.

---

## Crédits

- [ESCO v1.2.1](https://esco.ec.europa.eu/fr/use-esco/download) — Commission européenne (CC BY 4.0)
- [CH-ISCO-19](https://www.bfs.admin.ch/bfs/en/home.assetdetail.23530849.html) — OFS/BFS
- Données d'offres collectées en temps réel depuis Jobup.ch, Jobs.ch, SuisseTalent.ch, stelle.admin.ch

---

## Licence

MIT — voir [LICENSE](LICENSE).

`source/taxonomy_db.json` est dérivé d'ESCO v1.2.1 (CC BY 4.0) et CH-ISCO-19 (OFS/BFS). Attribution requise pour toute redistribution.
