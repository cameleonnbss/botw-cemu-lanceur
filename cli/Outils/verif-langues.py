"""Verifie que toute cle utilisee dans le code existe dans les deux langues.

C'est le genre d'erreur qu'on ne voit pas au test : la commande marche, mais
elle affiche le nom de la cle au lieu du texte, ou pire, elle plante sur un
.KeyError. On relit donc le code avec une expression reguliere.
"""
import io
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
CODE = os.path.join(RACINE, "botw")
APPEL = re.compile(r'(?<![\w.])_\(\s*"([^"]+)"')

langs = {}
for code in ("en", "fr"):
    with io.open(os.path.join(RACINE, "locales", code + ".json"),
                 encoding="utf-8") as f:
        langs[code] = json.load(f)

trouve = {}
for nom in sorted(os.listdir(CODE)):
    if not nom.endswith(".py"):
        continue
    texte = io.open(os.path.join(CODE, nom), encoding="utf-8").read()
    for cle in APPEL.findall(texte):
        trouve.setdefault(cle, set()).add(nom)

manquantes = []
for cle in sorted(trouve):
    for code in ("en", "fr"):
        if cle not in langs[code]:
            manquantes.append("%s manquante en %s (utilisee dans %s)"
                              % (cle, code, ",".join(sorted(trouve[cle]))))

inutilisees = []
for cle in sorted(langs["en"]):
    if cle not in trouve:
        inutilisees.append(cle)

print("cles utilisees : %d" % len(trouve))
print("cles definies dans en.json : %d" % len(langs["en"]))
if manquantes:
    print("\nMANQUANTES (%d) :" % len(manquantes))
    for m in manquantes:
        print("  " + m)
else:
    print("\nAucune cle manquante.")
if inutilisees:
    print("\ndefinies mais jamais utilisees (%d) :" % len(inutilisees))
    for u in inutilisees:
        print("  " + u)
sys.exit(1 if manquantes else 0)
