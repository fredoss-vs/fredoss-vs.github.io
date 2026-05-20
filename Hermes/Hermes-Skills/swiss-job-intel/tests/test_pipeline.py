#!/usr/bin/env python3
"""
Tests de non-régression — swiss-job-intel v6.0.0

Couvre :
  - Détection d'état Phase 0 (done.flag / profile_cache / rien)
  - Enrichissement ESCO (4 domaines)
  - Scoring générique (profil-dépendant, zéro hardcode)
  - Validation profil avant pipeline
  - Contrat done.flag / summary.json

Usage : python3 tests/test_pipeline.py
"""
from __future__ import annotations
import json, os, sys, tempfile, subprocess, unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS    = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

PASS = 0; FAIL = 0

def ok(label: str) -> None:
    global PASS; PASS += 1
    print(f"  ✅ {label}")

def fail(label: str, detail: str = "") -> None:
    global FAIL; FAIL += 1
    print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))

def run_script(script: str, args: list[str], cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script)] + args,
        capture_output=True, text=True, cwd=cwd or SKILL_ROOT
    )

def make_profile(name, domain, isco_codes, primary_terms, **extra) -> dict:
    p = {
        "name": name, "level": "senior", "domain": domain,
        "isco_major_group": "", "isco_codes": isco_codes,
        "recommended_title": name, "target_roles": [],
        "preferred_locations": ["valais", "vaud"],
        "contract": "CDI", "remote_policy": "", "availability": "",
        "salary_range_chf": [], "languages": ["français"],
        "education_level": "", "hard_skills": [], "soft_skills": [],
        "primary_terms": primary_terms, "exclude_terms": [],
        "_meta": {"name": name, "recommended_title": name,
                  "generated": "2026-05-14", "skill_version": "6.0.0",
                  "source_hash": ""},
    }
    p.update(extra)
    return p

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T1 : Enrichissement ESCO — 4 domaines ──────────────────────────────")

ENRICH_CASES = [
    ("Infirmière ICUS",    "sante",        ["2221"], ["infirmier","soins intensifs"],  (20, 150)),
    ("Maçon chantier",     "construction", ["7111"], ["maçon","béton","chantier"],     (20, 150)),
    ("Viticulteur Valais", "agriculture",  ["6112"], ["viticulteur","vigne","cave"],   (10, 150)),
    ("IT Support",         "it",           ["3512"], ["service desk","ITSM","helpdesk"],(20, 150)),
]

for name, domain, codes, terms, (lo, hi) in ENRICH_CASES:
    profile = make_profile(name, domain, codes, terms)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False); tmp_in = f.name
    tmp_out = tmp_in.replace(".json", "_enriched.json")
    r = run_script("enrich_profile_esco.py", [tmp_in, "--out", tmp_out])
    if os.path.exists(tmp_out):
        enriched = json.loads(Path(tmp_out).read_text(encoding="utf-8"))
        added = len(enriched["primary_terms"]) - len(terms)
        if lo <= added <= hi:
            ok(f"Enrich {name} : {added} termes ajoutés ({lo}–{hi})")
        else:
            fail(f"Enrich {name}", f"{added} termes hors plage [{lo},{hi}]")
        os.unlink(tmp_out)
    else:
        fail(f"Enrich {name}", "fichier de sortie absent")
    os.unlink(tmp_in)

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T2 : Scoring générique (profil-dépendant) ───────────────────────────")

def norm(t):
    t = str(t).lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

def score_offer(offer, profile):
    title = norm(offer.get("title",""))
    text  = title + " " + norm(offer.get("snippet",""))
    loc   = norm(offer.get("location",""))
    s = 0
    for kw in profile["primary_terms"]:
        if norm(kw) in text: s += 4
    for kw in profile["exclude_terms"]:
        if norm(kw) in title: s -= 8
    for p in profile["preferred_locations"]:
        if norm(p) in loc: s += 3; break
    return s

# Un bon match pour un infirmier doit scorer >0, un maçon sur la même offre doit scorer 0
infirmier = make_profile("Test INF", "sante", ["2221"], ["infirmier","soins","urgences"])
macon     = make_profile("Test MAC", "construction", ["7111"], ["maçon","béton","chantier"])
offer_inf = {"title":"Infirmier soins intensifs","snippet":"soins urgences hôpital","location":"sion","date":""}
offer_mac = {"title":"Maçon gros oeuvre","snippet":"béton coffrage chantier","location":"sion","date":""}

s_inf_inf = score_offer(offer_inf, infirmier)
s_inf_mac = score_offer(offer_inf, macon)
s_mac_mac = score_offer(offer_mac, macon)
s_mac_inf = score_offer(offer_mac, infirmier)

