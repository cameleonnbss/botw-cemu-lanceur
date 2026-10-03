"""Recopie le programme botw vers le bureau, et prouve que la copie est exacte.

On developpe dans ~/botw-bcml-work/botw-tools, mais ce qui est livre au joueur
vit dans ~/Desktop/BOTW/botw. Ce sont deux dossiers, donc deux versions, donc
un moment ou l'on oublie de recopier et ou le lanceur execute du code vieux de
trois semaines. La faute est invisible : les tests passent, le lanceur marche,
c'est juste l'ancien texte qui s'affiche.

Ce script supprime le risque :

  * il recopie la liste complete, sans jamais se fier a ce qu'il trouve deja
    sur le bureau (les fichiers supprimes ici partent aussi) ;
  * il compare le MD5 de chaque fichier apres copie - la copie doit etre
    identique, octet pour octet ;
  * il revérifie les contraintes Windows : un .bat ou un .ps1 doit etre en
    ASCII, sans BOM, avec des fins de ligne CRLF, sinon cmd.exe et
    PowerShell 5.1 le refusent ou plantent sur un accent du nom d'utilisateur ;
  * il n'écrit rien d'autre : ni Sauvegardes, ni Mods, ni config.

Usage :
    python Outils/maj-bureau.py            recopie et verifie
    python Outils/maj-bureau.py --check    verifie sans rien ecrire
"""
from __future__ import print_function

import fnmatch
import hashlib
import io
import os
import shutil
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.dirname(ICI)
DEST = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW", "botw")

# Ce qu'on livre. Tout le reste (caches, brouillons) reste cote source.
LIVRABLES = ["botw.py", "botw.bat", "README.md", "README.fr.md"]
DOSSIERS = ["botw", "locales", "tests", "Outils"]
EXCLUS = ("__pycache__", "*.pyc", ".pytest_cache", "_*.py", "*.bak")

# Dossiers qu'on ne veut ni copier, ni laisser trainer cote bureau. Ils
# reapparaisent des qu'on lance pytest depuis la copie livree.
CACHES = ("__pycache__", ".pytest_cache")

# Fichiers que Windows execute : ASCII, sans BOM, fins de ligne CRLF.
WINDOWS = (".bat", ".cmd", ".ps1")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def exclus(nom):
    # Les fichiers en __ sont la structure du paquet (__init__.py,
    # __main__.py), pas des brouillons. "_*.py" les attrapait, et la copie
    # livree se retrouvait sans eux.
    if nom.startswith("__") and nom.endswith(".py"):
        return False
    return any(fnmatch.fnmatch(nom, motif) for motif in EXCLUS)


def a_livrer(src, dst):
    """Les fichiers a copier, en paires (source, destination)."""
    paires = []
    for nom in LIVRABLES:
        paires.append((os.path.join(src, nom), os.path.join(dst, nom)))
    for d in DOSSIERS:
        base = os.path.join(src, d)
        if not os.path.isdir(base):
            continue
        for rep, sous, fichiers in os.walk(base):
            sous[:] = [s for s in sous
                       if s not in CACHES and not exclus(s)]
            rel = os.path.relpath(rep, src)
            for f in fichiers:
                if exclus(f):
                    continue
                paires.append((os.path.join(rep, f),
                               os.path.join(dst, rel, f)))
    return paires


def nettoyer_les_obsoletes(dst, src):
    """Supprime sur le bureau ce qui n'existe plus cote source.

    Les caches (__pycache__, .pytest_cache) sont supprimes entiers. Les
    ignorer au parcours ne suffirait pas : on ne les visiterait pas, donc on
    ne verrait pas leurs fichiers, donc ils resteraient sur le bureau.
    """
    orphelins = []
    caches = []
    for rep, sous, fichiers in os.walk(dst):
        for s in list(sous):
            if s in CACHES:
                caches.append(os.path.join(rep, s))
                sous.remove(s)
    for rep, sous, fichiers in os.walk(dst):
        for f in fichiers:
            if exclus(f):
                continue
            cible = os.path.join(rep, f)
            origine = os.path.join(src, os.path.relpath(cible, dst))
            if not os.path.isfile(origine):
                orphelins.append(cible)
    for o in orphelins:
        os.remove(o)
    for c in caches:
        shutil.rmtree(c, ignore_errors=True)
    # Les dossiers devenus vides, du plus profond au plus haut.
    for rep, _s, _f in sorted(os.walk(dst), key=lambda x: -len(x[0])):
        if rep == dst:
            continue
        try:
            if not os.listdir(rep):
                os.rmdir(rep)
        except OSError:
            pass
    return orphelins, caches


