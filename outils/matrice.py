#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'essai : teste des COMBINAISONS de mods de bout en bout.

Pour chaque combinaison, on fait exactement ce que fait le lanceur quand tu
appuies sur une touche :

    1. un profil UKMM jetable est cree avec les mods demandes
    2. l'ordre de fusion est ecrit (load_order)
    3. Set-ProfilUKMM.ps1 est appele : c'est le vrai code du lanceur
       (remerge + deploy + liens durs + pack de textes FR + rules.txt)
    4. verifier-profil.py verifie que chaque fichier declare par chaque mod
       se retrouve tel quel dans merged/ ET dans le pack deploye
    5. le profil jetable est supprime (place disque limitee : 14 Go libres)

Rien n'est simule : c'est la chaine complete qui tourne a chaque essai.

PIEGES CONNUS, GERES ICI
------------------------
- %APPDATA%\\ukmm\\settings.yml contient deploy_config.auto: true. Donc CHAQUE
  remerge deploie automatiquement le profil ACTIF. On positionne donc le
  profil actif sur le profil jetable avant de merger, sinon on ecrase le
  deploiement du profil du joueur.
- UKMM n'installe un mod que dans le profil ACTIF : "install <zip> <profil>"
  ecrit en realite dans le profil actif.
- A la fin, on redeploie le profil du joueur, sinon le pack graphique de Cemu
  contient le dernier profil teste.

Usage :
    python matrice.py solo        # chaque mod seul
    python matrice.py paires      # tous les couples
    python matrice.py cumul       # constructions cumulatives
    python matrice.py presets     # les profils reels du lanceur
    python matrice.py tout
    python matrice.py --liste     # affiche les suites sans lancer
