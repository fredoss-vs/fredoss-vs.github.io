#!/usr/bin/env python3
"""
Swiss Job Intel — Orchestrateur autonome universel.

Usage:
    python3 orchestrate.py [profile_cache.json] [--out /path/to/output]

Pipeline complet en une commande :
  1. Charge profile_cache.json (domaine + termes + ISCO)
  2. Sélectionne les sources actives depuis sources_registry.yaml
  3. Lance scrape_ch_jobs.py (toutes sources actives, séquentiellement)
  4. Écrit les offres brutes → /tmp/jobs_raw.json
  5. Lance score_export.py → CSV + Markdown dans --out

IMPORTANT (WSL) : exécuter via terminal(), jamais via execute_code.
Copier dans /tmp/ avant d'exécuter :
    cp /path/to/skill/scripts/orchestrate.py /tmp/orchestrate.py
    python3 /tmp/orchestrate.py profile_cache.json --out .
"""
from __future__ import annotations
import json, os, sys, subprocess, time, tempfile, datetime, hashlib
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = SKILL_ROOT / "source" / "sources_registry.yaml"
SCRAPER_PATH = SKILL_ROOT / "scripts" / "scrape_ch_jobs.py"
SCORER_PATH  = SKILL_ROOT / "scripts" / "score_export.py"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_json(path: str | Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"[err] Impossible de charger {path}: {e}")
        return None


def load_yaml_safe(path: str | Path) -> dict | None:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        log("[warn] PyYAML non installé — sources_registry non chargé (pip install pyyaml)")
        return None
    except Exception as e:
        log(f"[err] sources_registry: {e}")
        return None


INACTIVE_STATUSES = {"blocked_cloudflare", "spa_manual", "spa_no_api", "needs_connector",
                     "js_dynamic", "tls_error"}


def select_sources(profile: dict, registry: dict | None) -> list[dict]:
    """
    Sélectionne toutes les sources techniquement scrapables.

    Critère unique : disponibilité technique (statut hors INACTIVE_STATUSES).
    La pertinence métier est décidée au scoring de chaque offre individuelle.

    preferred_domains dans le registry = annotation documentaire uniquement,
    jamais une règle d'exclusion. Un hôpital publie des postes IT ; une école
    technique publie des postes RH ; CIGES peut publier hors IT.
    """
    if not registry:
        log("[warn] Registry non disponible — fallback scrape_ch_jobs.py")
        return [{"id": "default", "connector": "scrape_ch_jobs"}]

    all_sources = registry.get("sources", {})
    selected: list[dict] = []

    for sid, src in all_sources.items():
        status = src.get("status", "")
        if status in INACTIVE_STATUSES:
            log(f"[sources] ✗ {src.get('label', sid)} — {status}")
            continue
        selected.append(src)
        log(f"[sources] ✓ {src.get('label', sid)}")

    if not selected:
        log("[warn] Aucune source active — fallback scrape_ch_jobs.py")
        selected = [{"id": "default", "connector": "scrape_ch_jobs"}]

    return selected


def run_scraper_subprocess(profile_path: str, tmp_out: str, selected: list[dict]) -> bool:
    """Lance scrape_ch_jobs.py dans un sous-processus. Retourne True si succès."""
    if not SCRAPER_PATH.exists():
        log(f"[err] Scraper introuvable : {SCRAPER_PATH}")
        return False
    tmp_sources = "/tmp/selected_sources.json"
    try:
        with open(tmp_sources, "w", encoding="utf-8") as f:
            json.dump(selected, f, ensure_ascii=False)
    except Exception as e:
        log(f"[warn] Impossible d'écrire {tmp_sources}: {e} — scraper utilisera toutes les sources")
        tmp_sources = None
    cmd = [sys.executable, str(SCRAPER_PATH), profile_path]
    if tmp_sources:
        cmd += ["--sources", tmp_sources]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                log(f"  {line}")
        if result.returncode != 0:
            log(f"[err] scrape_ch_jobs.py code retour {result.returncode}")
            return False
        # Écrire la sortie JSON
        with open(tmp_out, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        return True
    except subprocess.TimeoutExpired:
        log("[err] Timeout scraping (600s dépassé)")
        return False
    except Exception as e:
        log(f"[err] Scraper: {e}")
        return False


def run_scorer(offers_path: str, profile_path: str, out_dir: str) -> bool:
    """Lance score_export.py dans le répertoire de sortie."""
    if not SCORER_PATH.exists():
        log(f"[err] Scorer introuvable : {SCORER_PATH}")
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(SCORER_PATH), offers_path, profile_path],
            cwd=out_dir, capture_output=True, text=True, timeout=60
        )
        for line in (result.stdout + result.stderr).strip().splitlines():
            print(line)   # sortie principale visible dans la conversation
        return result.returncode == 0
    except Exception as e:
        log(f"[err] Scorer: {e}")
        return False


