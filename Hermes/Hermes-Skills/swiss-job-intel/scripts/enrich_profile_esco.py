#!/usr/bin/env python3
"""
Enrichissement ESCO/ISCO du profil swiss-job-intel.

Usage:
    python3 enrich_profile_esco.py [profile_cache.json] [--out /tmp/profile_enriched.json]

Stratégie :
  1. Si source/taxonomy_db.json existe (build_taxonomy_db.py déjà exécuté) :
       → lookup instantané, couverture totale CH-ISCO-19 (23K métiers) + ESCO v1.2.1
  2. Sinon, fallback sur les YAML manuels de source/taxonomies/
       → couverture partielle (IT, santé, social, bâtiment, agriculture)

Résultat : primary_terms étendu avec synonymes officiels ISCO/ESCO suisses.

Pas de dépendance externe (json dans stdlib). PyYAML nécessaire uniquement pour fallback.
"""
from __future__ import annotations
import json, sys, os, unicodedata
from pathlib import Path

SKILL_ROOT    = Path(__file__).resolve().parent.parent
DB_PATH       = SKILL_ROOT / "source" / "taxonomy_db.json"
TAXONOMIES_DIR = SKILL_ROOT / "source" / "taxonomies"


def norm(text: str) -> str:
    if not text:
        return ""
    t = str(text).lower().strip()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def terms_overlap(term_set: set[str], labels: list[str]) -> bool:
    for pt in term_set:
        for lbl in labels:
            if lbl and pt and (pt in lbl or lbl in pt):
                return True
    return False


def parse_args() -> tuple[str, str]:
    profile_path = "profile_cache.json"
    out_path = "/tmp/profile_enriched.json"
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--out" and i + 1 < len(args):
            out_path = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and args[i].endswith(".json"):
            profile_path = args[i]
            i += 1
        else:
            i += 1
    return profile_path, out_path


# ──────────────────────────────────────────────────────────────────────────────
# Enrichissement via taxonomy_db.json (couverture totale)
# ──────────────────────────────────────────────────────────────────────────────

MAX_NEW_TERMS   = 200   # plafond absolu pour éviter l'explosion du profil
MAX_CH_NAMES    = 25    # noms CH-ISCO par groupe (les plus représentatifs)
MAX_TEXTUAL_GRP = 5     # groupes ajoutés via matching textuel (hors codes ISCO explicites)
MIN_TERM_LEN    = 5     # longueur minimale d'un terme pour le matching textuel


def enrich_from_db(
    primary_terms: list[str],
    primary_norms: set[str],
    isco_codes: list[str],
    db: dict,
) -> list[str]:
    """
    Retourne la liste des termes ajoutés.

    Deux passes :
    A. ISCO codes explicites → lookup direct dans by_isco4 (expansion complète)
    B. Matching textuel → top-N groupes par score, unit_label + minor_label uniquement
       (seulement si < 3 groupes matchés via codes ISCO)
    """
    added: list[str] = []
    by_isco4: dict = db.get("by_isco4", {})

    def add_if_new(term: str) -> None:
        if len(added) >= MAX_NEW_TERMS:
            return
        n = norm(term)
        if n and len(n) > 2 and n not in primary_norms:
            primary_terms.append(term)
            primary_norms.add(n)
            added.append(term)

    def absorb_entry(entry: dict) -> None:
        # Noms CH-ISCO officiels (titres de postes réels en Suisse)
        for term in entry.get("ch_names", [])[:MAX_CH_NAMES]:
            add_if_new(term)
        # Labels et synonymes ESCO officiels
        for term in entry.get("esco_preferred", []) + entry.get("esco_alts", []):
            add_if_new(term)
        # Compétences essentielles (pour enrichir les snippets)
        for term in entry.get("skills", [])[:10]:
            add_if_new(term)

    # ── Passe A : codes ISCO explicites ──────────────────────────────────────
    matched_direct: set[str] = set()
    for code in isco_codes:
        c4 = str(code).strip()[:4]
        if c4 in by_isco4:
            absorb_entry(by_isco4[c4])
            matched_direct.add(c4)
            print(f"   [ISCO {c4}] {by_isco4[c4].get('unit_label','?')} ({len(added)} termes)", file=sys.stderr)

    # ── Passe B : matching textuel (seulement si peu de codes directs) ────────
    if len(matched_direct) < 3 and len(added) < MAX_NEW_TERMS:
        # Scorer chaque groupe : compter les primary_terms (≥ MIN_TERM_LEN cars)
        # qui apparaissent dans unit_label ou minor_label du groupe ISCO
        scored: list[tuple[int, str]] = []
        significant_terms = [pt for pt in primary_norms if len(pt) >= MIN_TERM_LEN]

        for isco4, entry in by_isco4.items():
            if isco4 in matched_direct:
                continue
            unit_lbl  = norm(entry.get("unit_label", ""))
            minor_lbl = norm(entry.get("minor_label", ""))
            labels = [unit_lbl, minor_lbl]
            score = sum(
                1 for pt in significant_terms
                if any(pt in lbl for lbl in labels if lbl)
            )
            if score >= 1:
                scored.append((score, isco4))

        # Top N groupes par score décroissant
        top_groups = sorted(scored, reverse=True)[:MAX_TEXTUAL_GRP]
        for score, isco4 in top_groups:
            absorb_entry(by_isco4[isco4])
            matched_direct.add(isco4)
            print(
                f"   [ISCO {isco4}] {by_isco4[isco4].get('unit_label','?')} "
                f"(score={score}, match textuel)",
                file=sys.stderr,
            )

    return added