"""
from __future__ import print_function

import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

LOCAL = os.environ["LOCALAPPDATA"]
APPDATA = os.environ["APPDATA"]
# Le dossier du script, ou il soit : le banc doit fonctionner aussi bien depuis
# le dossier de travail que depuis Outils\ du dossier de jeu du Bureau.
RACINE = os.path.dirname(os.path.abspath(__file__))
BOTW = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW")
UKMM = os.path.join(os.path.expanduser("~"), "Tools", "UKMM", "ukmm.exe")
PROFILES = os.path.join(LOCAL, "ukmm", "wiiu", "profiles")
STOCK = os.path.join(LOCAL, "ukmm", "wiiu", "mods")
SETTINGS = os.path.join(APPDATA, "ukmm", "settings.yml")
DEPLOY = os.path.join(APPDATA, "Cemu", "graphicPacks", "BreathOfTheWild_UKMM")
APPLIQUER = os.path.join(BOTW, "Set-ProfilUKMM.ps1")
JETABLE = "_essai"
RAPPORT_JSON = os.path.join(RACINE, "matrice-rapport.json")
RAPPORT_MD = os.path.join(RACINE, "matrice-rapport.md")

# Ordre de priorite canonique, du PLUS FAIBLE au PLUS FORT.
# UKMM empile dans cet ordre et le DERNIER l'emporte pour les fichiers qu'il
# ne sait pas fusionner (crates/uk-mod/src/unpack.rs, build_file).
PRIORITE = [
    "Second_Wind_(core).zip",
    "Second_Wind_-_Shrine_Overhaul.zip",
    "Second_Wind_-_Eventide_Fix.zip",
    "Relics_of_the_Past.zip",
    "Ancient_Weaponry_Mark_II.zip",
    "Hyrule_Warriors_Weapon_Collection.zip",
    "Islands_Expansion_v1.2.zip",
    "Seamless_Warping.zip",
    "More_Korok_Seeds.zip",
    "Korok_Extra_Rewards.zip",
    "10x_Speed_Paraglider_v2.zip",
    "Farore's_Wind.zip",
    "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
    "The_Linkle_Mod_3.0.1.zip",
]

# Mods identifies par leur nom lisible (meta.yml), plus pratique a lire.
def lister_mods():
    import zipfile
    out = []
    for z in sorted(os.listdir(STOCK)):
        if not z.lower().endswith(".zip"):
            continue
        nom = z
        try:
            with zipfile.ZipFile(os.path.join(STOCK, z)) as zf:
                if "meta.yml" in zf.namelist():
                    m = re.search(r"(?m)^name:\s*(.+?)\s*$",
                                  zf.read("meta.yml").decode("utf-8", "replace"))
                    if m:
                        nom = m.group(1).strip(" '\"")
        except Exception:                                        # noqa: BLE001
            pass
        out.append((z, nom))
    return out


# --- pequeno outillage UKMM -------------------------------------------------

def profil_actif():
    with io.open(SETTINGS, encoding="utf-8") as f:
        m = re.search(r"(?m)^\s*profile:\s*(\S+)\s*$", f.read())
    return m.group(1) if m else None


def set_profil_actif(nom):
    with io.open(SETTINGS, encoding="utf-8") as f:
        raw = f.read()
    new = re.sub(r"(?m)^(\s*profile:\s*).*$", lambda m: m.group(1) + nom, raw)
    if new != raw:
        with io.open(SETTINGS, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)


def lire_profile(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        t = f.read()
    mods, lignes, i = {}, t.split("\n"), 0
    while i < len(lignes):
        m = re.match(r"^  (\d+):\s*$", lignes[i])
        if not m:
            i += 1
            continue
        h, nom, zip_, j = m.group(1), "", "", i + 1
        while j < len(lignes) and not re.match(r"^  \d+:\s*$", lignes[j]) \
                and not re.match(r"^\S", lignes[j]):
            nm = re.match(r"^\s+name: (.+?)\s*$", lignes[j])
            zp = re.match(r"^\s+path: .*\\([^\\\r\n]+)\s*$", lignes[j])
            if nm:
                nom = nm.group(1)
            if zp:
                zip_ = zp.group(1)
            j += 1
        mods[h] = (nom, zip_)
        i = j
    lo = re.search(r"load_order:\n((?:- \d+\n?)+)", t)
    ordre = re.findall(r"- (\d+)", lo.group(1)) if lo else []
    return mods, ordre


def creer_profil_jetable():
    d = os.path.join(PROFILES, JETABLE)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "merged"))
    with io.open(os.path.join(d, "profile.yml"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write("mods: {}\nload_order: []\n")
    return d


def supprimer_profil_jetable():
    shutil.rmtree(os.path.join(PROFILES, JETABLE), ignore_errors=True)


def installer(zips):
    """Installe les zips dans le profil jetable. -> (installes, echecs)"""
    set_profil_actif(JETABLE)
    ok, ko = [], []
    for z in zips:
        r = subprocess.run([UKMM, "install", os.path.join(STOCK, z), JETABLE],
                           capture_output=True, text=True, errors="replace")
        (ok if r.returncode == 0 else ko).append(z)
    return ok, ko


def ecrire_load_order():
    p = os.path.join(PROFILES, JETABLE, "profile.yml")
    mods, _ = lire_profile(p)
    rang = {}
    for z in PRIORITE:
        for h, (_n, zp) in mods.items():
            if zp == z:
                rang[zp] = len(rang)
    restants = [zp for _h, (_n, zp) in mods.items() if zp not in rang]
    ordre = []
    for zp in PRIORITE + sorted(restants):
        for h, (_n, z) in mods.items():
            if z == zp:
                ordre.append(h)
                break
    with io.open(p, encoding="utf-8") as f:
        t = f.read()
    corps = "load_order:\n" + "".join("- %s\n" % h for h in ordre)
    t = re.sub(r"load_order:\n(?:- \d+\n?)+", corps, t)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    return [mods[h][0] for h in ordre]


def compter(racine):
    n = 0
    for _b, _d, files in os.walk(racine):
        n += len(files)
    return n


def verifier():
    """Reutilise verifier-profil.py. -> (ok, texte)"""
    r = subprocess.run([sys.executable,
                        os.path.join(RACINE, "verifier-profil.py"), JETABLE],
                       capture_output=True, text=True, errors="replace")
    return r.returncode == 0, r.stdout + r.stderr


def appliquer(profil):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", APPLIQUER, "-Profile", profil],
                       capture_output=True, text=True, errors="replace")
    return r.returncode, r.stdout + r.stderr


# --- un essai ---------------------------------------------------------------

def essai(nom, zips):
    t0 = time.time()
    res = {"nom": nom, "mods": [], "ok": False, "code": None, "duree": 0,
           "note": "", "fichiers": 0, "deployes": 0, "echec_install": []}
    print("  -> %s" % nom, flush=True)
    try:
        creer_profil_jetable()
        ok, ko = installer(zips)
        res["echec_install"] = ko
        if not ok:
            res["note"] = "aucun mod installe"
            return res
        res["mods"] = ecrire_load_order()
        code, sortie = appliquer(JETABLE)
        res["code"] = code
        if code != 0:
            res["note"] = "deploiement refuse (code %s)" % code
            for ln in sortie.strip().splitlines()[-6:]:
                print("       %s" % ln, flush=True)
            return res
        merged = os.path.join(PROFILES, JETABLE, "merged")
        res["fichiers"] = compter(merged)
        res["deployes"] = compter(DEPLOY) - 1          # -1 : rules.txt
        ok, texte = verifier()
        res["ok"] = ok
        if not ok:
            res["note"] = "verification incomplete"
            for ln in texte.splitlines():
                if ln.strip().startswith("!!") or "manquant" in ln:
                    print("       %s" % ln.strip(), flush=True)
        elif res["deployes"] != res["fichiers"]:
            res["note"] = ("deploiement incoherent : %d deployes pour %d fusionnes"
                           % (res["deployes"], res["fichiers"]))
    except Exception as exc:                                     # noqa: BLE001
        res["note"] = "erreur : %r" % (exc,)
    finally:
        supprimer_profil_jetable()
    res["duree"] = round(time.time() - t0, 1)
    print("     %s  %d fichiers, %s s  %s"
          % ("OK " if res["ok"] else "ECHEC", res["fichiers"],
             res["duree"], res["note"]), flush=True)
    return res


# --- les suites -------------------------------------------------------------

def zips_de(noms):
    z = dict((nom, zp) for zp, nom in lister_mods())
    return [z[n] for n in noms if n in z]


def suite_solo():
    out = []
    for zp, nom in lister_mods():
        out.append(("SEUL : %s" % nom, [zp]))
    return out


def suite_paires():
    mods = [(zp, nom) for zp, nom in lister_mods()
            if zp != "Second_Wind_(core).zip"]
    out = []
    for i in range(len(mods)):
        for j in range(i + 1, len(mods)):
            out.append(("%s + %s" % (mods[i][1], mods[j][1]),
                        [mods[i][0], mods[j][0]]))
    return out


def suite_sw():
    coeurs = ("Second_Wind_(core).zip",
              "Second_Wind_-_Shrine_Overhaul.zip",
              "Second_Wind_-_Eventide_Fix.zip")
    out = []
    for zp, nom in lister_mods():
        if zp not in coeurs:
            out.append(("Second Wind + %s" % nom, ["Second_Wind_(core).zip", zp]))
    return out


def suite_cumul():
    base = ["Second_Wind_(core).zip",
            "Second_Wind_-_Shrine_Overhaul.zip",
            "Second_Wind_-_Eventide_Fix.zip"]
    suite = []
    for zp, nom in lister_mods():
        if zp in base:
            continue
        suite.append(("Second Wind + %s" % nom, base + [zp]))
    return suite


def suite_presets():
    """(libelle, None, nom du profil reel a tester).

    On enchaine tous les profils réellement présents, pas une liste figee :
    ajouter un profil dans le panneau le fait entrer dans les tests tout
    seul. Les profils techniques et vides sont ignores.
    """
    out = []
    if not os.path.isdir(PROFILES):
        return out
    for nom in sorted(os.listdir(PROFILES)):
        if nom.startswith("_") or nom == "Default":
            continue
        p = os.path.join(PROFILES, nom, "profile.yml")
        if not os.path.isfile(p):
            continue
        with io.open(p, encoding="utf-8") as f:
            n = len(re.findall(r"(?m)^      name: ", f.read()))
        if n == 0:
            continue
        out.append(("PRESET %-12s (%d mods)" % (nom, n), None, nom))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    suites = {"solo": suite_solo, "paires": suite_paires, "sw": suite_sw,
              "cumul": suite_cumul, "presets": suite_presets}
    if "--liste" in sys.argv:
        for nom, f in suites.items():
            print("%-10s %d essais" % (nom, len(f())))
        return 0
    if not args:
        args = ["solo"]
    if "tout" in args:
        args = ["solo", "paires", "sw", "cumul", "presets"]

    if os.path.isdir(RAPPORT_JSON):
        os.remove(RAPPORT_JSON)
    avant = profil_actif()
    print("Profil actif avant les essais : %s" % avant, flush=True)
    if _process_ouvert("Cemu") or _process_ouvert("ukmm"):
        print("!! Cemu ou UKMM est ouvert : ferme-les avant de lancer la matrice.")
        return 2

    resultats = []
    t0 = time.time()
    for nom_suite in args:
        essais = suites[nom_suite]()
        print("\n=== SUITE %s : %d essais ===" % (nom_suite, len(essais)),
              flush=True)
        for essai_item in essais:
            nom, zips = essai_item[0], essai_item[1]
            if zips is None:            # preset : on teste le profil reel
                res = tester_preset(nom, essai_item[2])
            else:
                res = essai(nom, zips)
            res["suite"] = nom_suite
            resultats.append(res)
            with io.open(RAPPORT_JSON, "w", encoding="utf-8") as f:
                json.dump(resultats, f, indent=1)

    print("\n=== BILAN (%.1f min) ===" % ((time.time() - t0) / 60.0))
    for s in args:
        sous = [r for r in resultats if r["suite"] == s]
        bons = len([r for r in sous if r["ok"]])
        print("  %-9s %2d/%2d OK" % (s, bons, len(sous)))
    echecs = [r for r in resultats if not r["ok"]]
    if echecs:
        print("\n  Echecs :")
        for r in echecs:
            print("   - [%s] %s  -> %s" % (r["suite"], r["nom"], r["note"]))
    ecrire_markdown(resultats)

    print("\nOn remet le profil '%s' en place..." % avant)
    set_profil_actif(avant)
    code = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", APPLIQUER, "-Profile", avant],
        capture_output=True, text=True, errors="replace").returncode
    print("Profil '%s' redeploye (code %s)" % (avant, code))
    return 0


def _process_ouvert(nom):
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s.exe" % nom],
                       capture_output=True, text=True, errors="replace")
    return nom.lower() in (r.stdout or "").lower()


def tester_preset(nom, vrai):
    t0 = time.time()
    res = {"nom": nom, "mods": [], "ok": False, "code": None, "duree": 0,
           "note": "", "fichiers": 0, "deployes": 0, "echec_install": []}
    avant = profil_actif()
    print("  -> %s" % nom, flush=True)
    try:
        set_profil_actif(vrai)
        p = os.path.join(PROFILES, vrai, "profile.yml")
        mods, ordre = lire_profile(p)
        res["mods"] = [mods[h][0] for h in ordre] if ordre else \
                      [v[0] for v in mods.values()]
        if len(ordre) != len(mods):
            res["note"] = ("load_order incoherent : %d entrees pour %d mods"
                           % (len(ordre), len(mods)))
        code, sortie = appliquer(vrai)
        res["code"] = code
        if code != 0:
            res["note"] = "deploiement refuse (code %s)" % code
            for ln in sortie.strip().splitlines()[-6:]:
                print("       %s" % ln, flush=True)
            return res
        merged = os.path.join(PROFILES, vrai, "merged")
        res["fichiers"] = compter(merged)
        res["deployes"] = compter(DEPLOY) - 1
        r = subprocess.run([sys.executable,
                            os.path.join(RACINE, "verifier-profil.py"), vrai],
                           capture_output=True, text=True, errors="replace")
        res["ok"] = r.returncode == 0
        if not res["ok"]:
            res["note"] = "verification incomplete"
            for ln in (r.stdout + r.stderr).splitlines():
                if ln.strip().startswith("!!") or "manquant" in ln:
                    print("       %s" % ln.strip(), flush=True)
        elif res["deployes"] != res["fichiers"]:
            res["note"] = ("deploiement incoherent : %d deployes pour %d fusionnes"
                           % (res["deployes"], res["fichiers"]))
    finally:
        set_profil_actif(avant)
    res["duree"] = round(time.time() - t0, 1)
    print("     %s  %d fichiers, %s s  %s"
          % ("OK " if res["ok"] else "ECHEC", res["fichiers"],
             res["duree"], res["note"]), flush=True)
    return res


def ecrire_markdown(resultats):
    L = ["# Combinaisons de mods testees", "",
         "Chaque ligne = une fusion UKMM complete, un deploiement reel vers Cemu,",
         "et une verification fichier par fichier de ce que chaque mod fourni.",
         "", "| Combinaison | Suite | Mods | Fichiers fusionnes | Deployes | Duree | Resultat |",
         "|---|---|---|---|---|---|---|"]
    for r in resultats:
        L.append("| %s | %s | %d | %d | %d | %.0f s | %s |"
                 % (r["nom"], r["suite"], len(r["mods"]), r["fichiers"],
                    r["deployes"], r["duree"],
                    "OK" if r["ok"] else "ECHEC - " + r["note"]))
    L.append("")
    L.append("Total : %d essais, %d reussis, %d echecs."
             % (len(resultats), len([r for r in resultats if r["ok"]]),
                len([r for r in resultats if not r["ok"]])))
    with io.open(RAPPORT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("Rapport : %s" % RAPPORT_MD)


if __name__ == "__main__":
    sys.exit(main())