def run_manual_search_plan(profile_path: str, out_dir: str) -> str | None:
    """
    Lance manual_search_plan.py si disponible.
    Retourne le nom du fichier généré, ou None si non déclenché.
    """
    script = SKILL_ROOT / "scripts" / "manual_search_plan.py"
    if not script.exists():
        return None
    today = datetime.date.today().strftime("%d-%m-%Y")
    summary_path = str(Path(out_dir) / f"{today}_summary.json")
    try:
        result = subprocess.run(
            [sys.executable, str(script), profile_path, summary_path,
             "--out", out_dir, "--registry", str(REGISTRY_PATH)],
            capture_output=True, text=True, timeout=15
        )
        for line in (result.stdout + result.stderr).strip().splitlines():
            print(line)
        if result.returncode == 0 and (Path(out_dir) / f"{today}_manual_search_plan.json").exists():
            return f"{today}_manual_search_plan.json"
    except Exception as e:
        log(f"[warn] manual_search_plan: {e}")
    return None


def enrich_profile(profile_path: str) -> str:
    """Lance enrich_profile_esco.py si disponible. Retourne le chemin du profil enrichi."""
    enrich_script = SKILL_ROOT / "scripts" / "enrich_profile_esco.py"
    enriched_path = "/tmp/profile_enriched.json"

    if not enrich_script.exists():
        return profile_path

    try:
        result = subprocess.run(
            [sys.executable, str(enrich_script), profile_path, "--out", enriched_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            for line in result.stderr.strip().splitlines():
                log(f"  {line}")
            return enriched_path
    except Exception as e:
        log(f"[warn] Enrichissement ESCO échoué: {e} — profil original conservé")

    return profile_path


def main() -> None:
    # ── Arguments ─────────────────────────────────────────────────────────────
    profile_arg   = "profile_cache.json"
    out_dir       = str(Path.cwd() / "results")
    force_refresh = False
    force_profile = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--out" and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2
        elif args[i] == "--force-refresh":
            force_refresh = True; i += 1
        elif args[i] == "--force-profile":
            force_profile = True; force_refresh = True; i += 1
        elif not args[i].startswith("--") and args[i].endswith(".json"):
            profile_arg = args[i]; i += 1
        else:
            i += 1

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    if force_refresh:
        flag = Path(out_dir) / "done.flag"
        if flag.exists():
            flag.unlink()
            log("🔄 --force-refresh : done.flag supprimé")
    if force_profile:
        cache = Path(os.getcwd()) / profile_arg
        if cache.exists():
            cache.unlink()
            log("🔄 --force-profile : profile_cache.json supprimé.")
        else:
            log("🔄 --force-profile : profile_cache.json déjà absent.")
        log("   ➜  Relancer le skill Hermes pour régénérer le profil candidat (Phase 0 → 2C).")
        sys.exit(0)   # sortie propre — le LLM doit prendre le relais

    # ── Résoudre le chemin du profil ───────────────────────────────────────────
    profile_path = profile_arg if os.path.isabs(profile_arg) else os.path.join(os.getcwd(), profile_arg)
    if not os.path.exists(profile_path):
        log(f"❌ Profil non trouvé : {profile_path}")
        log("   Exécuter d'abord le skill swiss-job-intel (Phase 2C) pour créer profile_cache.json")
        sys.exit(1)

    profile = load_json(profile_path) or {}
    # ── Validation du profil ───────────────────────────────────────────────────
    errors = []
    if not profile.get("primary_terms"):
        errors.append("primary_terms vide ou absent — profil inutilisable pour le scraping")
    if not profile.get("domain"):
        errors.append("domain absent — routage des sources impossible")
    cached_ver = profile.get("_meta", {}).get("skill_version", "")
    if cached_ver and cached_ver != "6.0.0":
        errors.append(f"skill_version '{cached_ver}' ≠ '6.0.0' — régénérer avec --force-profile")
    if errors:
        for e in errors:
            log(f"❌ Profil invalide : {e}")
        log("   Utiliser --force-profile pour régénérer, ou relancer le skill (Phase 0 → Phase 2C).")
        sys.exit(1)

    # ── Vérification hash sources (cv.md / bilan.md ont-ils changé ?) ─────────
    def _hash(path: str) -> str:
        try:
            return hashlib.md5(Path(path).read_bytes()).hexdigest()[:12]
        except Exception:
            return ""

    stored_hash = profile.get("_meta", {}).get("source_hash", "")
    if stored_hash:
        current_hash = _hash("cv.md") + "+" + _hash("bilan.md")
        if current_hash != stored_hash:
            log("⚠️  cv.md ou bilan.md a changé depuis la génération du profil.")
            log("   Utiliser --force-profile pour régénérer le profil candidat.")

    m = profile.get("_meta", {})
    domain = profile.get("domain", "inconnu")
    log(f"🚀 swiss-job-intel — {m.get('name', '?')} | domaine: {domain} | {len(profile.get('primary_terms', []))} termes")

    # ── Enrichissement ESCO ────────────────────────────────────────────────────
    log("\n[1/4] Enrichissement ESCO/ISCO...")
    active_profile_path = enrich_profile(profile_path)

    # ── Chargement du registry ─────────────────────────────────────────────────
    log("\n[2/4] Sélection des sources...")
    registry = load_yaml_safe(REGISTRY_PATH)
    selected = select_sources(profile, registry)
    log(f"      {len(selected)} source(s) techniquement active(s)")

    # ── Scraping parallèle ─────────────────────────────────────────────────────
    log("\n[3/4] Scraping (parallèle)...")
    t0 = time.time()

    # Pour l'instant : un scraper principal + subprocessus parallèles pour futures sources
    # Architecture extensible : chaque source dans `selected` peut avoir son propre scraper
    tmp_raw = "/tmp/jobs_raw.json"
    ok = run_scraper_subprocess(active_profile_path, tmp_raw, selected)

    if not ok or not os.path.exists(tmp_raw):
        log("❌ Aucune offre collectée — vérifier la connectivité réseau")
        sys.exit(1)

    try:
        with open(tmp_raw, encoding="utf-8") as f:
            offers = json.load(f)
        log(f"      {len(offers)} offres brutes en {time.time() - t0:.0f}s")
    except Exception as e:
        log(f"❌ Lecture jobs_raw.json: {e}")
        sys.exit(1)

    if not offers:
        log("⚠️  Aucune offre collectée. Causes possibles :")
        log("   1. Sources vides ou inaccessibles (vérifier /tmp/scrape_log.txt)")
        log("   2. Termes trop spécifiques dans primary_terms")
        log("   3. Problème réseau WSL (tester: curl -s https://httpbin.org/get)")
        sys.exit(0)

    # ── Scoring et export ──────────────────────────────────────────────────────
    log(f"\n[4/4] Scoring + export → {out_dir}/")
    ok = run_scorer(tmp_raw, active_profile_path, out_dir)
    if not ok:
        log("❌ Scoring échoué")
        sys.exit(1)

    # ── Plan de recherche manuelle (si résultats insuffisants) ────────────────
    manual_plan = run_manual_search_plan(active_profile_path, out_dir)

    # ── Sentinel done.flag ─────────────────────────────────────────────────────
    today = datetime.date.today().strftime("%d-%m-%Y")
    flag_path = Path(out_dir) / "done.flag"
    flag = {
        "timestamp":        datetime.datetime.now().isoformat(timespec="seconds"),
        "candidate":        m.get("name", "?"),
        "domain":           domain,
        "offers_collected": len(offers),
        "out_dir":          out_dir,
        "csv":              f"{today}_output.csv",
        "md":               f"{today}_output.md",
        "summary":          f"{today}_summary.json",
        "manual_search_plan": manual_plan,
        "pipeline_seconds": round(time.time() - t0),
    }
    with open(flag_path, "w", encoding="utf-8") as f:
        json.dump(flag, f, ensure_ascii=False, indent=2)

    log(f"\n✅ Pipeline terminé — {len(offers)} offres traitées en {flag['pipeline_seconds']}s")
    log(f"🏁 Sentinel : {flag_path}")
    log(f"   CSV : {out_dir}/{flag['csv']}")
    log(f"   MD  : {out_dir}/{flag['md']}")
    if manual_plan:
        log(f"   Plan recherche manuelle : {out_dir}/{manual_plan}")


if __name__ == "__main__":
    main()