if s_inf_inf > 0: ok(f"Offre infirmier scorée positivement par profil infirmier ({s_inf_inf})")
else: fail("Score infirmier/infirmier", f"score={s_inf_inf}")
if s_inf_mac == 0: ok(f"Offre infirmier scorée 0 par profil maçon ({s_inf_mac})")
else: fail("Score infirmier/maçon devrait être 0", f"score={s_inf_mac}")
if s_mac_mac > 0: ok(f"Offre maçon scorée positivement par profil maçon ({s_mac_mac})")
else: fail("Score maçon/maçon", f"score={s_mac_mac}")
if s_mac_inf == 0: ok(f"Offre maçon scorée 0 par profil infirmier ({s_mac_inf})")
else: fail("Score maçon/infirmier devrait être 0", f"score={s_mac_inf}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T3 : score_export.py — refus sans profil ────────────────────────────")

with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump([], f); empty_offers = f.name
r = run_script("score_export.py", [empty_offers])
if r.returncode == 1 and "profil" in r.stderr.lower():
    ok("score_export.py exit 1 sans profil avec message clair")
else:
    fail("score_export.py doit refuser sans profil", f"rc={r.returncode} stderr={r.stderr[:80]}")
os.unlink(empty_offers)

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T4 : scrape_ch_jobs.py — refus sans profil ──────────────────────────")

r = run_script("scrape_ch_jobs.py", [])
if r.returncode == 1 and "profil" in r.stderr.lower():
    ok("scrape_ch_jobs.py exit 1 sans profil avec message clair")
else:
    fail("scrape_ch_jobs.py doit refuser sans profil", f"rc={r.returncode}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T5 : orchestrate.py — validation profil ─────────────────────────────")

bad_profiles = [
    ("sans primary_terms", {"domain":"it","_meta":{"skill_version":"6.0.0"}}),
    ("sans domain",        {"primary_terms":["test"],"_meta":{"skill_version":"6.0.0"}}),
    ("version obsolète",   {"domain":"it","primary_terms":["test"],"_meta":{"skill_version":"5.0.0"}}),
]
for label, bad in bad_profiles:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(bad, f); tmp = f.name
    r = run_script("orchestrate.py", [tmp])
    if r.returncode == 1 and "invalide" in r.stderr.lower():
        ok(f"orchestrate.py rejette profil {label}")
    else:
        fail(f"orchestrate.py devrait rejeter profil {label}", f"rc={r.returncode}")
    os.unlink(tmp)

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T6 : contrat done.flag — champs obligatoires ────────────────────────")

required_flag_fields = ["timestamp","candidate","domain","offers_collected",
                         "out_dir","csv","md","summary","pipeline_seconds"]
# Vérifier dans le code source d'orchestrate.py
src = (SCRIPTS / "orchestrate.py").read_text(encoding="utf-8")
for field in required_flag_fields:
    if f'"{field}"' in src:
        ok(f"done.flag contient le champ '{field}'")
    else:
        fail(f"done.flag manque le champ '{field}'")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T7 : Routing sources — type-based ───────────────────────────────────")

