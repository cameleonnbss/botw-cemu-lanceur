#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repare les manifest.yml des mods UKMM qui n'appliquent rien du tout.

LE PROBLEME
-----------
Le manifest.yml d'un mod UKMM dit a UKMM QUELS fichiers reconstruire.
UKMM n'applique QUE les fichiers listes dans le manifeste : les autres
entrees du zip sont ignorees (verifie dans crates/uk-mod/src/unpack.rs,
build_file, qui n'itere que sur les fichiers declares).

Deux de nos mods ont un manifeste qui ne correspond pas a leur contenu :

  10x_Speed_Paraglider_v2.zip     declare "Pack/TitleBG.pack"
                                  et ne contient que Actor/AIProgram/Player_Link.baiprog
  Second_Wind_-_Eventide_Fix.zip declare "Pack/TitleBG.pack"
                                  et contient 21 fichiers (Model/, Actor/, EventFlow/)

Aucun des deux ne contient de fichier rangé sous Pack/TitleBG/, donc la
declaration ne sert a rien et, surtout, AUCUN de leurs fichiers reels n'est
declare : le mod ne fait strictement rien en jeu. C'est exactement le genre
de mod qui donne l'impression que le lanceur ment.

Declaration d'un pack parent
----------------------------
Declarer "Pack/Dungeon004.pack" alors que le zip ne le contient pas est
NORMAL et correct : ca veut dire "reconstruis ce pack pour y integrer les
fichiers enfants que j'ai modifies". Il faut donc distinguer :
  - un fichier embarque qui n'est couvert par aucune declaration  -> a ajouter
  - un pack parent declare, dont les enfants sont bien dans le zip -> normal

Noms de fichiers
----------------
UKMM applique canonicalize() a tous les chemins, qui fait
replace(".s", "."). Le nom du disque (Actor/AIProgram/Player_Link.baiprog)
donne donc exactement le meme chemin canonique que le nom du jeu
(Actor/AIProgram/Player_Link.sbaiprog). On ecrit le nom du disque : c'est
ce qui est reellement dans le zip, donc sans ambiguite.

Usage :  python reparer-manifests.py [--seul <nom.zip>] [--simuler]
"""
from __future__ import print_function

import io
import os
import re
import shutil
import sys
import time
import zipfile

LOCAL = os.environ["LOCALAPPDATA"]
MODS = os.path.join(LOCAL, "ukmm", "wiiu", "mods")
DESKTOP_MODS = os.path.join(os.path.expanduser("~"), "Desktop", "BOTW", "Mods")
SAUVEGARDE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "manifests-avant-reparation")
RESERVED = ("manifest.yml", "meta.yml", "options.yml")


def canon(p):
    """Meme transformation que uk_content::canonicalize."""
    return p.replace("\\", "/").replace(".s", ".")


def lire_manifest(texte):
    """-> (liste content, liste aoc) telles qu'ecrites dans le fichier."""
    out = {"content": [], "aoc": []}
    sect = None
    for ln in texte.splitlines():
        if re.match(r"^\s*[a-z_0-9]+:\s*$", ln) and not ln.strip().startswith("-"):
            sect = ln.strip().split(":")[0]
            continue
        m = re.match(r"^\s*-\s+(.+?)\s*$", ln)
        if m and sect in out:
            out[sect].append(m.group(1))
    return out


def couvert(entree, declares):
    """L'entree du zip est-elle deja couverte par une declaration ?

    Deux cas :
      - la declaration est le fichier lui-meme ;
      - la declaration est un PACK PARENT : "Pack/TitleBG.pack" couvre tout
        ce qui se trouve sous "Pack/TitleBG/".
    """
    ce = canon(entree)
    for d in declares:
        cd = canon(d)
        if cd == ce:
            return True
        if "/" not in d or "." not in d.rsplit("/", 1)[-1]:
            continue
        # "Pack/TitleBG.pack" couvre tout ce qui est sous "Pack/TitleBG/"
        prefixe = cd.rsplit(".", 1)[0] + "/"
        if ce.startswith(prefixe):
            return True
    return False


def section_de(entree):
    return "aoc" if entree.replace("\\", "/").lower().startswith("aoc/0010/") else "content"


def reparer(chemin_zip, simuler=False):
    nom = os.path.basename(chemin_zip)
    with zipfile.ZipFile(chemin_zip) as zf:
        entrees = [i for i in zf.infolist() if i.filename not in RESERVED]
        texte = zf.read("manifest.yml").decode("utf-8")
        section = lire_manifest(texte)
        declares = section["content"] + section["aoc"]
        couverts = [i for i in entrees if couvert(i.filename, declares)]
        manque = [i.filename for i in entrees if not couvert(i.filename, declares)]

    if not manque:
        return nom, [], "complet"
    if couverts:
        # Le manifeste ne couvre qu'une partie du zip. C'est le cas de la
        # plupart des mods officials : ils declarent parfois un pack parent
        # plutot que chaque enfant, et leur liste a ete verifiee par leur
        # auteur. Y toucher serait prendre le risque de casser un mod qui
        # marche. On se contente de le signaler.
        return nom, manque, "partiel (%d/%d couverts, on n'y touche pas)" % (
            len(couverts), len(entrees))

    if not os.path.isdir(SAUVEGARDE):
        os.makedirs(SAUVEGARDE)
    shutil.copy2(chemin_zip, os.path.join(SAUVEGARDE, nom))

    # On repart du manifeste existant et on ajoute seulement ce qui manque,
    # en conservant l'ordre : les packs parents d'abord, les enfants ensuite.
    for e in sorted(manque):
        declares.append(e)

    tmp = chemin_zip + ".repar"
    src = zipfile.ZipFile(chemin_zip)
    out = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
    for item in src.infolist():
        data = src.read(item.filename)
        if item.filename == "manifest.yml":
            corps = []
            for sect in ("content", "aoc"):
                lst = [d for d in declares if section_de(d) == sect]
                corps.append(sect + ":")
                corps += ["- " + d for d in lst]
            data = ("\n".join(corps) + "\n").encode("utf-8")
        if item.compress_type == zipfile.ZIP_STORED:
            out.writestr(item, data, zipfile.ZIP_STORED)
        else:
            out.writestr(item.filename, data, zipfile.ZIP_DEFLATED)
    out.close()
    src.close()

    if not simuler:
        # Remplacement atomique, puis on rafraichit le lien dur du dossier
        # Mods\ du bureau pour qu'il pointe sur le nouveau fichier.
        os.replace(tmp, chemin_zip)
        lien = os.path.join(DESKTOP_MODS, nom)
        if os.path.isfile(lien):
            os.remove(lien)
            try:
                os.link(chemin_zip, lien)
            except OSError:
                shutil.copy2(chemin_zip, lien)
    else:
        os.remove(tmp)
    return nom, manque, "corrige"


def main():
    simuler = "--simuler" in sys.argv
    seul = None
    if "--seul" in sys.argv:
        seul = sys.argv[sys.argv.index("--seul") + 1]

    zips = sorted(f for f in os.listdir(MODS) if f.lower().endswith(".zip"))
    if seul:
        zips = [z for z in zips if seul.lower() in z.lower()]

    total = 0
    inertes = []
    partiels = []
    for z in zips:
        nom, manque, etat = reparer(os.path.join(MODS, z), simuler)
        if etat == "complet":
            print("%-48s complet" % nom[:48])
            continue
        if manque and etat.startswith("partiel"):
            partiels.append((nom, manque, etat))
            print("%-48s %s" % (nom[:48], etat))
            continue
        total += len(manque)
        inertes.append((nom, manque))
        print("%-48s INERTE -> corrige (%d fichiers declares)" % (nom[:48], len(manque)))
        for m in manque:
            print("      + %s" % m)

    print("")
    if partiels:
        print("Mods au manifeste partiel (on n'y touche pas, liste d'origine) :")
        for nom, manque, etat in partiels:
            print("  %-46s %s" % (nom[:46], etat))
        print("")
    print("Sauvegardes des zip originaux : %s" % SAUVEGARDE)
    print("Total : %d declaration(s) ajoutee(s) dans %d mod(s)%s"
          % (total, len(inertes),
             "  (simulation, rien n'a ete ecrit)" if simuler else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())