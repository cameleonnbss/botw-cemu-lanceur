#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyse statique de tous les mods UKMM installes : quels fichiers chacun
touche, et donc quels mods se marchent dessus.

Pourquoi c'est important
------------------------
UKMM empile les mods dans l'ordre du load_order et le DERNIER l'emporte
(crates/uk-mod/src/unpack.rs : versions.pop_back()). Quand deux mods
modifient le meme fichier, l'ordre decide qui gagne - et c'est exactement le
genre de detail qui fait planter le jeu au chargement. En regardant SEULEMENT
les fichiers que chaque mod embarque, on peut dire quels couples sont
dangereux sans merger quoi que ce soit : quelques secondes au lieu de
plusieurs minutes par essai.

On compare deux jeux de chemins :
  - "declarés"  : les chemins du manifest.yml, tels qu'ils s'appellent DANS le
                  jeu (Actor/Pack/Weapon_Bow_024.sbactorpack). C'est ce que
                  UKMM utilise pour savoir quoi remplacer.
  - "embarques" : les noms d'entrees du zip. Le 's' de tete d'extension
                  (sbactorpack) n'existe pas sur le disque : UKMM le retire.

Usage :  python analyse-mods.py [-o rapport.txt]
"""
from __future__ import print_function

import io
import json
import os
import re
import struct
import sys
import zipfile
from collections import defaultdict

LOCAL = os.environ["LOCALAPPDATA"]
MODS = os.path.join(LOCAL, "ukmm", "wiiu", "mods")

RESERVED = ("manifest.yml", "meta.yml", "options.yml", "manifest.json")


def manifest_sections(text):
    """Repartit un manifest.yml UKMM en {section: [chemins]}."""
    out, sect = {}, None
    for ln in text.splitlines():
        if re.match(r"^\s*[a-z_0-9]+:\s*$", ln) and not ln.strip().startswith("-"):
            sect = ln.strip().split(":")[0]
            out.setdefault(sect, [])
            continue
        m = re.match(r"^\s*-\s+(.+?)\s*$", ln)
        if m and sect:
            out[sect].append(m.group(1))
    return out


def meta_name(text):
    m = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
    return m.group(1).strip(" '\"") if m else "?"


def yaz0_decompress(data):
    """Decompresse une archive Yaz0, ou renvoie None si le format est autre.

    On verifie le champ 'header size' : sans ce controle, n'importe quels
    4 premiers octets passant pour une signature seraient lus comme une
    archive, et le resultat serait du bruit.
    """
    if len(data) < 0x14 or data[:4] != b"\x28\xb5\x2f\xfd":
        return None
    if struct.unpack(">I", data[8:12])[0] != 0x10:
        return None
    out = bytearray()
    pos, n = 0x10, len(data)
    while pos + 4 <= n:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        pos += 4
        if size == 0:
            break
        end = min(pos + size, n)
        while pos < end:
            b = data[pos]
            pos += 1
            if b == 0:
                if pos >= end:
                    break
                out += b"\x00" * data[pos]
                pos += 1
            else:
                out.append(b)
    return bytes(out)


def sarc_names(data):
    """Noms de fichiers d'une SARC, ou None si ce n'en est pas une."""
    if data[:4] != b"SARC":
        return None
    count = struct.unpack(">H", data[10:12])[0]
    if count > 4096:
        return None
    out = []
    for i in range(count):
        o = 0x10 + i * 0x50
        if o + 0x50 > len(data):
            break
        nm = data[o:o + 0x40].split(b"\x00", 1)[0].decode("ascii", "replace").strip()
        if nm:
            out.append(nm)
    return out


def read_mod(zip_path):
    """Lit un mod UKMM et retourne ce qu'il touche, sous tous les angles."""
    res = {"zip": os.path.basename(zip_path), "nom": os.path.basename(zip_path),
           "declares": set(), "embarques": set(), "conteneurs": set(),
           "tailles": {}, "erreurs": []}
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = [n for n in zf.namelist() if n not in RESERVED]
            res["embarques"] = set(names)
            res["tailles"] = dict((n, zf.getinfo(n).file_size) for n in names)
            if "meta.yml" in zf.namelist():
                res["nom"] = meta_name(zf.read("meta.yml").decode("utf-8", "replace"))
            if "manifest.yml" not in zf.namelist():
                res["erreurs"].append("pas de manifest.yml")
                return res
            sect = manifest_sections(zf.read("manifest.yml").decode("utf-8", "replace"))
            res["declares"] = set(["content/" + p for p in sect.get("content", [])])
            res["declares"] |= set(["aoc/0010/" + p for p in sect.get("aoc", [])])
            # On ouvre les archives pour voir les fichiers qu'elles cachent :
            # une mod qui remplace un .bsp embarque des dizaines de fichiers
            # a l'interieur, et c'est precisement la que se cachent les
            # conflits qu'on ne devinerait pas.
            for n in names:
                try:
                    data = zf.read(n)
                except KeyError:
                    continue
                if len(data) < 0x14:
                    continue
                plain = data if data[:4] == b"SARC" else yaz0_decompress(data)
                if plain is None:
                    continue
                inner = sarc_names(plain)
                if inner:
                    res["conteneurs"].add(n)
                    for nm in inner:
                        res["declares"].add("content/" + n + "!" + nm)
    except Exception as exc:                                     # noqa: BLE001
        res["erreurs"].append(repr(exc))
    return res


def norm(p):
    """Chemin lisible : on retire le prefixe content/ et le '!' des archives."""
    p = p[len("content/"):] if p.startswith("content/") else p
    return p