try:
    import yaml
    registry_path = SKILL_ROOT / "source" / "sources_registry.yaml"
    with open(registry_path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    # Vérifier que tous les sources actives ont un type
    sources = registry.get("sources", {})
    for sid, src in sources.items():
        if "type" not in src:
            fail(f"Source '{sid}' sans champ 'type'")
        else:
            ok(f"Source '{sid}' a type='{src['type']}'")

    # Toutes les sources actives sont sélectionnées peu importe le domaine candidat.
    # L'employeur ne définit pas le métier — le tri est au niveau de l'offre.
    sys.path.insert(0, str(SCRIPTS))
    from orchestrate import select_sources, INACTIVE_STATUSES as _INACTIVE

    active_ids = {sid for sid, src in sources.items()
                  if src.get("status", "") not in _INACTIVE}

    for domain in ["it", "sante", "agriculture", "construction", "social"]:
        prof = make_profile(f"Test {domain}", domain, [], [f"terme_{domain}"])
        selected = select_sources(prof, registry)
        sel_ids = {s.get("id") for s in selected}
        if sel_ids == active_ids:
            ok(f"Domaine '{domain}' : toutes les sources actives ({len(selected)}) — collecte large")
        else:
            missing = active_ids - sel_ids
            extra   = sel_ids - active_ids
            fail(f"Domaine '{domain}' : sources incorrectes",
                 f"manquantes={missing} extras={extra}")

    # CIGES est une source active → doit apparaître pour TOUS les domaines,
    # y compris sante, agriculture, construction — l'offre individuelle triera.
    for domain in ["sante", "agriculture", "construction", "it", "social"]:
        prof = make_profile(f"Test {domain}", domain, [], ["terme"])
        sel = select_sources(prof, registry)
        if any(s.get("id") == "ciges" for s in sel):
            ok(f"CIGES inclus pour domaine '{domain}' — tri au scoring, pas à la source")
        else:
            fail(f"CIGES devrait être inclus pour tout profil (domaine='{domain}')")

except ImportError:
    fail("PyYAML non disponible — tests routing skippés", "pip install pyyaml")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T8 : Offre hétérogène — employeur IT, poste admin ───────────────────")

# Un candidat RH qui postule sur une offre admin chez Swisscom doit scorer >0
rh_profile = make_profile(
    "Test RH", "administration", ["1212"],
    ["responsable rh", "gestionnaire rh", "recrutement", "ressources humaines", "paie"],
    hard_skills=["sap hcm", "workday", "gestion du personnel"]
)
offer_rh_at_swisscom = {
    "title": "Responsable RH Suisse romande",
    "snippet": "Gestion des ressources humaines, recrutement, paie, Workday",
    "location": "lausanne",
    "date": "",
    "source": "swisscom_workday",
    "employer": "Swisscom"
}
s = score_offer(offer_rh_at_swisscom, rh_profile)
if s > 0:
    ok(f"Offre admin chez employeur IT scorée positivement par profil RH (score={s})")
else:
    fail("Offre admin chez employeur IT devrait scorer >0 pour profil RH", f"score={s}")

# Un candidat maçon sur la même offre RH doit scorer 0 (pas de match)
s_mac = score_offer(offer_rh_at_swisscom, macon)
if s_mac == 0:
    ok(f"Offre RH scorée 0 par profil maçon — pas de faux positif (score={s_mac})")
else:
    fail("Profil maçon ne devrait pas matcher une offre RH", f"score={s_mac}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T9 : --force-refresh et --force-profile ─────────────────────────────")

import tempfile as _tmp
with _tmp.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    # Créer un profile_cache.json valide
    prof_data = make_profile("Test", "it", ["3512"], ["service desk"])
    (tmpdir / "profile_cache.json").write_text(
        json.dumps(prof_data), encoding="utf-8"
    )
    # Créer un done.flag factice
    results_dir = tmpdir / "results"
    results_dir.mkdir()
    (results_dir / "done.flag").write_text('{"test":true}')

    # --force-refresh : supprime done.flag avant de relancer le pipeline
    # Le flag original contenait '{"test":true}' — après --force-refresh il ne peut plus
    # contenir ce contenu (soit absent, soit recréé avec un vrai timestamp)
    original_content = '{"test":true}'
    r = subprocess.run(
        [sys.executable, str(SCRIPTS/"orchestrate.py"),
         str(tmpdir/"profile_cache.json"), "--out", str(results_dir), "--force-refresh"],
        capture_output=True, text=True, cwd=tmpdir
    )
    flag_after = results_dir / "done.flag"
    flag_content = flag_after.read_text() if flag_after.exists() else ""
    if original_content not in flag_content:
        ok("--force-refresh : done.flag original effacé (flag absent ou recréé par le pipeline)")
    else:
        fail("--force-refresh devrait avoir effacé le done.flag original")

    # --force-profile : supprime profile_cache.json et quitte proprement (exit 0)
    (tmpdir / "profile_cache.json").write_text(json.dumps(prof_data), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPTS/"orchestrate.py"),
         str(tmpdir/"profile_cache.json"), "--force-profile"],
        capture_output=True, text=True, cwd=tmpdir
    )
    if r.returncode == 0 and not (tmpdir/"profile_cache.json").exists():
        ok("--force-profile : cache supprimé, exit 0 propre")
    else:
        fail("--force-profile devrait supprimer le cache et exit 0",
             f"rc={r.returncode} cache_exists={(tmpdir/'profile_cache.json').exists()}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T11 : Offres cross-secteur — l'employeur ne définit pas le métier ───")

# Profils cross-secteur
cyber_profile = make_profile(
    "Test Cyber", "it", ["2512"],
    ["cybersécurité", "sécurité informatique", "pentest", "SOC", "SIEM"],
    hard_skills=["splunk", "sentinel", "iso27001"]
)
nettoyage_profile = make_profile(
    "Test Nettoyage", "services", ["9112"],
    ["nettoyage", "entretien", "propreté", "agent de service"],
)
rh_hospitalier = make_profile(
    "Test RH", "administration", ["1212"],
    ["ressources humaines", "recrutement", "paie", "gestion du personnel"],
    hard_skills=["sap hcm", "workday"]
)