def verifier_windows(path):
    """(ok, pourquoi) pour un fichier execute par cmd.exe ou powershell."""
    with io.open(path, "rb") as f:
        brut = f.read()
    if brut[:3] == b"\xef\xbb\xbf":
        return False, "BOM UTF-8 : cmd.exe lit le BOM comme du texte"
    for octet in brut:
        if octet > 127:
            return False, "octet non-ASCII (0x%02x) : le fichier doit etre ASCII" % octet
    if b"\r\n" not in brut:
        return False, "fins de ligne LF : cmd.exe les execute mal"
    lone = brut.count(b"\n") - brut.count(b"\r\n")
    if lone:
        return False, "%d fin(s) de ligne LF isolee(s)" % lone
    return True, "ASCII, sans BOM, CRLF"


def main(argv):
    verifier_seulement = "--check" in argv
    if os.path.normcase(SOURCE) == os.path.normcase(DEST):
        print("Le programme est deja a sa place (%s) : rien a recopier." % DEST)
        return 0
    if not os.path.isdir(os.path.dirname(DEST)):
        print("Dossier parent absent : %s" % os.path.dirname(DEST))
        return 1

    paires = a_livrer(SOURCE, DEST)
    if not paires:
        print("Aucun fichier a livrer depuis %s" % SOURCE)
        return 1

    copies = 0
    for src, dst in paires:
        attendu = md5(src)
        deja = os.path.isfile(dst) and md5(dst) == attendu
        if deja:
            continue
        if verifier_seulement:
            print("  [manquant] %s" % os.path.relpath(dst, DEST))
            copies += 1
            continue
        d = os.path.dirname(dst)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        shutil.copy2(src, dst)
        if md5(dst) != attendu:
            print("  [KO] copie differente : %s" % dst)
            return 1
        copies += 1

    orphelins, caches = (nettoyer_les_obsoletes(DEST, SOURCE)
                         if not verifier_seulement else ([], []))

    # --- controle final ----------------------------------------------------
    divergences = [os.path.relpath(d, DEST) for s, d in paires
                   if not os.path.isfile(d) or md5(s) != md5(d)]
    problemes = []
    for src, dst in paires:
        if dst.lower().endswith(WINDOWS) and os.path.isfile(dst):
            ok, pourquoi = verifier_windows(dst)
            if not ok:
                problemes.append("%s : %s" % (os.path.relpath(dst, DEST), pourquoi))

    print("source : %s" % SOURCE)
    print("bureau : %s" % DEST)
    print("fichiers livres : %d" % len(paires))
    if verifier_seulement:
        print("a recopier : %d" % copies)
    else:
        print("recopies : %d" % copies)
        print("obsoletes supprimes : %d" % len(orphelins))
        for o in orphelins:
            print("  - %s" % os.path.relpath(o, DEST))
        print("caches supprimes : %d" % len(caches))
        for c in caches:
            print("  - %s" % os.path.relpath(c, DEST))
    # Auto-controle : la copie livree doit contenir les fichiers qui font
    # exister le paquet. Leur absence ne se voyait pas.
    attendus = ["botw/__init__.py", "botw/__main__.py"]
    manquants = [a for a in attendus
                 if not os.path.isfile(os.path.join(DEST, *a.split("/")))]
    if manquants:
        print("\nPROBLEMES : fichiers du paquet absents de la copie :")
        for a in manquants:
            print("  ! %s" % a)
        return 1

    print("divergences MD5 : %d" % len(divergences))
    for d in divergences:
        print("  ! %s" % d)
    if problemes:
        print("\nPROBLEMES (%d) :" % len(problemes))
        for p in problemes:
            print("  ! %s" % p)
        return 1
    if verifier_seulement and copies:
        return 1
    print("\nOK : la copie du bureau est identique a la source.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))