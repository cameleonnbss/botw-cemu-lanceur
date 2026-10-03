#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cree un profil UKMM a partir d'une liste de mods, dans le bon ordre.

Usage :
    python creer-profil.py <profil> <mod1> [mod2 ...]

Les noms de mods sont ceux lus dans meta.yml ("Second Wind (core)"), ou le nom
du fichier zip. L'ordre de fusion n'est pas celui de la ligne de commande :
chaque mod est place selon PRIORITE, du plus faible au plus fort.

Pourquoi l'ordre compte
-----------------------
UKMM empile les mods dans l'ordre du load_order et le DERNIER l'emporte
(crates/uk-mod/src/unpack.rs, build_file). Pour les fichiers qu'il sait
fusionner, peu importe. Pour les autres, le dernier ecrase tout : c'est la
que se decide si un mod marche ou casse le jeu.

Regles appliquees ici :
  - Second Wind en priorite la plus basse : c'est une extension du jeu, les
    autres mods doivent pouvoir corriger ce qu'il ajoute.
  - ses modules optionnels juste au-dessus.
  - Relics of the Past (Relics of the Past) Avant Ancient Weaponry : les deux
    remplacent les memes emplacements d'arme. Ordon avant Relics pour rester
    coherent avec ce que le lanceur propose.
  - Linkle toujours en dernier : c'est une peau, elle doit passer au-dessus
    des mods qui changent les armures, sinon les textures se melangent.
  - 10x Paraglider juste sous Linkle : il touche Player_Link.baiprog, un
    fichier que Relics touche aussi.
"""
from __future__ import print_function

import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

LOCAL = os.environ["LOCALAPPDATA"]
STOCK = os.path.join(LOCAL, "ukmm", "wiiu", "mods")
PROFILES = os.path.join(LOCAL, "ukmm", "wiiu", "profiles")
SETTINGS = os.path.join(os.environ["APPDATA"], "ukmm", "settings.yml")
UKMM = os.path.join(os.path.expanduser("~"), "Tools", "UKMM", "ukmm.exe")

# Priorite, du PLUS FAIBLE au PLUS FORT. Les cles sont les noms de fichiers.
PRIORITE = [
    "Second_Wind_(core).zip",
    "Second_Wind_-_Shrine_Overhaul.zip",
    "Second_Wind_-_Eventide_Fix.zip",
    "Ancient_Weaponry_Mark_II.zip",
    "Relics_of_the_Past.zip",
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


def lister():
    """-> {nom lisible ou nom de zip: fichier zip}"""
    out = {}
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
        out[nom] = z
        out[z] = z
        out[z[:-4]] = z
    return out


def set_actif(nom):
    with io.open(SETTINGS, encoding="utf-8") as f:
        raw = f.read()
    new = re.sub(r"(?m)^(\s*profile:\s*).*$", lambda m: m.group(1) + nom, raw)
    if new != raw:
        with io.open(SETTINGS, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        t = f.read()
    mods, lignes, i = {}, t.split("\n"), 0
    while i < len(lignes):
        m = re.match(r"^  (\d+):\s*$", lignes[i])
        if not m:
            i += 1
            continue
        h, nom, zp, j = m.group(1), "", "", i + 1
        while j < len(lignes) and not re.match(r"^  \d+:\s*$", lignes[j]) \
                and not re.match(r"^\S", lignes[j]):
            nm = re.match(r"^\s+name: (.+?)\s*$", lignes[j])
            pp = re.match(r"^\s+path: .*\\([^\\\r\n]+)\s*$", lignes[j])
            if nm:
                nom = nm.group(1)
            if pp:
                zp = pp.group(1)
            j += 1
        mods[h] = (nom, zp)
        i = j
    return mods


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    profil = sys.argv[1]
    demandes = sys.argv[2:]
    connus = lister()

    zips, inconnus = [], []
    for d in demandes:
        z = connus.get(d) or connus.get(d.lower())
        (zips if z else inconnus).append(z or d)
    if inconnus:
        print("Mod inconnu : %s" % ", ".join(inconnus))
        print("Disponibles : %s" % ", ".join(sorted(set(connu for connu, z
                                                          in lister().items()
                                                          if z == connu))))
        return 2

    d = os.path.join(PROFILES, profil)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(os.path.join(d, "merged"))
    with io.open(os.path.join(d, "profile.yml"), "w",
                 encoding="utf-8", newline="\n") as f:
        f.write("mods: {}\nload_order: []\n")

    avant = None
    with io.open(SETTINGS, encoding="utf-8") as f:
        m = re.search(r"(?m)^\s*profile:\s*(\S+)\s*$", f.read())
        avant = m.group(1) if m else None
    set_actif(profil)
    try:
        echecs = []
        for z in zips:
            r = subprocess.run([UKMM, "install", os.path.join(STOCK, z), profil],
                               capture_output=True, text=True, errors="replace")
            if r.returncode != 0:
                echecs.append(z)
            else:
                print("  + %s" % z)
        if echecs:
            print("  !! refuses : %s" % ", ".join(echecs))
    finally:
        if avant:
            set_actif(avant)

    p = os.path.join(d, "profile.yml")
    mods = lire(p)
    rang, ordre = {}, []
    for z in PRIORITE:
        for h, (_n, zp) in mods.items():
            if zp == z and h not in ordre:
                rang[h] = len(rang)
                ordre.append(h)
    for h in mods:
        if h not in ordre:
            print("  (mod hors priorite connue : %s)" % mods[h][0])
            ordre.append(h)
    with io.open(p, encoding="utf-8") as f:
        t = f.read()
    corps = "load_order:\n" + "".join("- %s\n" % h for h in ordre)
    t = re.sub(r"load_order:\n(?:- \d+\n?)+", corps, t)
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)

    print("")
    print("Profil '%s' cree : %d mods" % (profil, len(mods)))
    print("Ordre de fusion, du PLUS FAIBLE au PLUS FORT :")
    for i, h in enumerate(ordre):
        print("  %2d. %s" % (i + 1, mods[h][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())