# Offre cyber dans un hôpital (CHUV, HUG...) → doit scorer >0 pour profil cyber
offer_cyber_hopital = {
    "title": "Analyste cybersécurité SOC",
    "snippet": "Surveillance SIEM, détection d'incidents, pentest, ISO27001, Splunk",
    "location": "lausanne", "date": "", "source": "chuv", "employer": "CHUV"
}
s = score_offer(offer_cyber_hopital, cyber_profile)
if s > 0:
    ok(f"Offre cyber dans un hôpital → profil cyber score={s} (employeur ≠ domaine)")
else:
    fail("Offre cyber dans un hôpital devrait scorer >0 pour profil cyber", f"score={s}")

# Même offre ne doit pas scorer pour profil nettoyage
s_nett = score_offer(offer_cyber_hopital, nettoyage_profile)
if s_nett == 0:
    ok(f"Offre cyber dans un hôpital → profil nettoyage score=0 (pas de faux positif)")
else:
    fail("Profil nettoyage ne doit pas matcher une offre cyber", f"score={s_nett}")

# Offre RH dans une institution de recherche → doit scorer >0 pour profil RH
offer_rh_epfl = {
    "title": "Responsable des ressources humaines",
    "snippet": "Recrutement, gestion du personnel, paie, SAP HCM, Workday, contrats",
    "location": "lausanne", "date": "", "source": "epfl", "employer": "EPFL"
}
s = score_offer(offer_rh_epfl, rh_hospitalier)
if s > 0:
    ok(f"Offre RH à l'EPFL → profil RH score={s} (institution recherche ≠ obstacle)")
else:
    fail("Offre RH à l'EPFL devrait scorer >0 pour profil RH", f"score={s}")

# Offre nettoyage / conciergerie dans une structure IT → profil nettoyage score >0
offer_nettoyage_ciges = {
    "title": "Agent de nettoyage et entretien",
    "snippet": "Entretien des locaux, propreté, nettoyage bureaux et salles de cours",
    "location": "sion", "date": "", "source": "ciges", "employer": "CIGES"
}
s = score_offer(offer_nettoyage_ciges, nettoyage_profile)
if s > 0:
    ok(f"Offre nettoyage chez CIGES (école IT) → profil nettoyage score={s}")
else:
    fail("Offre nettoyage chez un employeur IT devrait scorer >0 pour profil nettoyage", f"score={s}")

# Même offre nettoyage → 0 pour profil cyber
s_cyber = score_offer(offer_nettoyage_ciges, cyber_profile)
if s_cyber == 0:
    ok(f"Offre nettoyage chez CIGES → profil cyber score=0 (pas de faux positif)")
else:
    fail("Profil cyber ne doit pas matcher une offre de nettoyage", f"score={s_cyber}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T10 : --sources respecté par scrape_ch_jobs.py ──────────────────────")

# Liste vide → aucune source connue → toutes les sources doivent être ignorées
# (test réseau-indépendant : le scraper ne tente aucune connexion)
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump([], f); tmp_sel = f.name

with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump(make_profile("Test IT", "it", ["3512"], ["service desk"]), f, ensure_ascii=False)
    tmp_prof = f.name

r = run_script("scrape_ch_jobs.py", [tmp_prof, "--sources", tmp_sel])
ignored = r.stderr.count("ignoré (non sélectionné)")
try:
    out_offers = json.loads(r.stdout) if r.stdout.strip() else []
    if ignored >= 4 and isinstance(out_offers, list) and len(out_offers) == 0:
        ok(f"--sources [] : {ignored} sources ignorées, output []")
    else:
        fail("--sources [] devrait ignorer toutes les sources",
             f"ignored={ignored} offers={len(out_offers) if isinstance(out_offers, list) else '?'}")
except Exception as e:
    fail("--sources [] : output JSON invalide", str(e)[:80])

os.unlink(tmp_sel)
os.unlink(tmp_prof)

# Liste avec une seule source → les 3 autres doivent être ignorées
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump([{"id": "admin_federal"}], f); tmp_sel2 = f.name

with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump(make_profile("Test IT", "it", ["3512"], ["service desk"]), f, ensure_ascii=False)
    tmp_prof2 = f.name

r2 = run_script("scrape_ch_jobs.py", [tmp_prof2, "--sources", tmp_sel2])
ignored2 = r2.stderr.count("ignoré (non sélectionné)")
try:
    import yaml as _yaml
    _reg = _yaml.safe_load((SKILL_ROOT / "source" / "sources_registry.yaml").read_text(encoding="utf-8"))
    from orchestrate import INACTIVE_STATUSES as _INACT2
    _active_ids2 = {sid for sid, src in _reg.get("sources", {}).items()
                    if src.get("status", "") not in _INACT2}
    expected_ignored2 = len(_active_ids2) - 1
