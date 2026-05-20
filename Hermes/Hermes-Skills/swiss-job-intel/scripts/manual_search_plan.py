#!/usr/bin/env python3
"""
Plan de recherche manuelle assistée — swiss-job-intel.

Génère des requêtes optimisées et un guide Markdown quand les sources
automatiques ne couvrent pas suffisamment le profil candidat.

Usage:
    python3 manual_search_plan.py <profile.json> <summary.json> [--out /path/] [--registry /path/]

Déclenchement automatique si :
  - tier_a == 0 et tier_b == 0
  - total < 5
"""
from __future__ import annotations
import json, os, sys, datetime, urllib.parse
from pathlib import Path

SKILL_ROOT     = Path(__file__).resolve().parent.parent
REGISTRY_PATH  = SKILL_ROOT / "source" / "sources_registry.yaml"

# Portails manuels toujours inclus (avec URL de recherche)
STATIC_PORTALS = [
    {
        "id": "jobup",
        "name": "Jobup.ch",
        "search_url_template": "https://www.jobup.ch/fr/emplois/?term={query}",
        "priority": 1,
        "notes": "Premier job board romand — filtre Region pour Valais/Vaud",
    },
    {
        "id": "jobs_ch",
        "name": "Jobs.ch",
        "search_url_template": "https://www.jobs.ch/fr/emplois/?term={query}",
        "priority": 1,
        "notes": "Portail national — filtres canton et type de contrat disponibles",
    },
    {
        "id": "indeed_ch",
        "name": "Indeed Suisse",
        "search_url_template": "https://ch.indeed.com/jobs?q={query}&l=Suisse",
        "priority": 2,
        "notes": "Large couverture — trier par date pour éliminer les doublons anciens",
    },
    {
        "id": "linkedin_ch",
        "name": "LinkedIn Jobs",
        "search_url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location=Suisse",
        "priority": 2,
        "notes": "Réseau professionnel — activer alerte emploi pour les requêtes P1",
    },
    {
        "id": "romandie",
        "name": "Romandie.com Emploi",
        "search_url_template": "https://emploi.romandie.com/offres-emploi/index/?q={query}",
        "priority": 2,
        "notes": "Spécialisé Suisse romande — forte couverture collectivités publiques",
    },
]

