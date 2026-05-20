#!/usr/bin/env python3
"""
Scoring et export CSV + Markdown pour le skill swiss-job-intel.

Usage:
    python3 score_export.py <offers.json> [profile_cache.json]
    → Écrit DD-MM-YYYY_output.csv et DD-MM-YYYY_output.md dans le CWD.

Le fichier offers.json doit être un array JSON avec les champs :
    title, employer, location, url, date, snippet, source

Hiérarchie de score :
    titre métier > hard skills > snippet > localisation > récence > soft skills
"""
from __future__ import annotations
import json, csv, unicodedata, datetime, sys, io, re, os

# ── Soft skills trop génériques pour discriminer ─────────────────────────────
# Ignorés dans les soft_skills du profil — présents dans presque toutes les offres
GENERIC_SOFT: frozenset[str] = frozenset({
    "organisation", "integrite", "autonomie", "communication",
    "motivation", "dynamisme", "rigueur", "flexibilite",
    "proactivite", "initiative", "serieux", "polyvalence",
    "adaptabilite", "gestion du stress", "esprit d equipe", "equipe",
    "ouverture", "curiosite", "engagement", "fiabilite", "perseverance",
    "respect", "empathie", "leadership",
})

# ── Helpers ───────────────────────────────────────────────────────────────────
def norm(text: object) -> str:
    if not text: return ""
    t = str(text).lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _recency_bonus(date_raw: str) -> int:
    """
    +3 si ≤7j · +2 si ≤14j · +1 si ≤30j · 0 sinon.
    Supporte :
      - Workday : "today", "yesterday", "Posted X Days Ago"
      - ISO 8601 : "2026-05-10", "2026-05-10T12:00:00+02:00", etc.
    """
    if not date_raw:
        return 0
    raw = str(date_raw).strip()
    raw_n = norm(raw)

    # Formats relatifs (Workday)
    if "today" in raw_n or "yesterday" in raw_n:
        return 3
    m = re.search(r"posted\s+(\d+)\s+days?\s+ago", raw_n)
    if m:
        d = int(m.group(1))
        return 3 if d <= 7 else (2 if d <= 14 else (1 if d <= 30 else 0))

    # Formats ISO — extraire YYYY-MM-DD (préfixe universel)
    iso_m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if iso_m:
        try:
            date = datetime.date.fromisoformat(iso_m.group(1))
            d = (datetime.date.today() - date).days
            if d < 0:
                return 0  # date future (données erronées)
            return 3 if d <= 7 else (2 if d <= 14 else (1 if d <= 30 else 0))
        except ValueError:
            pass

    return 0


def score_offer(offer: dict, profile: dict) -> tuple[int, list[str]]:
    """
    Calcule le score d'une offre pour un profil candidat.
    Retourne (score, [mots_clés_matchés]).

    Pondération :
      Titre cible exact   → +6   (recommended_title dans le titre de l'offre)
      Rôle cible approché → +4   (target_roles dans le titre)
      primary_terms titre → +5   par terme
      primary_terms snip  → +2   par terme (snippet uniquement)
      hard_skills titre   → +3   par terme
      hard_skills snippet → +2   par terme
      soft_skills titre   → +1   (cap +3, termes génériques ignorés)
      soft_skills snippet →  0   (ne discrimine pas)
      localisation        → +3   (un seul bonus)
      récence             → +1/+2/+3
      exclude_terms titre → -8   par terme
      0 primary_terms     → -5   (pénalité : aucun terme métier dans titre + snippet)
    """
    title   = norm(offer.get("title", ""))
    snippet = norm(offer.get("snippet", ""))
    loc     = norm(offer.get("location", ""))
    score   = 0
    matched: list[str] = []

    # 1. TITRE CIBLE — bonus si l'offre cible le poste visé directement
    rec_title = norm(profile.get("recommended_title", "") or "")
    if rec_title and len(rec_title) > 4 and rec_title in title:
        score += 6
        matched.append(profile.get("recommended_title", ""))
    else:
        for role in (profile.get("target_roles") or []):
            rn = norm(role)
            if rn and len(rn) > 4 and rn in title:
                score += 4
                matched.append(role)
                break  # un seul bonus target_role par offre

    # 2. PRIMARY_TERMS : titre → +5, snippet uniquement → +2
    for kw in profile.get("primary_terms", []):
        kw_n = norm(kw)
        if not kw_n or len(kw_n) < 3:
            continue
        if kw_n in title:
            score += 5
            matched.append(kw)
        elif kw_n in snippet:
            score += 2
            matched.append(kw)

    # 3. HARD_SKILLS : titre → +3, snippet → +2
    for kw in profile.get("hard_skills", []):
        kw_n = norm(kw)
        if not kw_n or len(kw_n) < 3:
            continue
        if kw_n in title:
            score += 3
            matched.append(kw)
        elif kw_n in snippet:
            score += 2
            matched.append(kw)

    # 4. SOFT_SKILLS : titre uniquement, cap +3, termes génériques ignorés
    soft_total = 0
    for kw in profile.get("soft_skills", []):
        if soft_total >= 3:
            break
        kw_n = norm(kw)
        if not kw_n or kw_n in GENERIC_SOFT:
            continue
        if kw_n in title:
            soft_total += 1
            matched.append(kw)
    score += soft_total

    # 5. EXCLUDE_TERMS : pénalité -8 sur le titre uniquement
    for kw in profile.get("exclude_terms", []):
        if norm(kw) in title:
            score -= 8

    # 6. LOCALISATION : +3 si une localisation préférée est dans le lieu de l'offre
    for pref in profile.get("preferred_locations", []):
        if norm(pref) in loc:
            score += 3
            break

    # 7. PÉNALITÉ — aucun primary_term présent nulle part (titre + snippet)
    pt_norms = [norm(kw) for kw in profile.get("primary_terms", [])
                if len(norm(kw)) >= 3]
    if pt_norms and not any(kw in (title + " " + snippet) for kw in pt_norms):
        score -= 5

    # 8. RÉCENCE
    score += _recency_bonus(offer.get("date", ""))

    return score, list(dict.fromkeys(matched))