except Exception:
    expected_ignored2 = 6  # fallback : 7 sources actives - 1
if ignored2 == expected_ignored2:
    ok(f"--sources [admin_federal] : exactement {expected_ignored2} autres sources ignorées")
else:
    fail(f"--sources [admin_federal] devrait ignorer {expected_ignored2} sources", f"ignorées={ignored2}")

os.unlink(tmp_sel2)
os.unlink(tmp_prof2)

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T12 : Plan de recherche manuelle ────────────────────────────────────")

import tempfile as _tmp2

# Cas 1 : summary avec tier_a=0, tier_b=0 → plan doit être généré
with _tmp2.TemporaryDirectory() as out_dir:
    out_dir = Path(out_dir)
    prof = make_profile("Secrétaire communale", "administration", ["2422"],
                        ["secrétaire communal", "administration communale", "commune"],
                        target_roles=["Secrétaire municipal", "Greffier communal"],
                        recommended_title="Secrétaire communale / municipale")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False); tmp_prof = f.name
    # summary avec 0 Tier A/B
    summary_empty = {"tier_a": 0, "tier_b": 0, "tier_c": 1, "total": 1,
                     "candidate": "Secrétaire communale", "domain": "administration",
                     "top_offers": [], "top_missing": [], "sources": []}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(summary_empty, f); tmp_sum = f.name

    r = run_script("manual_search_plan.py", [tmp_prof, tmp_sum, "--out", str(out_dir)])
    import datetime as _dt
    today_str = _dt.date.today().strftime("%d-%m-%Y")
    plan_json = out_dir / f"{today_str}_manual_search_plan.json"
    plan_md   = out_dir / f"{today_str}_manual_search_plan.md"

    if r.returncode == 0 and plan_json.exists() and plan_md.exists():
        plan = json.loads(plan_json.read_text(encoding="utf-8"))
        ok(f"Plan généré (tier_a=0,tier_b=0) : {len(plan['queries'])} requêtes · {len(plan['portals'])} portails")
    else:
        fail("Plan devrait être généré quand tier_a=0 et tier_b=0",
             f"rc={r.returncode} json={plan_json.exists()} md={plan_md.exists()}")

    # Vérifier structure du plan
    required_keys = ["candidate", "recommended_title", "domain", "status", "reason",
                     "auto_results", "queries", "portals", "generated"]
    if plan_json.exists():
        plan = json.loads(plan_json.read_text(encoding="utf-8"))
        for k in required_keys:
            if k in plan:
                ok(f"plan.json contient '{k}'")
            else:
                fail(f"plan.json manque '{k}'")
        # Vérifier requêtes P1 (titre recommandé)
        p1 = [q for q in plan["queries"] if q["priority"] == 1]
        if p1:
            ok(f"Plan contient {len(p1)} requête(s) P1 (titres cibles)")
        else:
            fail("Plan devrait contenir des requêtes P1")
        # Vérifier portails avec URLs pré-générées
        portals_with_urls = [p for p in plan["portals"] if p.get("urls")]
        if portals_with_urls:
            ok(f"{len(portals_with_urls)} portail(s) avec URLs pré-générées")
        else:
            fail("Les portails devraient avoir des URLs pré-générées")

    os.unlink(tmp_prof)
    os.unlink(tmp_sum)

