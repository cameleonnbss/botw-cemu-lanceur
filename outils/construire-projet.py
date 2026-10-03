#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble le depot GitHub du projet a partir des fichiers reels.

Plutot que de recopier des fichiers a la main (et d'oublier de les
remettre a jour), ce script rebuild complet le depot depuis les sources
vives :

    ~/Desktop/BOTW          -> lanceur/          (le .bat et les .ps1)
    ~/botw-bcml-work/botw-tools -> cli/          (le programme botw)
    ~/botw-bcml-work        -> outils/           (les scripts de verification)
    rapports generes        -> docs/

Il ecrase le depot a chaque lancement : le depot ne contient JAMAIS une copie
obsolete, il est toujours image des fichiers reellement utilises.

Usage :  python construire-projet.py
"""
from __future__ import print_function

import io
import os
import shutil
import sys

RACINE = os.path.expanduser(r"~\botw-bcml-work")
BOTW = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW")
CLI = os.path.join(RACINE, "botw-tools")
DEPO = os.path.join(RACINE, "botw-lanceur-github")

LANCEUR = ["Lanceur-BOTW.bat", "Set-ProfilUKMM.ps1", "Sauvegardes-BOTW.ps1",
           "Sauvegardes-BOTW.bat", "Graphismes-BOTW.ps1", "Choix-Mods.ps1",
           "Coop-2Joueurs.ps1", "Panel-Profils.ps1", "Verifier-Tout.ps1",
           "LISEZ-MOI.txt", "GUIDE-MODS-BOTW.md"]

OUTILS = ["verifier-profil.py", "conflits.py", "analyse-mods.py", "matrice.py",
          "reparer-manifests.py", "creer-profil.py", "editer-profil.py",
          "tester-lanceur.py", "construire-projet.py", "maj-bureau.py"]

# Outils qui vivent avec le programme plutot qu'a la racine du chantier.
OUTIFS_DU_CLI = ["maj-bureau.py"]

RAPPORTS = [("matrice-rapport-complet.md", "combinaisons-testees.md"),
            ("conflits.txt", "conflits-mods.txt"),
            ("analyse-mods.txt", "inventaire-mods.txt")]

# Le CLI : la racine, puis deux dossiers entiers.
CLI_FICHIERS = ["botw.py", "botw.bat", "README.md", "README.fr.md"]
CLI_DOSSIERS = ["botw", "locales", "tests", "Outils"]


def copier(src, dst):
    if not os.path.isfile(src):
        print("   (absent) %s" % os.path.basename(src))
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def copier_arbre(src, dst, compte):
    """Copie un dossier en ignorant les __pycache__ et les .pyc."""
    if not os.path.isdir(src):
        print("   (absent) %s" % os.path.basename(src))
        return
    for base, dossiers, files in os.walk(src):
        dossiers[:] = [d for d in dossiers if d != "__pycache__"]
        rel = os.path.relpath(base, src)
        for f in files:
            if f.endswith(".pyc"):
                continue
            cible = os.path.join(dst, f) if rel == "." \
                else os.path.join(dst, rel, f)
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            shutil.copy2(os.path.join(base, f), cible)
            compte[0] += 1


def main():
    if os.path.isdir(DEPO):
        # On ne supprime QUE les dossiers generes. README.md, README.fr.md,
        # LICENSE, CHANGELOG.md et .gitignore sont ecrits a la main : ils sont
        # preserves.
        for d in ("lanceur", "outils", "docs", "cli"):
            shutil.rmtree(os.path.join(DEPO, d), ignore_errors=True)
    for d in ("lanceur", "outils", "docs", "cli"):
        os.makedirs(os.path.join(DEPO, d))

    n = 0
    print("lanceur/ :")
    for f in LANCEUR:
        if copier(os.path.join(BOTW, f), os.path.join(DEPO, "lanceur", f)):
            n += 1
    print("cli/ :")
    compte = [0]
    for f in CLI_FICHIERS:
        if copier(os.path.join(CLI, f), os.path.join(DEPO, "cli", f)):
            n += 1
    for d in CLI_DOSSIERS:
        copier_arbre(os.path.join(CLI, d), os.path.join(DEPO, "cli", d), compte)
    print("   %d fichiers de code et de tests" % compte[0])
    n += compte[0]
    print("outils/ :")
    for f in OUTILS:
        if copier(os.path.join(RACINE, f), os.path.join(DEPO, "outils", f)):
            n += 1
    for f in OUTIFS_DU_CLI:
        if copier(os.path.join(CLI, "Outils", f),
                  os.path.join(DEPO, "outils", f)):
            n += 1
    print("docs/ :")
    for src, dst in RAPPORTS:
        if copier(os.path.join(RACINE, src), os.path.join(DEPO, "docs", dst)):
            n += 1

    # Les .ps1 et le .bat sont livres en ASCII pur, SANS BOM : PowerShell 5.1
    # lit un .ps1 en ANSI, et un BOM se retrouve dans le texte affiche.
    # Les .md et .json du CLI, eux, sont en UTF-8 avec accents : c'est voulu,
    # et Python les lit en UTF-8 explicitement.
    ascii_seulement = (".ps1", ".bat")
    problemes = []
    for base, _d, files in os.walk(DEPO):
        if os.sep + "cli" + os.sep in base + os.sep:
            continue                      # le CLI est UTF-8, c'est voulu
        for f in files:
            p = os.path.join(base, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in (".ps1", ".bat", ".txt", ".md"):
                with io.open(p, "rb") as fh:
                    tete = fh.read(3)
                if tete[:3] == b"\xef\xbb\xbf":
                    problemes.append(p)
            if ext in ascii_seulement:
                with io.open(p, "rb") as fh:
                    data = fh.read()
                if any(c > 127 for c in data):
                    problemes.append(p + "  (accent dans un fichier ASCII)")

    print("")
    if problemes:
        print("!! Problemes :")
        for p in problemes:
            print("   %s" % p)
    else:
        print("Aucun BOM, aucun accent dans les .bat / .ps1 : PowerShell 5.1 "
              "les lit correctement.")

    print("")
    print("%d fichiers dans %s" % (n, DEPO))
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())