INACTIVE_STATUSES = {"blocked_cloudflare", "spa_manual", "spa_no_api",
                     "js_dynamic", "tls_error"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_json(path: str | Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[err] {path}: {e}")
        return None


def load_yaml_safe(path: str | Path) -> dict | None:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        return None
    except Exception:
        return None


def should_generate(summary: dict) -> tuple[bool, str]:
    tier_a = summary.get("tier_a", 0)
    tier_b = summary.get("tier_b", 0)
    total  = summary.get("total", 0)
    if tier_a == 0 and tier_b == 0:
        return True, "Aucune offre Tier A/B trouvée via sources automatiques"
    if total < 5:
        return True, f"Seulement {total} offre(s) retenue(s) — couverture insuffisante"
    return False, ""


def generate_queries(profile: dict) -> list[dict]:
    queries: list[dict] = []
    seen: set[str] = set()

    def add(label: str, query: str, priority: int, intent: str) -> None:
        q = query.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append({"label": label, "query": q, "priority": priority, "intent": intent})

    rec_title = profile.get("recommended_title") or profile.get("_meta", {}).get("recommended_title", "")
    if rec_title:
        add("titre recommandé", rec_title, 1, "titre cible direct — optimisé ATS")

    for role in (profile.get("target_roles") or [])[:4]:
        add("rôle cible", role, 1, "variante de titre connue des recruteurs")

    primary = profile.get("primary_terms") or []
    for term in primary[:5]:
        add("terme principal", term, 2, "terme de recherche clé du profil")

    locations = profile.get("preferred_locations") or []
    for term in primary[:3]:
        for loc in locations[:2]:
            add("terme + canton", f"{term} {loc}", 2, f"recherche géolocalisée ({loc})")

    for skill in (profile.get("hard_skills") or [])[:4]:
        add("compétence technique", skill, 3, "recruteurs recherchent parfois la compétence directement")

    return queries


def get_registry_portals(registry: dict | None) -> list[dict]:
    """Retourne les sources du registry avec search_url_template (manuelles ou needs_connector)."""
    if not registry:
        return []
    portals = []
    for sid, src in (registry.get("sources") or {}).items():
        status = src.get("status", "")
        if status in INACTIVE_STATUSES or status == "needs_connector":
            tpl = src.get("search_url_template") or src.get("url")
            if tpl:
                portals.append({
                    "id": sid,
                    "name": src.get("label", sid),
                    "search_url_template": tpl,
                    "priority": 2 if status == "needs_connector" else 3,
                    "notes": src.get("notes", ""),
                    "from_registry": True,
                })
    return portals


def build_portal_urls(portal: dict, queries: list[dict]) -> list[dict]:
    tpl = portal.get("search_url_template", "")
    if not tpl:
        return []
    # Si le template ne contient pas {query}, c'est un listing fixe — une seule entrée
    if "{query}" not in tpl:
        return [{"query": "→ filtrer sur la page", "priority": 1, "url": tpl}]
    urls = []
    for q in queries:
        if q["priority"] <= 2:
            encoded = urllib.parse.quote_plus(q["query"])
            url = tpl.replace("{query}", encoded)
            urls.append({"query": q["query"], "priority": q["priority"], "url": url})
    return urls


def write_markdown(plan: dict, out_path: Path) -> None:
    c = plan["candidate"]
    today = plan["generated"]
    queries = plan["queries"]
    portals = plan["portals"]

    lines = [
        f"# Plan de recherche manuelle — {c} — {today}\n",
        f"**Statut :** {plan['reason']}\n",
        f"**Résultats auto :** Tier A={plan['auto_results']['tier_a']} · "
        f"Tier B={plan['auto_results']['tier_b']} · "
        f"Tier C={plan['auto_results']['tier_c']} · "
        f"Total={plan['auto_results']['total']}\n",
        "---\n",
        "## Requêtes recommandées\n",
        "| Priorité | Requête | Intention |\n|---|---|---|",
    ]
    for q in queries:
        lines.append(f"| P{q['priority']} | `{q['query']}` | {q['intent']} |")

    lines += ["", "---", "", "## Portails à ouvrir\n"]

    p1 = [p for p in portals if p["priority"] == 1]
    p2 = [p for p in portals if p["priority"] == 2]
    p3 = [p for p in portals if p["priority"] >= 3]

    for tier_label, tier_portals in [("Priorité 1", p1), ("Priorité 2", p2), ("Priorité 3+", p3)]:
        if not tier_portals:
            continue
        lines.append(f"### {tier_label}\n")
        for p in tier_portals:
            lines.append(f"**{p['name']}**")
            if p.get("notes"):
                lines.append(f"> {p['notes']}\n")
            for u in p.get("urls", [])[:5]:
                lines.append(f"- P{u['priority']} [`{u['query']}`]({u['url']})")
            lines.append("")

    lines += [
        "---",
        "",
        "## Conseils de tri",
        "",
        "- Trier par **date de publication** (plus récent d'abord)",
        "- Filtrer par **région** selon les cantons cibles du profil",
        "- Privilégier les offres avec **description complète** (snippet > 200 caractères)",
        "- Ignorer les offres d'agences de placement si poste direct disponible",
        "",
        "## Sources institutionnelles à connecter (priorité P2)",
        "",
        "Ces portails sont actifs mais sans connecteur automatique :",
        "",
        "- [État de Vaud — offres d'emploi](https://www.vd.ch/themes/etat-droit-finances/"
        "ressources-humaines/emplois-a-letat-de-vaud/)",
        "- [État du Valais — Stellenbörse](https://www.vs.ch/web/srh/stellenborse)",
        "- [HES-SO — emplois](https://www.hes-so.ch/fr/emplois)",
        "- [Hôpital du Valais — offres](https://www.hopitalvs.ch/travailler-chez-nous/offres-demploi)",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    profile_path  = None
    summary_path  = None
    out_dir       = str(Path.cwd())
    registry_path = str(REGISTRY_PATH)

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--out" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        elif args[i] == "--registry" and i + 1 < len(args):
            registry_path = args[i + 1]; i += 2
        elif not args[i].startswith("--") and args[i].endswith(".json"):
            if profile_path is None:
                profile_path = args[i]
            else:
                summary_path = args[i]
            i += 1
        else:
            i += 1

    if not profile_path or not os.path.exists(profile_path):
        log("❌ profile_path manquant ou introuvable")
        sys.exit(1)

    profile = load_json(profile_path) or {}
    summary = load_json(summary_path) if summary_path and os.path.exists(summary_path) else {}

    triggered, reason = should_generate(summary)
    if not triggered:
        log(f"[manual_search] Pas nécessaire — {summary.get('tier_a', 0)} Tier A, "
            f"{summary.get('tier_b', 0)} Tier B, {summary.get('total', 0)} total")
        sys.exit(0)

    log(f"[manual_search] Déclenchement : {reason}")

    registry = load_yaml_safe(registry_path)
    queries  = generate_queries(profile)
    portals  = list(STATIC_PORTALS)
    existing_templates = {p.get("search_url_template", "").split("?")[0] for p in portals}
    for p in get_registry_portals(registry):
        tpl_base = (p.get("search_url_template") or "").split("?")[0]
        if p["id"] not in {ep["id"] for ep in portals} and tpl_base not in existing_templates:
            portals.append(p)
            if tpl_base:
                existing_templates.add(tpl_base)
    portals.sort(key=lambda p: p["priority"])

    for p in portals:
        p["urls"] = build_portal_urls(p, queries)

    today = datetime.date.today().strftime("%d-%m-%Y")
    meta  = profile.get("_meta", {})
    plan = {
        "generated":          today,
        "candidate":          meta.get("name") or profile.get("name", "?"),
        "recommended_title":  meta.get("recommended_title") or profile.get("recommended_title", ""),
        "domain":             profile.get("domain", ""),
        "status":             "manual_search_recommended",
        "reason":             reason,
        "auto_results":       {
            "tier_a": summary.get("tier_a", 0),
            "tier_b": summary.get("tier_b", 0),
            "tier_c": summary.get("tier_c", 0),
            "total":  summary.get("total", 0),
        },
        "queries":  queries,
        "portals":  portals,
    }

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    json_path = Path(out_dir) / f"{today}_manual_search_plan.json"
    md_path   = Path(out_dir) / f"{today}_manual_search_plan.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    write_markdown(plan, md_path)

    p1_count = sum(1 for q in queries if q["priority"] == 1)
    log(f"✅ Plan généré — {len(queries)} requêtes ({p1_count} P1) · {len(portals)} portails")
    print(f"\n🔍 Plan recherche manuelle → {md_path}")
    print(f"📋 JSON                    → {json_path}")


if __name__ == "__main__":
    main()