# Cas 2 : summary suffisant (tier_a=3) → plan ne doit PAS être généré
with _tmp2.TemporaryDirectory() as out_dir2:
    out_dir2 = Path(out_dir2)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False); tmp_prof2 = f.name
    summary_ok = {"tier_a": 3, "tier_b": 5, "tier_c": 2, "total": 10,
                  "candidate": "Test", "domain": "it"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(summary_ok, f); tmp_sum2 = f.name

    r2 = run_script("manual_search_plan.py", [tmp_prof2, tmp_sum2, "--out", str(out_dir2)])
    plan_json2 = out_dir2 / f"{today_str}_manual_search_plan.json"
    if r2.returncode == 0 and not plan_json2.exists():
        ok("Plan non généré quand résultats suffisants (tier_a=3)")
    else:
        fail("Plan ne devrait pas être généré si tier_a>0 et total≥5",
             f"rc={r2.returncode} exists={plan_json2.exists()}")
    os.unlink(tmp_prof2)
    os.unlink(tmp_sum2)

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T13 : _recency_bonus — ISO + formats relatifs ───────────────────────")

import datetime as _dt13
sys.path.insert(0, str(SCRIPTS))
from score_export import _recency_bonus, score_offer as se_score, tier as se_tier, GENERIC_SOFT

today_iso    = _dt13.date.today().isoformat()
recent_iso   = (_dt13.date.today() - _dt13.timedelta(days=3)).isoformat()
old_iso      = (_dt13.date.today() - _dt13.timedelta(days=45)).isoformat()
two_weeks    = (_dt13.date.today() - _dt13.timedelta(days=10)).isoformat()

cases_recency = [
    ("today",                              3, "Workday today → +3"),
    ("yesterday",                          3, "Workday yesterday → +3"),
    ("Posted 5 Days Ago",                  3, "Workday 5j → +3"),
    ("Posted 10 Days Ago",                 2, "Workday 10j → +2"),
    ("Posted 25 Days Ago",                 1, "Workday 25j → +1"),
    ("Posted 40 Days Ago",                 0, "Workday 40j → 0"),
    (today_iso,                            3, "ISO aujourd'hui → +3"),
    (recent_iso,                           3, f"ISO {recent_iso} (3j) → +3"),
    (two_weeks,                            2, f"ISO {two_weeks} (10j) → +2"),
    (old_iso,                              0, f"ISO {old_iso} (45j) → 0"),
    (today_iso + "T10:30:00",              3, "ISO datetime sans TZ → +3"),
    (today_iso + "T08:00:00+02:00",        3, "ISO datetime avec TZ → +3"),
    ("",                                   0, "Vide → 0"),
    (None,                                 0, "None → 0"),
]
for raw, expected, label in cases_recency:
    got = _recency_bonus(raw)
    if got == expected:
        ok(f"récence : {label}")
    else:
        fail(f"récence : {label}", f"attendu={expected} obtenu={got}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T14 : Scoring amélioré — titre > snippet, soft skills, pénalité ─────")

# Profil de référence pour T14
prof_secretaire = make_profile(
    "Secrétaire communale", "administration", ["2422"],
    ["secrétaire communal", "administration communale", "commune", "droit administratif"],
    recommended_title="Secrétaire communale / municipale",
    target_roles=["Secrétaire municipal", "Greffier communal"],
    hard_skills=["SAP", "Microsoft Office", "logiciels communaux"],
    soft_skills=["organisation", "communication", "autonomie",  # génériques → ignorés
                 "accueil", "conseil aux citoyens"],             # spécifiques → comptés si titre
    preferred_locations=["valais", "vaud", "sion"],
)

# Offre avec titre fort — doit scorer bien au-dessus d'une offre snippet-only
offer_titre_fort = {
    "title": "Secrétaire municipal / administration communale",
    "snippet": "Gestion administrative de la commune, droit administratif, conseil citoyens",
    "location": "sion", "date": today_iso, "source": "jobup"
}
offer_snippet_only = {
    "title": "Assistant polyvalent",
    "snippet": "secrétaire communal administration communale droit administratif commune",
    "location": "sion", "date": today_iso, "source": "jobup"
}

s_titre, _ = se_score(offer_titre_fort, prof_secretaire)
s_snip, _  = se_score(offer_snippet_only, prof_secretaire)

if s_titre > s_snip:
    ok(f"Titre fort ({s_titre}) > snippet seul ({s_snip}) — hiérarchie respectée")
else:
    fail("Le titre fort devrait scorer plus que le snippet seul",
         f"titre={s_titre} snippet={s_snip}")

if se_tier(s_titre) in ("A", "B"):
    ok(f"Offre titre fort atteint Tier {se_tier(s_titre)} (score={s_titre})")
else:
    fail("Offre avec titre direct devrait atteindre Tier A ou B", f"score={s_titre}")

# Faux positif : offre hors domaine avec soft skills génériques + localisation
# Ne doit pas dépasser le seuil
offer_hors_domaine = {
    "title": "Chef de projet informatique — organisation autonomie communication",
    "snippet": "Projet IT, rigueur, flexibilité, dynamisme, motivation",
    "location": "sion", "date": "", "source": "swisscom_workday"
}
s_fp, matched_fp = se_score(offer_hors_domaine, prof_secretaire)
if se_tier(s_fp) is None:
    ok(f"Faux positif soft skills + localisation rejeté (score={s_fp})")
else:
    fail("Offre hors domaine ne devrait pas passer le seuil via soft skills seuls",
         f"score={s_fp} tier={se_tier(s_fp)} match={matched_fp[:5]}")

# Pénalité : aucun primary_term dans titre + snippet
offer_zero_terms = {
    "title": "Peintre en bâtiment",
    "snippet": "Travaux de peinture, rénovation, finitions",
    "location": "sion", "date": "", "source": "jobup"
}
s_zero, _ = se_score(offer_zero_terms, prof_secretaire)
if se_tier(s_zero) is None:
    ok(f"Pénalité zéro primary_terms appliquée — offre rejetée (score={s_zero})")
else:
    fail("Offre sans aucun primary_term ne devrait pas passer",
         f"score={s_zero} tier={se_tier(s_zero)}")

# Soft skills génériques ne contribuent pas au score
assert "organisation"  in GENERIC_SOFT, "organisation doit être générique"
assert "autonomie"     in GENERIC_SOFT, "autonomie doit être générique"
assert "communication" in GENERIC_SOFT, "communication doit être générique"
ok("GENERIC_SOFT contient les soft skills génériques ciblés")

# Offre récente doit scorer plus haut qu'identique mais ancienne
offer_recente = {"title": "Secrétaire communale", "snippet": "commune", "location": "", "date": today_iso}
offer_ancienne = {"title": "Secrétaire communale", "snippet": "commune", "location": "", "date": old_iso}
s_rec, _ = se_score(offer_recente, prof_secretaire)
s_old, _ = se_score(offer_ancienne, prof_secretaire)
if s_rec > s_old:
    ok(f"Offre récente ({s_rec}) > offre ancienne ({s_old}) — récence ISO active")
else:
    fail("La récente devrait scorer plus haut que l'ancienne", f"rec={s_rec} old={s_old}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T15 : Contrôles multi-profils ───────────────────────────────────────")

import datetime as _datetime2

_today_iso = _datetime2.date.today().isoformat()

# Profils multi-domaines
prof_macon = make_profile(
    "Maçon", "construction", ["7111"],
    ["maçon", "béton", "chantier", "gros oeuvre", "coffrage"],
    hard_skills=["banche", "ferraillage", "enduit"],
)
prof_cyber = make_profile(
    "Analyste cyber", "it", ["2512"],
    ["cybersécurité", "sécurité informatique", "SOC", "pentest", "SIEM"],
    hard_skills=["Splunk", "ISO27001", "incident response"],
)
prof_nettoyage = make_profile(
    "Agent nettoyage", "services", ["9112"],
    ["nettoyage", "entretien", "propreté", "agent de service"],
)
prof_rh = make_profile(
    "Gestionnaire RH", "administration", ["1212"],
    ["ressources humaines", "recrutement", "paie", "gestion du personnel"],
    hard_skills=["SAP HCM", "Workday"],
)

# Offres évidentes par profil
offres_profil = [
    (prof_macon,    {"title": "Maçon gros oeuvre 100%",             "snippet": "béton coffrage chantier banche",       "location": "sion",     "date": _today_iso}, "maçon"),
    (prof_cyber,    {"title": "Analyste cybersécurité SOC",          "snippet": "SIEM Splunk pentest ISO27001",         "location": "lausanne", "date": _today_iso}, "cyber"),
    (prof_nettoyage,{"title": "Agent de nettoyage et entretien",     "snippet": "propreté entretien locaux nettoyage",  "location": "sion",     "date": _today_iso}, "nettoyage"),
    (prof_rh,       {"title": "Responsable ressources humaines",     "snippet": "recrutement paie SAP HCM Workday",    "location": "lausanne", "date": _today_iso}, "rh"),
    (prof_secretaire,{"title": "Secrétaire communal / municipale",   "snippet": "administration communale commune droit administratif", "location": "sion", "date": _today_iso}, "secretaire"),
]
for prof, offer, label in offres_profil:
    s, _ = se_score(offer, prof)
    if se_tier(s) in ("A", "B", "C"):
        ok(f"Profil {label} : offre évidente passe le seuil (score={s} tier={se_tier(s)})")
    else:
        fail(f"Profil {label} : offre évidente devrait passer le seuil", f"score={s}")

# Faux positifs : chaque profil ne doit pas matcher l'offre d'un autre domaine
cross_checks = [
    (prof_macon,     offres_profil[1][1], "maçon",     "cyber"),
    (prof_cyber,     offres_profil[0][1], "cyber",     "maçon"),
    (prof_nettoyage, offres_profil[3][1], "nettoyage", "rh"),
    (prof_rh,        offres_profil[2][1], "rh",        "nettoyage"),
]
for prof, offer, prof_label, offer_label in cross_checks:
    s, _ = se_score(offer, prof)
    if se_tier(s) is None:
        ok(f"Profil {prof_label} ne matche pas offre {offer_label} (score={s})")
    else:
        fail(f"Profil {prof_label} ne devrait pas matcher offre {offer_label}",
             f"score={s} tier={se_tier(s)}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n── T16 : URLs JSON-LD — fallback page détail ──────────────────────────")

scraper_src = (SCRIPTS / "scrape_ch_jobs.py").read_text(encoding="utf-8")

if "def _coerce_url(" in scraper_src:
    ok("scrape_ch_jobs.py normalise les variantes JSON-LD d'URL")
else:
    fail("Le helper _coerce_url devrait exister dans scrape_ch_jobs.py")

if 'from_jsonld(ld, "jobup", fallback_url=detail_url)' in scraper_src:
    ok("Jobup transmet l'URL de détail comme fallback")
else:
    fail("Jobup devrait transmettre detail_url à from_jsonld()")

if 'from_jsonld(ld, "jobs_ch", fallback_url=detail_url)' in scraper_src:
    ok("Jobs.ch transmet l'URL de détail comme fallback")
else:
    fail("Jobs.ch devrait transmettre detail_url à from_jsonld()")

if 'from_jsonld(ld, "ansam", fallback_url=url)' in scraper_src:
    ok("ANSAM transmet l'URL de détail comme fallback")
else:
    fail("ANSAM devrait transmettre fallback_url à from_jsonld()")

if 'from_jsonld(ld, "ciges", fallback_url=url)' in scraper_src:
    ok("CIGES transmet l'URL de détail comme fallback")
else:
    fail("CIGES devrait transmettre fallback_url à from_jsonld()")

if '_coerce_url(ld.get("url"' in scraper_src and "url_key" in scraper_src:
    ok("Suissetalent utilise _coerce_url pour la clé de déduplication")
else:
    fail("Suissetalent devrait utiliser _coerce_url pour la clé de déduplication")

# Tests fonctionnels — extraction AST des fonctions pures (sans effets de bord module)
import ast as _ast16
_tree16 = _ast16.parse(scraper_src)
_ns16: dict = {"re": __import__("re"), "json": __import__("json"), "sys": __import__("sys")}
_target16 = {"norm_snippet", "make_offer", "_coerce_url", "from_jsonld"}
for _node16 in _tree16.body:
    if isinstance(_node16, _ast16.FunctionDef) and _node16.name in _target16:
        exec(compile(_ast16.Module(body=[_node16], type_ignores=[]), "<t16>", "exec"), _ns16)
_coerce16   = _ns16["_coerce_url"]
_fromld16   = _ns16["from_jsonld"]

# _coerce_url : 8 variantes
for _label16, _val16, _exp16 in [
    ("string directe",        "https://example.com/1",              "https://example.com/1"),
    ("dict @id",              {"@id": "https://example.com/2"},      "https://example.com/2"),
    ("dict url",              {"url": "https://example.com/3"},      "https://example.com/3"),
    ("dict id",               {"id":  "https://example.com/4"},      "https://example.com/4"),
    ("liste de strings",      ["https://example.com/5", "other"],   "https://example.com/5"),
    ("liste de dicts @id",    [{"@id": "https://example.com/6"}],   "https://example.com/6"),
    ("chaîne vide",           "",                                    ""),
    ("None → vide",           None,                                  ""),
]:
    _got16 = _coerce16(_val16)
    if _got16 == _exp16:
        ok(f"_coerce_url {_label16}")
    else:
        fail(f"_coerce_url {_label16}", f"attendu {_exp16!r}, obtenu {_got16!r}")

# from_jsonld : 6 variantes URL
_fb = "https://fallback.example.com/job"
for _label16, _ld16, _kw16, _exp16 in [
    ("fallback_url quand url absent",       {"title": "Poste"},                                     {"fallback_url": _fb}, _fb),
    ("url string prioritaire sur fallback", {"title": "Poste", "url": "https://ld.ex/1"},           {"fallback_url": _fb}, "https://ld.ex/1"),
    ("url dict @id",                        {"title": "Poste", "url": {"@id": "https://ld.ex/2"}},  {"fallback_url": _fb}, "https://ld.ex/2"),
    ("mainEntityOfPage string",             {"title": "Poste", "mainEntityOfPage": "https://mep.ex/3"}, {}, "https://mep.ex/3"),
    ("mainEntityOfPage liste @id",          {"title": "Poste", "mainEntityOfPage": [{"@id": "https://mep.ex/4"}, {"@id": "other"}]}, {}, "https://mep.ex/4"),
    ("aucune URL disponible → vide",        {"title": "Poste"},                                     {}, ""),
]:
    _got16 = _fromld16(_ld16, "test", **_kw16)["url"]
    if _got16 == _exp16:
        ok(f"from_jsonld {_label16}")
    else:
        fail(f"from_jsonld {_label16}", f"attendu {_exp16!r}, obtenu {_got16!r}")

# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  Résultat : {PASS} ✅  {FAIL} ❌  ({PASS+FAIL} tests)")
if FAIL > 0:
    sys.exit(1)
