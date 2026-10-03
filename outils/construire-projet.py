#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble le depot GitHub du projet a partir des fichiers reels.

Plutot que de recopier des fichiers a la main (et d'oublier de les
remettre a jour), ce script rebuild complet le depot depuis les sources
vives :

    ~/Desktop/BOTW          -> lanceur/          (le .bat et les .ps1)
    ~/botw-bcml-work        -> outils/           (les scripts de verification)
    rapports generes        -> docs/

Il ecrase le depot a chaque lancement : le depot ne contient JAMAIS une copie
obsolete, il est toujours-image des fichiers reellement utilises.

Usage :  python construire-projet.py
"""
from __future__ import print_function

import io
import os
import shutil
import subprocess
import sys

RACINE = os.path.expanduser(r"~\botw-bcml-work")
BOTW = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW")
DEPO = os.path.join(RACINE, "botw-lanceur-github")

LANCEUR = ["Lanceur-BOTW.bat", "Set-ProfilUKMM.ps1", "Sauvegardes-BOTW.ps1",
           "Sauvegardes-BOTW.bat", "Graphismes-BOTW.ps1", "Choix-Mods.ps1",
           "Coop-2Joueurs.ps1", "Panel-Profils.ps1", "Verifier-Tout.ps1",
           "LISEZ-MOI.txt", "GUIDE-MODS-BOTW.md"]

OUTILS = ["verifier-profil.py", "conflits.py", "analyse-mods.py", "matrice.py",
          "reparer-manifests.py", "creer-profil.py", "editer-profil.py",
          "tester-lanceur.py", "construire-projet.py"]

RAPPORTS = [("matrice-rapport-complet.md", "combinaisons-testees.md"),
            ("conflits.txt", "conflits-mods.txt"),
            ("analyse-mods.txt", "inventaire-mods.txt")]


def copier(src, dst):
    if not os.path.isfile(src):
        print("   (absent) %s" % os.path.basename(src))
        return False
    shutil.copy2(src, dst)
    return True


def main():
    if os.path.isdir(DEPO):
        # On ne supprime QUE les dossiers generes. README.md, LICENSE,
        # CHANGELOG.md et .gitignore sont ecrits a la main : ils sont
        # preserves.
        for d in ("lanceur", "outils", "docs"):
            shutil.rmtree(os.path.join(DEPO, d), ignore_errors=True)
    for d in ("lanceur", "outils", "docs"):
        os.makedirs(os.path.join(DEPO, d))

    n = 0
    print("lanceur/ :")
    for f in LANCEUR:
        if copier(os.path.join(BOTW, f), os.path.join(DEPO, "lanceur", f)):
            n += 1
    print("outils/ :")
    for f in OUTILS:
        if copier(os.path.join(RACINE, f), os.path.join(DEPO, "outils", f)):
            n += 1
    print("docs/ :")
    for src, dst in RAPPORTS:
        if copier(os.path.join(RACINE, src), os.path.join(DEPO, "docs", dst)):
            n += 1

    # Les .ps1 et le .bat sont livres en ASCII pur, SANS BOM : PowerShell 5.1
    # lit un .ps1 en ANSI, et un BOM se retrouve dans le texte affiche.
    problemes = []
    for base, _d, files in os.walk(DEPO):
        for f in files:
            p = os.path.join(base, f)
            if os.path.splitext(f)[1].lower() in (".ps1", ".bat", ".txt", ".md"):
                with io.open(p, "rb") as fh:
                    tete = fh.read(3)
                if tete[:3] == b"\xef\xbb\xbf":
                    problemes.append(p)
    print("")
    if problemes:
        print("!! BOM detecte dans :")
        for p in problemes:
            print("   %s" % p)
    else:
        print("Aucun BOM : les scripts restent lisibles par PowerShell 5.1.")

    print("")
    print("%d fichiers dans %s" % (n, DEPO))
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())