#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste le ROUTAGE du menu du lanceur, touche par touche, sans rien changer.

On fait une copie du .bat dans laquelle tout ce qui a un effet est neutralise :
  - "choice" est remplace par un faux choix qui reproduit son code de sortie
    a partir du premier argument ;
  - les appels a powershell deviennent un echo APPEL ;
  - "start" devient un echo OUVERTURE ;
  - "pause" devient un no-op ;
  - chaque "goto menu" pointe vers la fin, pour ne faire qu'un seul tour.

On verifie ainsi que chaque touche arrive bien sur la bonne branche, sans
deploiement reel ni ouverture de fenetre. Les scripts PowerShell sont, eux,
testes pour de vrai separement.

Le test est ecrit en Python et non en bash : entre Git Bash, cmd.exe et un
nom de dossier utilisateur accentue, le calcul des guillemets devient un
champ de mines. Python appelle directement le .bat, sans quoting.

Usage :  python tester-lanceur.py
"""
from __future__ import print_function

import io
import os
import re
import subprocess
import sys
import tempfile

BAT = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW", "Lanceur-BOTW.bat")
TOUCHES = "123456789abcdefgh0"

ATTENDU = [
    ("1", "-Profile combo"),
    ("2", "-Profile flo"),
    ("3", "-Profile secondwind"),
    ("4", "-Profile boost"),
    ("5", "-Profile sur"),
    ("6", "Choix-Mods.ps1"),
    ("7", "Sauvegardes-BOTW.ps1"),
    ("8", "Coop-2Joueurs.ps1"),
    ("9", "Panel-Profils.ps1"),
    ("a", "Graphismes-BOTW.ps1"),
    ("b", "Verifier-Tout.ps1"),
    ("c", "matrice.py"),
    ("d", "OUVERTURE"),
    ("e", "OUVERTURE"),
    ("f", "botw.py"),
    ("g", "botw.py"),
    ("h", "botw.py"),
    ("0", None),                      # quitter : aucun appel attendu
]


def fabriquer(src, dst):
    t = io.open(src, encoding="ascii").read()
    # "call :fauxchoix %1" et non "call :fauxchoix" : dans une sous-routine,
    # %1 designe les arguments DE LA SOUS-ROUTINE, pas ceux du script.
    t = re.sub(r"(?m)^choice .*$", "call :fauxchoix %1", t)
    t = re.sub(r"(?m)^pause\s*$", "rem pause", t)
    t = re.sub(r"(?m)^start \"\"", "echo OUVERTURE", t)
    t = t.replace("powershell -NoProfile -ExecutionPolicy Bypass -File", "echo APPEL")
    # Les touches c, f, g, h appellent directement python : on neutralise aussi.
    t = re.sub(r"(?m)^(\s*)python ", r"\1echo APPEL ", t)
    # La touche h pose une question avant d'appeler python : sans terminal, le
    # "set /p" tournerait en boucle. On le transforme en echo.
    t = re.sub(r'(?m)^(\s*)set /p "', r'\1echo REPONSE ', t)
    t = re.sub(r"(?m)^\s*goto menu\s*$", "goto :testfin", t)
    # Piege de cmd : "echo" ne remet pas ERRORLEVEL a 0. Or le faux choice
    # vient de faire "exit /b 5" : les "if errorlevel 1 goto menu" du lanceur
    # seraient donc toujours vrais, et le menu bouclerait a l'infini.
    # "ver > nul" remet ERRORLEVEL a 0, comme le vrai appel PowerShell.
    lignes = []
    for ln in t.split("\n"):
        lignes.append(ln)
        if re.match(r"^\s*echo (APPEL|OUVERTURE)", ln) or re.match(r"^\s*echo APPEL ", ln):
            lignes.append("ver > nul")
    t = "\n".join(lignes)
    t += "\n".join(
        ["", ":testfin", "exit /b 0", "", ":fauxchoix",
         "rem Reproduit le code de sortie de choice /c " + TOUCHES]
        + ['if "%~1"=="{0}" exit /b {1}'.format(c, i + 1)
           for i, c in enumerate(TOUCHES)]
        + ["exit /b %d" % (len(TOUCHES) + 1), ""])
    io.open(dst, "w", encoding="ascii", newline="\r\n").write(t)
    return t


def main():
    if not os.path.isfile(BAT):
        print("Lanceur introuvable : %s" % BAT)
        return 2
    dossier = tempfile.mkdtemp(prefix="test-lanceur-")
    copie = os.path.join(dossier, "Lanceur-BOTW.bat")
    fabriquer(BAT, copie)
    # La touche c cherche Outils\matrice.py : sans ce fichier, la branche
    # affiche "introuvable" et le test croirait a une erreur de routage.
    os.makedirs(os.path.join(dossier, "Outils"))
    io.open(os.path.join(dossier, "Outils", "matrice.py"), "w").write("# stub\n")
    # Les touches f, g, h verifient que le dossier botw existe.
    os.makedirs(os.path.join(dossier, "botw"))
    io.open(os.path.join(dossier, "botw", "botw.py"), "w").write("# stub\n")

    print("=== routage des %d touches ===" % len(TOUCHES))
    print("%-8s %-26s %s" % ("TOUCHE", "ATTENDU", "RESULTAT"))
    ko = 0
    for touche, attendu in ATTENDU:
        p = subprocess.Popen([copie, touche], cwd=dossier,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            sortie = p.communicate(timeout=30)[0].decode("cp1252", "replace")
        except subprocess.TimeoutExpired:
            p.kill()
            sortie = ""
            print("%-8s %-26s ECHEC (le menu ne se ferme pas)"
                  % (touche, attendu if attendu else "sortie"))
            ko += 1
            continue
        if attendu is None:
            # touche 0 : le script doit se terminer sans rien appeler
            if p.returncode == 0 and "APPEL" not in sortie:
                print("%-8s %-26s OK" % (touche, "sortie immediate"))
            else:
                print("%-8s %-26s ECHEC" % (touche, "sortie immediate"))
                ko += 1
            continue
        if attendu in sortie:
            print("%-8s %-26s OK" % (touche, attendu))
        else:
            print("%-8s %-26s ECHEC" % (touche, attendu))
            for ln in sortie.strip().splitlines()[-12:]:
                print("          %s" % ln)
            ko += 1

    try:
        os.remove(copie)
        os.rmdir(dossier)
    except OSError:
        pass
    print("")
    print("Resultat : %d touche(s) en echec sur %d" % (ko, len(TOUCHES) + 1))
    return 0 if ko == 0 else 1


if __name__ == "__main__":
    sys.exit(main())