def table(mods, key, titre, L):
    L.append("-" * 78)
    L.append("  " + titre)
    L.append("-" * 78)
    paires = []
    for i in range(len(mods)):
        for j in range(i + 1, len(mods)):
            a, b = mods[i], mods[j]
            both = a[key] & b[key]
            if both:
                paires.append((a, b, both))
    if not paires:
        L.append("  Aucun chevauchement.")
        L.append("")
    for a, b, both in sorted(paires, key=lambda t: -len(t[2])):
        L.append("")
        L.append("  !! %s" % a["nom"])
        L.append("     VS %s        -> %d fichier(s) en commun" % (b["nom"], len(both)))
        for p in sorted(both)[:20]:
            L.append("        - %s" % norm(p))
        if len(both) > 20:
            L.append("        ... et %d autres" % (len(both) - 20))
    L.append("")
    return paires


def gravite(mods, L):
    """Pour chaque fichier partage, la taille que chaque mod en fournit.

    C'est LA table la plus utile du rapport. UKMM sait fusionner deux fichiers
    SARC (un .pack, un .sarc) : les ajouts des deux mods coexistent. Mais pour
    tout le reste (un .byml, un .bfres, un .bfevfl), le dernier mod de la liste
    remplace purement et simplement le fichier. La ou les tailles s'ecartent
    fortement, on sait que quelqu'un va perdre son travail - et c'est
    precisement ce qui provoque les plantages.
    """
    par = defaultdict(list)
    for m in mods:
        for p in m["embarques"]:
            par[p].append(m["nom"])
    L.append("-" * 78)
    L.append("  CONFLITS REELS : fichiers partages qui NE se fusionnent pas")
    L.append("  (le dernier mod de la liste ecrase les autres)")
    L.append("-" * 78)
    L.append("")
    tailles_par_fichier = {}
    for m in mods:
        for p, s in m["tailles"].items():
            tailles_par_fichier.setdefault(p, {})[m["nom"]] = s
    liste = []
    for p, qui in par.items():
        if len(qui) < 2:
            continue
        if p.lower().endswith((".sarc", ".pack", ".bsp", ".arc")):
            continue                      # fusionnable : pas un conflit
        tailles = set(tailles_par_fichier.get(p, {}).values())
        liste.append((max(tailles) - min(tailles) if len(tailles) > 1 else 0, p, qui))
    if not liste:
        L.append("  Aucun : tous les fichiers partages sont des SARC, UKMM les fusionne.")
    for ecart, p, qui in sorted(liste, reverse=True):
        L.append("")
        L.append("  %-56s  %d mod(s)" % (norm(p), len(qui)))
        for n in qui:
            s = tailles_par_fichier.get(p, {}).get(n, 0)
            L.append("      %-46s %9d o" % (n[:46], s))
        if ecart:
            L.append("      -> ecart max %d octets : le plus petit est purement et"
                     % ecart)
            L.append("         simplement remplace par le plus gros.")
    L.append("")
    return len(liste)


def main():
    out_txt = None
    if "-o" in sys.argv:
        out_txt = sys.argv[sys.argv.index("-o") + 1]

    zips = sorted(f for f in os.listdir(MODS) if f.lower().endswith(".zip"))
    mods = [read_mod(os.path.join(MODS, z)) for z in zips]
    mods.sort(key=lambda m: m["nom"].lower())

    L = []
    L.append("=" * 78)
    L.append("  ANALYSE DES MODS UKMM  -  %d mods" % len(mods))
    L.append("=" * 78)
    L.append("")
    L.append("%-44s %8s %8s %8s %6s" % ("MOD", "declarés", "zip", "SARC", "erreurs"))
    L.append("-" * 78)
    for m in mods:
        L.append("%-44s %8d %8d %8d %6d" % (m["nom"][:44], len(m["declares"]),
                                            len(m["embarques"]), len(m["conteneurs"]),
                                            len(m["erreurs"])))
        for e in m["erreurs"]:
            L.append("      !! %s" % e)
    L.append("")

    p_declare = table(mods, "declares", "FICHIERS DECLARES EN COMMUN", L)
    p_zip = table(mods, "embarques", "MEMES NOMS D'ENTREE DANS LES ZIPS", L)

    # Fichiers partages par 3 mods ou plus.
    L.append("-" * 78)
    L.append("  FICHIERS MODIFIES PAR 3 MODS OU PLUS")
    L.append("-" * 78)
    L.append("")
    par = defaultdict(list)
    for m in mods:
        for p in m["declares"]:
            par[p].append(m["nom"])
    triples = {p: v for p, v in par.items() if len(v) >= 3}
    if not triples:
        L.append("  Aucun.")
    for p, v in sorted(triples.items(), key=lambda t: -len(t[1])):
        L.append("  %s" % norm(p))
        for n in v:
            L.append("      - %s" % n)
    L.append("")
    n_grav = gravite(mods, L)

    js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyse-mods.json")
    with io.open(js, "w", encoding="utf-8") as f:
        json.dump([{"zip": m["zip"], "nom": m["nom"],
                    "declares": sorted(m["declares"]),
                    "embarques": sorted(m["embarques"])} for m in mods],
                  f, indent=1)

    text = "\n".join(L) + "\n"
    if out_txt:
        with io.open(out_txt, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("rapport ecrit : %s" % out_txt)
    print(text)
    print("JSON ecrit : %s" % js)
    print()
    print("Resume : %d paire(s) se chevauchant sur les fichiers declares, "
          "%d sur les noms de zip, %d conflit(s) non fusionnables."
          % (len(p_declare), len(p_zip), n_grav))


if __name__ == "__main__":
    main()