# ──────────────────────────────────────────────────────────────────────────────
# Fallback : enrichissement via YAML manuels de source/taxonomies/
# ──────────────────────────────────────────────────────────────────────────────

def enrich_from_yamls(
    primary_terms: list[str],
    primary_norms: set[str],
    isco_codes: list[str],
    profile_domain: str,
) -> list[str]:
    try:
        import yaml
    except ImportError:
        print("❌ PyYAML requis pour le fallback YAML : pip install pyyaml", file=sys.stderr)
        return []

    yaml_files = sorted(TAXONOMIES_DIR.glob("*.yaml")) + sorted(TAXONOMIES_DIR.glob("*.yml"))
    if not yaml_files:
        print(f"⚠️  Aucun YAML dans {TAXONOMIES_DIR}", file=sys.stderr)
        return []

    print(f"[esco-yaml] {len(yaml_files)} fichier(s) taxonomie", file=sys.stderr)
    added: list[str] = []
    profile_isco_set = set(str(c)[:4] for c in isco_codes)

    def add_if_new(term: str) -> None:
        n = norm(term)
        if n and len(n) > 2 and n not in primary_norms:
            primary_terms.append(term)
            primary_norms.add(n)
            added.append(term)

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as f:
                taxonomy = yaml.safe_load(f)
        except Exception as e:
            print(f"[warn] {yaml_path.name}: {e}", file=sys.stderr)
            continue

        for occ in taxonomy.get("occupations", []):
            occ_isco = str(occ.get("isco_code", ""))[:4]
            isco_match = occ_isco in profile_isco_set if profile_isco_set else False

            all_labels = [
                norm(occ.get("isco_label_fr", "")),
                norm(occ.get("ch_isco_label_fr", "")),
            ] + [norm(s) for s in occ.get("synonyms", [])]

            if isco_match or terms_overlap(primary_norms, all_labels):
                for s in occ.get("synonyms", []):
                    add_if_new(s)
                for rt in occ.get("related_terms", []):
                    add_if_new(rt)

        for skill in taxonomy.get("skills", []):
            skill_norms = [norm(l) for l in skill.get("labels", [])]
            if terms_overlap(primary_norms, skill_norms):
                for s in skill.get("synonyms", []):
                    add_if_new(s)

    return added


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    profile_path, out_path = parse_args()

    # Résoudre chemin relatif
    if not os.path.isabs(profile_path):
        profile_path = os.path.join(os.getcwd(), profile_path)

    if not os.path.exists(profile_path):
        print(f"❌ Profil non trouvé : {profile_path}", file=sys.stderr)
        sys.exit(1)

    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)

    primary_terms: list[str] = list(profile.get("primary_terms", []))
    primary_norms: set[str]  = {norm(t) for t in primary_terms}
    isco_codes: list[str]    = [str(c) for c in (profile.get("isco_codes") or [])]
    domain: str              = (profile.get("domain") or "").lower().strip()

    meta = profile.get("_meta", {})
    print(
        f"[esco] Profil : {meta.get('name','?')} | domaine: {domain} | "
        f"ISCO codes: {isco_codes or 'auto-détection'} | "
        f"{len(primary_terms)} termes initiaux",
        file=sys.stderr,
    )

    # ── Stratégie : DB complète ou fallback YAML ──────────────────────────────
    if DB_PATH.exists():
        print(f"[esco] Utilisation taxonomy_db.json ({DB_PATH.stat().st_size // 1024} KB)", file=sys.stderr)
        with open(DB_PATH, encoding="utf-8") as f:
            db = json.load(f)
        db_meta = db.get("_meta", {})
        print(
            f"       {db_meta.get('isco4_groups','?')} groupes ISCO | "
            f"{db_meta.get('total_ch_names','?')} métiers CH | "
            f"construit le {db_meta.get('built','?')}",
            file=sys.stderr,
        )
        added = enrich_from_db(primary_terms, primary_norms, isco_codes, db)
    else:
        print(
            f"[esco] taxonomy_db.json absent — fallback YAML manuels\n"
            f"       → Exécuter scripts/build_taxonomy_db.py pour la couverture totale",
            file=sys.stderr,
        )
        added = enrich_from_yamls(primary_terms, primary_norms, isco_codes, domain)

    # ── Résultat ──────────────────────────────────────────────────────────────
    profile["primary_terms"] = primary_terms

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(added)} termes ajoutés (total: {len(primary_terms)})", file=sys.stderr)
    for t in added[:20]:
        print(f"   + {t}", file=sys.stderr)
    if len(added) > 20:
        print(f"   ... (+{len(added)-20} autres)", file=sys.stderr)
    print(f"📝 → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
