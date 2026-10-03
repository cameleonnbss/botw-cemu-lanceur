#!/usr/bin/env python3
"""Supprime un mod d'un profil UKMM (edition textuelle deterministe).

L'edition se fait au niveau du texte, pas avec PyYAML : le fichier contient des
tags YAML UKMM (`!Specific "Wii U"`) qu'un parseur standard refuse, et on veut
garantir que tout le reste du fichier reste identique au bit pres.

Usage :  python editer-profil.py <profil> --remove "<nom exact du mod>"
"""
import io
import os
import re
import sys

PROFILES = os.path.join(
    os.environ["LOCALAPPDATA"], "ukmm", "wiiu", "profiles")


def remove_mod(path, name):
    with io.open(path, encoding="utf-8") as f:
        lines = f.readlines()

    # 1. localiser la cle du mod dans le map "mods:" (indentation de 2 espaces)
    key = None
    in_mods = False
    for i, ln in enumerate(lines):
        if re.match(r"^mods:\s*$", ln):
            in_mods = True
            continue
        if in_mods and re.match(r"^\S", ln):          # fin du map (load_order:, ...)
            break
        m = re.match(r"^  (\d+):\s*$", ln)
        if not m:
            continue
        # le bloc d'un mod commence par "meta:" puis "name:"
        for j in range(i + 1, min(i + 5, len(lines))):
            nm = re.match(r"^      name: (.+?)\s*$", lines[j])
            if nm:
                if nm.group(1) == name:
                    key = m.group(1)
                    start = i
                break
        if key:
            break

    if not key:
        raise SystemExit("!! mod introuvable dans {} : {}".format(path, name))

    # 2. trouver la fin du bloc : prochaine cle de 2 espaces ou ligne de col 0
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^  \d+:\s*$", lines[j]) or re.match(r"^\S", lines[j]):
            end = j
            break
    removed = end - start

    # 3. retirer l'entree de load_order
    lo = [i for i, ln in enumerate(lines) if re.match(r"^- \d+\s*$", ln)]
    order_start = None
    for i, ln in enumerate(lines):
        if re.match(r"^load_order:\s*$", ln):
            order_start = i
            break
    order_hit = 0
    if order_start is not None:
        j = order_start + 1
        while j < len(lines) and re.match(r"^-\s*\d+\s*$", lines[j]):
            if lines[j].strip() == "- " + key:
                del lines[j]
                order_hit = 1
                break
            j += 1

    del lines[start:end]

    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)

    print("   '{}' retire : {} lignes de bloc, {} entree de load_order"
          .format(name, removed, order_hit))
    return True


def main():
    if len(sys.argv) < 4 or sys.argv[2] != "--remove":
        raise SystemExit(__doc__)
    profile, name = sys.argv[1], sys.argv[3]
    path = os.path.join(PROFILES, profile, "profile.yml")
    if not os.path.isfile(path):
        raise SystemExit("!! profil introuvable : {}".format(path))
    # sauvegarde
    bak = path + ".bak"
    with io.open(path, encoding="utf-8") as f:
        io.open(bak, "w", encoding="utf-8", newline="").write(f.read())
    print("   sauvegarde : {}".format(bak))
    remove_mod(path, name)


if __name__ == "__main__":
    main()