#!/usr/bin/env python3
"""Verifie qu'un profil UKMM est entierement fusionne ET deploye.

Pour chaque mod du profil, on relit son manifest.yml (la liste des fichiers que
le mod touche) et on verifie que chacun de ces fichiers se retrouve tel quel
dans merged/ puis dans le pack graphique deploye.

Les packs de langue (Pack/Bootup_XXxx.pack) sont traites a part : sur un jeu
francais UKMM les fusionne en un seul fichier Bootup_EUfr.pack.

Usage :  python verifier-profil.py <profil> [profil2 ...]
"""
import io
import os
import re
import sys
import zipfile

APPDATA = os.environ["APPDATA"]
LOCAL = os.environ["LOCALAPPDATA"]
UKMM = os.path.join(LOCAL, "ukmm", "wiiu")
DEPLOY = os.path.join(APPDATA, "Cemu", "graphicPacks", "BreathOfTheWild_UKMM")

LANG_PACK = re.compile(r"^Pack/Bootup_[A-Z]{2}[a-z]{2}\.pack$")


def tree(root):
    out = set()
    if not os.path.isdir(root):
        return out
    for base, _, files in os.walk(root):
        for f in files:
            out.add(os.path.relpath(os.path.join(base, f), root).replace("\\", "/"))
    return out


def manifest_sections(text):
    """Repartit un manifest.yml UKMM en {section: [chemins]}."""
    out, sect = {}, None
    for ln in text.splitlines():
        if re.match(r"^\s*[a-z_]+:\s*$", ln) and not ln.strip().startswith("-"):
            sect = ln.strip().split(":")[0]
            out[sect] = []
            continue
        m = re.match(r"^\s*-\s+(.+?)\s*$", ln)
        if m and sect:
            out[sect].append(m.group(1))
    return out


def wanted_paths(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        d = manifest_sections(zf.read("manifest.yml").decode("utf-8", "replace"))
    lang = [p for p in d.get("content", []) if LANG_PACK.match(p)]
    want = ["content/" + p for p in d.get("content", []) if p not in lang]
    # l'AOC du jeu est deploye sous aoc/0010/
    want += ["aoc/0010/" + p for p in d.get("aoc", [])]
    return want, len(lang)


def check(profile):
    pdir = os.path.join(UKMM, "profiles", profile)
    pfile = os.path.join(pdir, "profile.yml")
    if not os.path.isfile(pfile):
        print("  !! profil introuvable : %s" % profile)
        return False

    merged = tree(os.path.join(pdir, "merged"))
    deployed = tree(DEPLOY)

    prof = io.open(pfile, encoding="utf-8").read()
    names = re.findall(r"^      name: (.+?)\s*$", prof, re.M)
    zips = re.findall(r"^\s+path: .*\\([^\\\r\n]+)\s*$", prof, re.M)
    load_order = re.findall(r"^- (\d+)", prof.split("load_order:")[-1], re.M)

    print("  profil '%s' : %d mods" % (profile, len(names)))
    if len(load_order) != len(names):
        print("     !! INCOHERENT : %d entrees de load_order pour %d mods"
              % (len(load_order), len(names)))
        return False

    ok = True
    for zip_name, name in zip(zips, names):
        want, nlang = wanted_paths(os.path.join(UKMM, "mods", zip_name))
        m_miss = [p for p in want if p not in merged]
        d_miss = [p for p in want if p not in deployed]
        pct = 100.0 * (len(want) - len(m_miss)) / max(1, len(want))
        good = pct >= 99.0 and not d_miss
        ok = ok and good
        print("   %s %-44s %5d/%5d merge (%5.1f%%)  %5d/%5d deploye%s"
              % ("OK " if good else "!! ", name[:44],
                 len(want) - len(m_miss), len(want), pct,
                 len(want) - len(d_miss), len(want),
                 "   [%d pack(s) de langue fusionne(s)]" % nlang if nlang else ""))
        for m in (m_miss[:3] + d_miss[:3]):
            print("        manquant : %s" % m)
    return ok


def main():
    profiles = sys.argv[1:]
    if not profiles:
        profiles = [d for d in os.listdir(os.path.join(UKMM, "profiles"))
                    if os.path.isfile(os.path.join(UKMM, "profiles", d, "profile.yml"))]
    allok = True
    for p in profiles:
        allok = check(p) and allok
        print("")
    print("  RESULTAT :", "OK pour tous les profils verifies" if allok else "INCOMPLET")
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    main()