def tier(score: int) -> str | None:
    if score >= 20: return "A"
    if score >= 12: return "B"
    if score >= 6:  return "C"
    return None


def compute_gaps(offer: dict, profile: dict) -> list[str]:
    """
    Retourne les primary_terms absents de l'offre (titre + snippet).
    Max 5 termes, filtre les termes courts et les génériques.
    """
    title_snippet = norm(
        (offer.get("title") or "") + " " + (offer.get("snippet") or "")
    )
    candidates = [kw for kw in profile.get("primary_terms", [])[:20]
                  if len(norm(kw)) >= 4 and norm(kw) not in GENERIC_SOFT]
    return [kw for kw in candidates if norm(kw) not in title_snippet][:5]


def _try_load_profile(path: str | None) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for k in ["preferred_locations", "primary_terms", "hard_skills",
                   "soft_skills", "exclude_terms"]:
            data.setdefault(k, [])
        return data
    except Exception as e:
        print(f"[profile] Erreur chargement {path}: {e}", file=sys.stderr)
        return None


# ── Point d'entrée ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/jobs_all.json"
    try:
        with open(input_file, encoding="utf-8") as f:
            offers = json.load(f)
    except FileNotFoundError:
        print(f"❌ Fichier d'offres introuvable : {input_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Fichier d'offres invalide (JSON) : {e}", file=sys.stderr)
        sys.exit(1)

    profile = (
        _try_load_profile(sys.argv[2] if len(sys.argv) > 2 else None) or
        _try_load_profile(os.path.join(os.getcwd(), "profile_cache.json"))
    )
    if not profile:
        print("❌ Aucun profil candidat trouvé.", file=sys.stderr)
        print("   Fournir profile_cache.json en argument ou le placer dans le répertoire courant.", file=sys.stderr)
        print("   Générer le profil : lancer le skill swiss-job-intel (Phase 0 → Phase 2C).", file=sys.stderr)
        sys.exit(1)

    meta = profile.get("_meta", {})
    print(f"[profile] Chargé : {meta.get('name','?')} — {meta.get('recommended_title','?')}",
          file=sys.stderr)

    today_str = datetime.date.today().strftime("%d-%m-%Y")
    scored = []

    for offer in offers:
        s, matched = score_offer(offer, profile)
        t = tier(s)
        if t is None:
            continue
        gaps = compute_gaps(offer, profile)
        scored.append({
            "date_export":       today_str,
            "tier":              t,
            "score":             s,
            "titre":             offer.get("title", ""),
            "employeur":         offer.get("employer", ""),
            "localisation":      offer.get("location", ""),
            "source":            offer.get("source", ""),
            "url":               offer.get("url", ""),
            "date_offre":        offer.get("date", ""),
            "mots_cles_matches": ", ".join(matched[:8]),
            "gaps":              ", ".join(gaps),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        print("⚠️  Aucune offre n'a passé le seuil. Vérifier les termes du profil et les sources.",
              file=sys.stderr)
        sys.exit(0)

    nA = sum(1 for o in scored if o["tier"] == "A")
    nB = sum(1 for o in scored if o["tier"] == "B")
    nC = sum(1 for o in scored if o["tier"] == "C")

    print(f"✅ {len(scored)} offres retenues — Tier A: {nA}, Tier B: {nB}, Tier C: {nC}")
    for o in scored:
        print(f"  [{o['tier']}] {o['score']:3d} | {o['titre']:<55} | {o['localisation']:<22}")

    # ── CSV ──────────────────────────────────────────────────────────────────
    csv_path = f"{today_str}_output.csv"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "date_export", "tier", "score", "titre", "employeur",
        "localisation", "source", "url", "date_offre", "mots_cles_matches", "gaps"
    ], quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(scored)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(buf.getvalue())

    # ── Markdown ─────────────────────────────────────────────────────────────
    md_path = f"{today_str}_output.md"
    tier_labels = {
        "A": "Forte compatibilité (score ≥ 20)",
        "B": "Compatibilité moyenne (score 12–19)",
        "C": "Pistes exploratoires (score 6–11)",
    }
    sources_used = list(dict.fromkeys(o["source"] for o in scored))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Veille emploi Suisse — {today_str}\n\n")
        f.write("| Tier | Définition | Nb |\n|---|---|---|\n")
        f.write(f"| **A** | Forte compatibilité (≥ 20) | **{nA}** |\n")
        f.write(f"| **B** | Compatibilité moyenne (12-19) | **{nB}** |\n")
        f.write(f"| **C** | Exploratoire (6-11) | **{nC}** |\n")
        f.write(f"| | **Total** | **{len(scored)}** |\n\n")
        f.write(f"Sources actives : {', '.join(sources_used)}\n\n---\n\n")

        for t_key, lbl in tier_labels.items():
            group = [o for o in scored if o["tier"] == t_key]
            if not group: continue
            f.write(f"## Tier {t_key} — {lbl}\n\n")
            for o in group:
                f.write(f"### {o['titre']} — {o['employeur']}\n")
                f.write("| | |\n|---|---|\n")
                f.write(f"| Score | **{o['score']}** |\n")
                f.write(f"| Localisation | {o['localisation']} |\n")
                f.write(f"| Source | {o['source']} |\n")
                f.write(f"| Date | {o['date_offre'] or '—'} |\n")
                f.write(f"| URL | {o['url']} |\n")
                f.write(f"| Match | {o['mots_cles_matches'] or '—'} |\n")
                f.write(f"| Gaps | {o['gaps'] or '—'} |\n\n")

        rec_title   = meta.get("recommended_title") or profile.get("recommended_title", "")
        top_terms   = profile.get("primary_terms", [])[:5]
        top_missing = list(dict.fromkeys(
            kw for o in scored for kw in o["gaps"].split(", ") if kw
        ))[:5]

        f.write("---\n\n## Recommandations\n\n")
        if rec_title:
            f.write(f"- Titre cible ATS : `{rec_title}`\n")
        if top_terms:
            f.write(f"- Termes prioritaires du profil : "
                    f"{' · '.join(f'`{t}`' for t in top_terms)}\n")
        if top_missing:
            f.write(f"- Compétences absentes des offres Tier A/B : "
                    f"{' · '.join(f'`{t}`' for t in top_missing)}\n")

    # ── summary.json ─────────────────────────────────────────────────────────
    summary = {
        "generated":   today_str,
        "candidate":   f"{meta.get('name','?')} — {meta.get('recommended_title','?')}",
        "domain":      profile.get("domain", ""),
        "tier_a": nA, "tier_b": nB, "tier_c": nC, "total": len(scored),
        "top_offers": [
            {
                "tier":     o["tier"],
                "score":    o["score"],
                "title":    o["titre"],
                "employer": o["employeur"],
                "location": o["localisation"],
                "url":      o["url"],
                "match":    o["mots_cles_matches"],
            }
            for o in scored[:10]
        ],
        "top_missing":  top_missing,
        "sources":      sources_used,
    }
    summary_path = f"{today_str}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n📄 CSV     → {csv_path}")
    print(f"📝 MD      → {md_path}")
    print(f"📊 Summary → {summary_path}")
