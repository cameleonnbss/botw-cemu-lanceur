# -*- coding: utf-8 -*-
"""Verifie que chaque commande `botw` des README existe vraiment.

Une documentation qui cite une commande inexistante est pire qu'aucune
documentation : l'utilisateur la tape, elle echoue, et il conclut que
l'outil est casse. Ce script extrait les commandes citees des deux README et
les fait passer par le vrai analyseur d'arguments.
"""
from __future__ import print_function

import argparse
import io
import os
import re
import sys

# Le script vit dans outils/ : la racine du depot est au-dessus.
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ICI, "cli")
sys.path.insert(0, CLI)

for var in ("APPDATA", "LOCALAPPDATA", "USERPROFILE"):
    os.environ.setdefault(var, os.path.join(os.path.expanduser("~"), "botw-doc"))

from botw import cli                                              # noqa: E402


def commandes_citees(texte):
    """Les lignes de commande des README, commentaires retires.

    On ignore ce qui suit un « # » : dans un bloc bash c'est un commentaire,
    et le caractere se retrouve aussi dans une URL ou un nom de mod.
    """
    trouvees = set()
    for ligne in texte.replace("\r\n", "\n").split("\n"):
        ligne = ligne.split("#")[0]
        for m in re.finditer(r"`botw\s+([^`]+)`", ligne):
            trouvees.add(m.group(1).strip())
    return trouvees


def rendre_executable(commande):
    """`botw profile verify <nom>` doit devenir testable.

    `<nom>` et `[option]` sont des notations de documentation, pas des
    arguments : on les remplace par une valeur plausible pour que
    l'analyseur ait quelque chose a analysing.
    """
    commande = re.sub(r"<[^>]+>", "exemple", commande)
    commande = re.sub(r"\[[^\]]+\]", "", commande)      # options facultatives
    commande = commande.replace("\\|", "exemple")
    return commande.strip()


def main():
    parser = cli.build_parser()
    echecs = []
    total = 0
    for nom in ("README.md", "README.fr.md"):
        chemin = os.path.join(ICI, nom)
        if not os.path.isfile(chemin):
            echecs.append("%s : fichier absent" % nom)
            continue
        with io.open(chemin, encoding="utf-8") as f:
            citees = commandes_citees(f.read())
        for commande in sorted(citees):
            total += 1
            testee = rendre_executable(commande)
            sortie = sys.stdout
            try:
                parser.parse_args(testee.split())
            except SystemExit:
                sys.stdout = sortie
                echecs.append("%s : `botw %s` ne demarre pas" % (nom, commande))
            finally:
                sys.stdout = sortie
    print("%d commandes documentees, %d invalide(s)" % (total, len(echecs)))
    for e in echecs:
        print("  ! %s" % e)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
