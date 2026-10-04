#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Installe le lanceur BOTW sur cette machine, de bout en bout.

Le projet livre un dossier `lanceur/` (les .bat et .ps1) et un programme
`cli/` (l'outil en ligne de commande). Les deux vont dans un meme dossier de
bureau, `%USERPROFILE%\\Desktop\\BOTW`, et se parlent par un chemin relatif :
c'est ce qui rend l'ensemble transportable sur un autre poste.

Ce script fait TOUT ce qu'il faut, dans le bon ordre, et dit ce qu'il fait :

    1. il verifie Python 3.8+, et le signale clairement sinon ;
    2. il copie `lanceur/` et `cli/` vers le dossier de bureau ;
    3. il controle octet par octet que la copie est exacte (MD5), car une
       copie a moitie faite produit un lanceur qui semble marcher et qui
       execute du code vieux de trois semaines - la panne la plus invisible
       du projet ;
    4. il verifie les contraintes Windows sur les fichiers executes
       (ASCII, sans BOM, CRLF), car PowerShell 5.1 lit un .ps1 sans BOM en
       ANSI et refuse les accents ;
    5. il verifie UKMM et Cemu, et dit quoi installer s'ils manquent ;
    6. il n'ecrit JAMAIS dans les sauvegardes ni dans les mods.

Il ne supprime rien non plus : une re-installation par-dessus une
installation existante ne perd aucun profil, aucune partie, aucun mod.

Usage :
    python installer.py                 installe vers ~/Desktop/BOTW
    python installer.py --dest D:\\BOTW  installe ailleurs
    python installer.py --check         verifie sans rien ecrire
    python installer.py --shortcut      ajoute le lanceur au demarrage Windows
"""
from __future__ import print_function

import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
LANCEUR = os.path.join(RACINE, "lanceur")
CLI = os.path.join(RACINE, "cli")

# Le lanceur parle au CLI par `%~dp0botw\\botw.py`. On livre donc le CLI dans
# un sous-dossier `botw`, et non a plat : c'est ce chemin que le .bat attend.
SOUS_DOSSIER_CLI = "botw"

# Fichiers executes par Windows : ASCII, sans BOM, fins de ligne CRLF.
WINDOWS = (".bat", ".cmd", ".ps1")

# Ce qu'on ne copie jamais depuis les sources, meme s'il traine dedans.
EXCLUS = ("__pycache__", ".pytest_cache", ".git", "*.pyc")


def dire(texte, ok=False, grave=False):
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8",
                                                                 "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    prefixe = "[OK ] " if ok else ("[!! ] " if grave else "     ")
    print(prefixe + texte)


def titre(texte):
    print("")
    print("=" * 70)
    print("  " + texte)
    print("=" * 70)


def md5(path):
    h = hashlib.md5()
    with io.open(path, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def exclus(nom):
    import fnmatch
    if nom.startswith("__") and nom.endswith(".py"):
        return False        # __init__.py fait exister le paquet
    return any(fnmatch.fnmatch(nom, m) for m in EXCLUS)


def verifier_windows(path):
    """(ok, pourquoi) pour un fichier que cmd.exe ou PowerShell execute."""
    with io.open(path, "rb") as f:
        brut = f.read()
    if brut[:3] == b"\xef\xbb\xbf":
        return False, "BOM UTF-8 : cmd.exe le lit comme du texte"
    for octet in brut:
        if octet > 127:
            return (False,
                    "octet non-ASCII (0x%02x) : le fichier doit etre ASCII"
                    % octet)
    if b"\r\n" not in brut:
        return False, "fins de ligne LF : cmd.exe les execute mal"
    if brut.count(b"\n") != brut.count(b"\r\n"):
        return (False, "%d fin(s) de ligne LF isolee(s)"
                % (brut.count(b"\n") - brut.count(b"\r\n")))
    return True, "ASCII, sans BOM, CRLF"


# --- etape 1 : Python --------------------------------------------------------

def verifier_python():
    titre("1. Python")
    v = sys.version_info
    if v < (3, 8):
        dire("Python %d.%d est trop ancien : il faut 3.8 ou plus."
             % (v.major, v.minor), grave=True)
        return False
    dire("Python %d.%d.%d : OK." % (v.major, v.minor, v.micro), ok=True)
    return True


# --- etape 2/3 : copie verifiee ---------------------------------------------

def paires(source, dest_sous):
    """(source, destination) pour tout ce qu'on livre."""
    out = []
    for base, sous, fichiers in os.walk(source):
        sous[:] = [s for s in sous if not exclus(s)]
        rel = os.path.relpath(base, source)
        for f in fichiers:
            if exclus(f):
                continue
            out.append((os.path.join(base, f),
                        os.path.join(dest_sous, rel, f)
                        if rel != "." else os.path.join(dest_sous, f)))
    return out


def copier_verifie(source, dest_sous, seulement_verifier):
    if not os.path.isdir(source):
        dire("dossier absent : %s" % source, grave=True)
        return None
    a_copier = paires(source, dest_sous)
    recopies = 0
    for src, dst in a_copier:
        attendu = md5(src)
        deja = os.path.isfile(dst) and md5(dst) == attendu
        if deja:
            continue
        if seulement_verifier:
            recopies += 1
            continue
        d = os.path.dirname(dst)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        shutil.copy2(src, dst)
        if md5(dst) != attendu:
            dire("copie differente : %s" % dst, grave=True)
            return None
        recopies += 1
    return len(a_copier), recopies


# --- etape 4 : contraintes Windows -------------------------------------------

def controler_windows(racine):
    ko = []
    n = 0
    for base, _s, fichiers in os.walk(racine):
        for f in fichiers:
            if not f.lower().endswith(WINDOWS):
                continue
            n += 1
            ok, pourquoi = verifier_windows(os.path.join(base, f))
            if not ok:
                ko.append("%s : %s" % (f, pourquoi))
    if ko:
        dire("%d fichier(s) que Windows execute ne sont pas conformes :" % len(ko),
             grave=True)
        for k in ko:
            dire("    " + k, grave=True)
    else:
        dire("%d fichier(s) Windows : ASCII, sans BOM, CRLF." % n, ok=True)
    return not ko


# --- etape 5 : UKMM et Cemu --------------------------------------------------

def ou_ukmm():
    for candidat in (os.path.join(os.path.expanduser("~"), "Tools", "UKMM",
                                  "ukmm.exe"),):
        if os.path.isfile(candidat):
            return candidat
    return ""


def ou_cemu():
    racine = os.path.join(os.path.expanduser("~"), "Downloads")
    for base, _s, fichiers in os.walk(racine):
        for f in fichiers:
            if f.lower() == "cemu.exe":
                return os.path.join(base, f)
    return ""


def verifier_outils():
    titre("5. UKMM et Cemu")
    ukmm = ou_ukmm()
    if ukmm:
        dire("UKMM : %s" % ukmm, ok=True)
    else:
        dire("UKMM est introuvable. Telecharge UKMM (UKMM releases) et "
             "depose ukmm.exe dans %s\\Tools\\UKMM\\." %
             os.path.join(os.path.expanduser("~"), "Tools", "UKMM"))
    cemu = ou_cemu()
    if cemu:
        dire("Cemu : %s" % cemu, ok=True)
    else:
        dire("Cemu est introuvable. Telecharge Cemu 2.x et laisse-le dans "
             "ton dossier Downloads.")
    return bool(ukmm and cemu)


# --- etape 6 : raccourci de demarrage ----------------------------------------

def chemin_demarrage():
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup")


def poser_demarrage(dest):
    src = os.path.join(dest, "Cemu-BOTW-au-demarrage.cmd")
    if not os.path.isfile(src):
        dire("le script de demarrage est absent de l'installation", grave=True)
        return False
    d = chemin_demarrage()
    if not os.path.isdir(d):
        dire("dossier de demarrage introuvable : %s" % d, grave=True)
        return False
    dst = os.path.join(d, "Cemu-BOTW-au-demarrage.cmd")
    shutil.copy2(src, dst)
    dire("lanceur de demarrage pose : %s" % dst, ok=True)
    return True


# --- le lanceur est-il complet ? ---------------------------------------------

def fichiers_attendus(dest):
    """Ce dont le .bat a besoin pour fonctionner. Son absence se voit au
    moment de jouer, pas a l'installation : on le verifie maintenant."""
    return ["Lanceur-BOTW.bat", "Set-ProfilUKMM.ps1", "Sauvegardes-BOTW.ps1",
            "LISEZ-MOI.txt", os.path.join(SOUS_DOSSIER_CLI, "botw.py")]


def destination(choix=None):
    r"""Le dossier d'installation, normalise une fois pour toutes.

    Un dossier saisi avec des "/" (D:/BOTW) revient de Windows avec des
    melanges de separateurs ; sans normalisation, l'ecran final affiche
    "D:/BOTW\Lanceur-BOTW.bat". Ca marche quand meme, mais ca a l'air
    d'etre casse - et un installateur qui a l'air casse ne se relit pas.
    """
    if not choix:
        choix = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW")
    return os.path.normpath(choix)


def main(argv):
    p = argparse.ArgumentParser(
        description="Installer le lanceur Zelda BOTW sur cette machine.")
    p.add_argument("--dest", default=None,
                   help="dossier d'installation (defaut : le bureau)")
    p.add_argument("--check", action="store_true",
                   help="verifier sans rien ecrire")
    p.add_argument("--shortcut", action="store_true",
                   help="ajouter le lanceur au demarrage de Windows")
    args = p.parse_args(argv)

    dest = destination(args.dest)

    titre("Installation du lanceur Zelda BOTW")
    dire("source      : %s" % RACINE)
    dire("destination : %s" % dest)
    if args.check:
        dire("mode --check : rien ne sera ecrit")

    if not verifier_python():
        return 1

    # --- la copie d'abord : tout le reste suppose qu'elle est faite ------
    titre("2. Copie du lanceur")
    if not os.path.isdir(dest):
        if args.check:
            dire("dossier de destination absent : rien a verifier.", grave=True)
            return 1
        os.makedirs(dest)
    r = copier_verifie(LANCEUR, dest, args.check)
    if r is None:
        return 1
    dire("%d fichiers du lanceur, %d a %s."
         % (r[0], r[1], "verifier" if args.check else "ecrire"), ok=True)

    titre("3. Copie de l'outil en ligne de commande")
    r2 = copier_verifie(CLI, os.path.join(dest, SOUS_DOSSIER_CLI), args.check)
    if r2 is None:
        return 1
    dire("%d fichiers de code et de tests, %d a %s."
         % (r2[0], r2[1], "verifier" if args.check else "ecrire"), ok=True)

    # --- la copie est faite, on peut donc juger son contenu ---------------
    titre("4. Fichiers que Windows execute")
    if not controler_windows(dest):
        return 1

    complet = verifier_outils()

    if args.check:
        titre("Verification terminee")
        dire("rien n'a ete ecrit.", ok=True)
        return 0

    titre("6. Le lanceur est-il complet ?")
    manquants = [f for f in fichiers_attendus(dest)
                 if not os.path.isfile(os.path.join(dest, f))]
    if manquants:
        dire("fichiers manquants : %s" % ", ".join(manquants), grave=True)
        return 1
    dire("tous les fichiers necessaires sont la.", ok=True)

    if args.shortcut:
        titre("7. Demarrage automatique")
        poser_demarrage(dest)

    titre("C'est pret")
    dire("jouer : %s" % os.path.join(dest, "Lanceur-BOTW.bat"), ok=True)
    dire("outillage : %s"
         % os.path.join(dest, SOUS_DOSSIER_CLI, "botw.bat"), ok=True)
    print("")
    if complet:
        print("  Ouvre le lanceur. Les touches 1 et 2 donnent tes deux parties.")
    else:
        print("  Il manque UKMM ou Cemu : lis les messages ci-dessus d'abord.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
