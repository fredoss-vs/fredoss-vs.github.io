# swiss-job-intel

**Hermes skill — Swiss job market intelligence for any candidate profile.**

Scrapes active Swiss job boards, enriches candidate terms with ESCO/ISCO taxonomy, scores every offer against the candidate profile, and exports ranked results as CSV + Markdown — with zero LLM token cost after the initial profiling step.

---

## What is a Hermes skill?

[Hermes](https://github.com/your-org/hermes-agent) is an LLM agent framework that invokes structured skills from a `SKILL.md` instruction file. Each skill defines phases the agent executes in order: reading inputs, running autonomous scripts, and presenting results.

This skill is invoked by placing `SKILL.md` in the agent's skill directory. The agent reads it, profiles the candidate once, then hands off entirely to the Python pipeline.

```
User provides cv.md + bilan.md
        ↓
Hermes agent reads SKILL.md → profiles candidate → writes profile_cache.json
        ↓
Python pipeline runs autonomously (0 LLM tokens):
  enrich_profile_esco.py → scrape_ch_jobs.py → score_export.py
        ↓
Agent reads done.flag + summary.json → presents results to user
```

---

## Architecture

```
┌─ Hermes Agent (LLM) ────────────────────────┐   ┌─ Python Pipeline (0 tokens) ───────────────┐
│                                              │   │                                            │
│  Phase 0  — detect state (flag / cache)      │   │  orchestrate.py profile_cache.json         │
│  Phase 1  — read cv.md + bilan.md            │   │    1. enrich_profile_esco.py               │
│  Phase 2  — build profile{} + cache          │   │    2. scrape_ch_jobs.py                    │
│  Phase 3  — launch pipeline  ───────────────►│   │    3. score_export.py                      │
│  Phase 5  — present results  ◄───────────────│   │    → results/done.flag                    │
│             (done.flag + summary.json)        │   │    → results/DD-MM-YYYY_output.csv         │
└──────────────────────────────────────────────┘   │    → results/DD-MM-YYYY_output.md          │
                                                   │    → results/DD-MM-YYYY_summary.json       │
                                                   └────────────────────────────────────────────┘
```

**Cost model:** the LLM reads `cv.md` and `bilan.md` exactly once. All subsequent runs (same candidate, new search) skip directly to Phase 3 via `profile_cache.json`. Presenting results costs ~300 tokens (`done.flag` + `summary.json`).

---

## Installation

Copy the skill into your Hermes skills directory:

```bash
tar -xzf swiss-job-intel-v1.tar.gz -C ~/.hermes/skills/swiss-job-intel/
```

Then invoke the skill from your Hermes agent session.

---

## What SKILL.md defines

`SKILL.md` is the agent instruction set. It specifies:

- **Phase 0** — state detection: `done.flag` present → skip to results; `profile_cache.json` present → skip to pipeline; nothing → onboard candidate
- **Phase 1** — reading `cv.md`, `bilan.md`, optional portfolio URL
- **Phase 2** — candidate profiling: strategic synthesis + `profile{}` dict + ESCO enrichment
- **Phase 3** — pipeline launch via `orchestrate.py` (autonomous, 0 tokens)
- **Phase 5** — results presentation from `summary.json`

The agent **never reads raw job data** (`jobs_raw.json`, full CSV). Only `summary.json` (~200 tokens) reaches the conversation.

---

## Python pipeline (autonomous backend)

### Scripts

| Script | Role |
|--------|------|
| `orchestrate.py` | Entry point — runs the full pipeline end to end |
| `enrich_profile_esco.py` | Expands candidate terms via ESCO/ISCO taxonomy |
| `scrape_ch_jobs.py` | Scrapes all active Swiss sources |
| `score_export.py` | Scores offers + exports CSV / Markdown / JSON |
| `manual_search_plan.py` | Generates a manual search plan when automatic results are insufficient |
| `build_taxonomy_db.py` | One-time compilation of `source/taxonomy_db.json` from raw ESCO CSVs |

### Running manually (outside Hermes)

```bash
# Full pipeline
python3 scripts/orchestrate.py profile_cache.json --out results/

# Force re-scrape (same profile)
python3 scripts/orchestrate.py profile_cache.json --force-refresh

# Regenerate profile (CV changed)
python3 scripts/orchestrate.py profile_cache.json --force-profile
```

> **WSL note:** always run via a native terminal. Code execution sandboxes (Jupyter kernels, some IDE runners) block outbound network on WSL.

---

## Data sources

### Active sources (as of May 2026)

| Source | Connector | Notes |
|--------|-----------|-------|
| [Jobup.ch](https://www.jobup.ch) | `html_jsonld` | Listing → UUID → JSON-LD detail |
| [Jobs.ch](https://www.jobs.ch) | `html_jsonld` | DE endpoint → UUID → JSON-LD detail |
| [SuisseTalent.ch](https://www.suissetalent.ch) | `html_jsonld_inline` | JSON-LD inline in listing |
| [Swisscom](https://careers.swisscom.ch) | `workday_api` | Workday JSON API |
| [ANSAM](https://www.ansam.ch) | `teamtailor_jsonld` | JSON-LD per job page |
| [Admin fédérale (OHWS)](https://www.stelle.admin.ch) | `json_api` | Intermittently empty |
| [CIGES](https://www.ciges.net) | `wordpress_jsonld` | Low volume |

> Source selection is purely technical — the candidate's domain never filters sources. An IT school may post janitorial positions; a hospital recruits engineers. Offer-level scoring handles relevance.

### Inaccessible sources

| Source | Status | Reason |
|--------|--------|--------|
| Hôpital du Valais | `js_dynamic` | ServiceNow — client-side rendering |
| État du Valais | `js_dynamic` | Liferay + React |
| État de Vaud | `js_dynamic` | JS-rendered, WSL connection refused |
| HES-SO | `js_dynamic` | 403 on career page |
| EPFL | `js_dynamic` | WordPress JS — HTML shell only |
| Romandie.com | `tls_error` | TLS SNI rejection |
| CHUV | `blocked_cloudflare` | Cloudflare Turnstile |
| Jobup / Jobs.ch SPA | `spa_no_api` | React/Next.js SPA, no public API |

---

## Scraping limitations

**JavaScript-rendered pages:** Most Swiss institutional career pages (cantonal governments, hospitals, universities) use client-side JS frameworks. Standard HTTP scraping returns an empty shell. Headless browser support (Playwright/Selenium) is not yet implemented.

**Cloudflare / bot protection:** Sites with active bot protection are skipped automatically.

**TLS errors:** Some subdomains lack valid SSL certificates. Python's `urllib` fails the handshake; no workaround without a proxy.

**Volume:** A full run collects 150–220 unique offers across 7 sources. Niche profiles (archiving, library science, specialized trades) may return fewer than 15 relevant offers automatically. A manual search plan is generated when results fall below threshold.

**Sequential scraping:** Sources run sequentially. A full run with 175 enriched terms takes approximately 4–5 minutes.

---

## Scoring

Each offer is scored against the candidate profile — no hardcoded keywords.

| Signal | Title | Snippet |
|--------|-------|---------|
| Recommended title (exact) | +6 | — |
| Target role | +4 | — |
| Primary terms | +5 | +2 |
| Hard skills | +3 | +2 |
| Specific soft skills (cap +3) | +1 | — |
| Preferred location | +3 | — |
| Recency (≤7d / ≤14d / ≤30d) | +3 / +2 / +1 | — |
| Exclude term in title | −8 | — |
| No primary term anywhere | −5 | — |

Generic soft skills (autonomie, rigueur, esprit d'équipe…) are ignored to prevent boilerplate false positives.

**Tiers:** A ≥ 20 · B 12–19 · C 6–11 · rejected < 6

---

## ESCO / ISCO enrichment

Candidate terms are expanded from ~16 to ~175 using:

- **[ESCO v1.2.1](https://esco.ec.europa.eu/fr/use-esco/download)** (European Commission, CC BY 4.0) — 36,000+ Swiss job titles and occupational synonyms
- **[CH-ISCO-19](https://www.bfs.admin.ch/bfs/en/home.assetdetail.23530849.html)** (OFS/BFS) — Swiss occupational classification

The compiled database (`source/taxonomy_db.json`) covers 484 ISCO groups and 12,000+ synonyms, built once from raw CSVs via `scripts/build_taxonomy_db.py`.

---

## Output files

| File | Description |
|------|-------------|
| `results/DD-MM-YYYY_output.csv` | Full ranked list — UTF-8 BOM, Excel-compatible |
| `results/DD-MM-YYYY_output.md` | Human-readable Markdown report (Tier A/B/C) |
| `results/DD-MM-YYYY_summary.json` | Compact JSON for agent Phase 5 (~200 tokens) |
| `results/done.flag` | Pipeline completion sentinel (read by Hermes Phase 0) |

CSV columns: `date_export · tier · score · titre · employeur · localisation · source · url · date_offre · mots_cles_matches · gaps`

---

## Tests

```bash
python3 tests/test_pipeline.py
# 121 ✅  0 ❌  (121 tests)
```

Covers ESCO enrichment, scoring, source registry, URL extraction variants, multi-profile false positive detection, recency (Workday + ISO 8601), pipeline contract, and manual search plan logic.

---

## Known gaps

| Gap | Path forward |
|-----|-------------|
| No headless browser | Playwright connector for js_dynamic sources |
| Sequential scraping | asyncio / threading |
| Single Workday tenant (Swisscom) | One connector per tenant |
| French-language bias in scoring | Language-aware normalization |
| No scheduling | Cron / GitHub Actions integration |

---

## Legal notice

Read-only HTTP requests to publicly accessible job listing pages. Does not bypass authentication or bot protection. Cloudflare-protected sites are skipped automatically. Review each platform's Terms of Service before use in a commercial context.

---

## Credits

- [ESCO v1.2.1](https://esco.ec.europa.eu/fr/use-esco/download) — European Commission (CC BY 4.0)
- [CH-ISCO-19](https://www.bfs.admin.ch/bfs/en/home.assetdetail.23530849.html) — OFS/BFS
- Job data fetched in real time from Jobup.ch, Jobs.ch, SuisseTalent.ch, Swisscom, ANSAM, CIGES, stelle.admin.ch

---

## License

MIT — see [LICENSE](LICENSE).

`source/taxonomy_db.json` is derived from ESCO v1.2.1 (CC BY 4.0) and CH-ISCO-19 (OFS/BFS). Attribution required for redistribution.
