#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyse statique de tous les mods UKMM installes : quels mods s'ecrasent.

LA REGLE, lue dans le code source d'UKMM
-----------------------------------------
crates/uk-mod/src/unpack.rs, fonction build_file() :

    ResourceData::Mergeable(..) => versions.fold(base, |res, v| res.merge(v))
    ResourceData::Sarc(..)      => versions.fold(base, |res, v| res.merge(v))
    ResourceData::Binary(..)    => versions.pop_back()      <-- LE DERNIER

Autrement dit :
  - un fichier que UKMM sait DECORTIQUER (un .sbyml, un .sbactorpack, un
    .smubin, un .sbeventpack...) voit les ajouts de tous les mods
    s'additionner : combiner deux mods la-dessus est sans risque.
  - un fichier que UKMM ne sait pas ouvrir est remplace en entier par le
    DERNIER mod de la liste. La-bas, l'ordre decide de tout, et le perdant est
    simplement efface. C'est la, et uniquement la, qu'on peut casser le jeu.

La liste des extensions que UKMM sait fusionner est dans
crates/uk-content/src (chaque struct implemente Mergeable avec un
path_matches) ; le reste retombe sur le test "SARC" a l'octet 0 ou 0x11.

Le fichier qui compte n'est PAS l'ensemble du zip : UKMM ne deploie que les
fichiers declares dans manifest.yml. Un mod peut donc embarquer
GameData/gamedata.sarc sans que personne ne le voie jamais - c'est le cas ici.

Usage :  python conflits.py [-o rapport.txt]
"""
from __future__ import print_function

import io
import json
import os
import re
import sys
import zipfile
from collections import defaultdict

LOCAL = os.environ["LOCALAPPDATA"]
MODS = os.path.join(LOCAL, "ukmm", "wiiu", "mods")
RESERVED = ("manifest.yml", "meta.yml", "options.yml", "manifest.json")

# Extensions que UKMM sait fusionner (extrait des path_matches de uk-content).
# Le nom du fichier se termine par la chaine : ".sbyml" finit par "byml", donc
# un seul suffixe suffit, exactement comme dans le code Rust.
FUSIONNABLE = (
    "baiprog", "baischedule", "baniminfo", "bas", "baslist", "batcl",
    "batcllist", "bawareness", "bbonectrl", "bchemical", "bdemo", "bdmgparam",
    "bdrop", "bfarc", "bgparamlist", "blarc", "blifecondition", "blod",
    "bmodellist", "bphysics", "brecipe", "brgbw", "brgconfig", "brgconfiglist",
    "bshop", "bumii", "bwinfo", "bxml", "byml", "mubin", "bfevfl",
    "gamedata", "savedataformat", "system.bchmres", "residentactors",
)
# Archives SARC du jeu. UKMM sait les fusionner (ResourceData::Sarc).
# On les reconnait a l'extension et non a la signature : tous les fichiers des
# mods sont compresses en Yaz0, et le nom de la SARC n'apparait qu'apres
# decompression. Or la liste des extensions-container du jeu est fixe, donc
# l'extension suffit et evite de decompresser 500 Mo de Second Wind.
SARC_CONTENEURS = ("pack", "sarc", "arc", "bsp", "bactorpack", "beventpack",
                   "barc", "sharc", "ttarc", "farc", "marc", "sarcpack",
                   "bfarc", "blarc", "sysarc", "bspp")
# Extensions explicitement exclues de la fusion SARC par UKMM
# (EXCLUDE_EXTS de uk-content/src/resource.rs).
SARC_EXCLUS = ("genvb", "sarc", "arc")


def manifest_sections(text):
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
    """Yaz0 version UKMM : magic ASCII 'Yaz0'. Retourne None si absent."""
    if len(data) < 0x14 or data[:4] != b"Yaz0":
        return None
    out = bytearray()
    pos, n = 0x10, len(data)
    guard = 0
    while pos + 4 <= n and guard < 4000000:
        guard += 1
        size = struct_u32be(data, pos)
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
        if len(out) > 8 * 1024 * 1024:          # on ne lit que les en-tetes
            break
    return bytes(out)


def struct_u32be(buf, off):
    return (buf[off] << 24) | (buf[off + 1] << 16) | (buf[off + 2] << 8) | buf[off + 3]


def classer(nom_canon, data):
    """Reproduit ResourceData::from_binary d'UKMM.

    -> 'M' fusionnable (additif), 'S' archive fusionnable (additif),
       'B' binaire : le dernier mod de la liste ecrase tous les autres,
       '?' fichier non resolu dans le zip.
    """
    nom = nom_canon.lower()
    base = nom.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    ext = base.rsplit(".", 1)[-1] if "." in base else ""
    if stem == "dummy" or len(data) < 0x10:
        return "B"
    if data[:4] == b"SARC":
        return "S"
    for e in FUSIONNABLE:
        if nom.endswith(e):
            return "M"
    if ext in SARC_CONTENEURS and ext not in SARC_EXCLUS \
            and not stem.startswith("tera_resource"):
        return "S"
    return "B"


def resoudre(zf, chemin, index_base):
    """Retrouve dans le zip l'entree correspondant a un chemin declare.

    UKMM ecrit les noms du jeu (Actor/Pack/X.sbactorpack) alors que le zip
    contient Actor/Pack/X.bactorpack : meme chemin sans extension. Le prefixe
    content/ n'existe que dans le manifeste, et le DLC s'ecrit Aoc/0010/ avec
    une majuscule. Le pack de langue est le cas particulier :
    Pack/Bootup_EUen.pack vaut en vrai Message/Msg_EUen.product.sarc.
    """
    noms = zf.namelist()
    corps = chemin
    for pref in ("content/", "aoc/0010/", "Aoc/0010/"):
        if corps.startswith(pref):
            corps = corps[len(pref):]
            break
    candidats = [chemin, corps, "Aoc/0010/" + corps]
    for c in candidats:
        if c in noms:
            return c
    base = corps.rsplit(".", 1)[0]
    if base in index_base:
        return index_base[base]
    m = re.match(r"^Pack/Bootup_([A-Za-z]{2}[a-z]{2})\.pack$", corps)
    if m:
        cible = "Message/Msg_%s.product.sarc" % m.group(1)
        if cible in noms:
            return cible
    return None


def lire_mod(chemin_zip):
    res = {"zip": os.path.basename(chemin_zip),
           "nom": os.path.basename(chemin_zip),
           "fichiers": {}, "erreurs": []}
    try:
        with zipfile.ZipFile(chemin_zip) as zf:
            noms = [n for n in zf.namelist() if n not in RESERVED]
            index_base = {}
            for n in noms:
                index_base.setdefault(n.rsplit(".", 1)[0], n)
            if "meta.yml" in noms + ["meta.yml"]:
                res["nom"] = meta_name(zf.read("meta.yml").decode("utf-8", "replace"))
            if "manifest.yml" not in zf.namelist():
                res["erreurs"].append("pas de manifest.yml")
                return res
            sect = manifest_sections(zf.read("manifest.yml").decode("utf-8", "replace"))
            declares = ["content/" + p for p in sect.get("content", [])]
            declares += ["aoc/0010/" + p for p in sect.get("aoc", [])]
            for p in declares:
                entree = resoudre(zf, p, index_base)
                if entree is None:
                    res["fichiers"][p] = ("?", 0)
                    continue
                data = zf.read(entree)
                res["fichiers"][p] = (classer(p, data), len(data))
    except Exception as exc:                                     # noqa: BLE001
        res["erreurs"].append(repr(exc))
    return res


def norm(p):
    return p[len("content/"):] if p.startswith("content/") else p


def main():
    out_txt = None
    if "-o" in sys.argv:
        out_txt = sys.argv[sys.argv.index("-o") + 1]

    zips = sorted(f for f in os.listdir(MODS) if f.lower().endswith(".zip"))
    mods = [lire_mod(os.path.join(MODS, z)) for z in zips]
    mods.sort(key=lambda m: m["nom"].lower())

    L = []
    L.append("=" * 78)
    L.append("  CONFLITS REELS ENTRE MODS   (%d mods)" % len(mods))
    L.append("  M = fusionne par UKMM (sans risque)   S = archive fusionnable")
    L.append("  B = NON fusionnable : le dernier mod de la liste gagne")
    L.append("=" * 78)
    L.append("")
    L.append("%-46s %6s %6s %6s %6s" % ("MOD", "declar", "M", "S", "B"))
    L.append("-" * 78)
    for m in mods:
        c = defaultdict(int)
        for k, _v in m["fichiers"].values():
            c[k] += 1
        L.append("%-46s %6d %6d %6d %6d" % (m["nom"][:46], len(m["fichiers"]),
                                            c["M"], c["S"], c["B"]))
        for e in m["erreurs"]:
            L.append("      !! %s" % e)
    L.append("")

    # Fichiers partages : on ne garde que les B, les seuls destructeurs.
    par = defaultdict(list)
    for m in mods:
        for p, (k, taille) in m["fichiers"].items():
            par[p].append((m["nom"], k, taille))

    destructeurs = []
    additifs = []
    for p, qui in par.items():
        if len(qui) < 2:
            continue
        (destructeurs if any(k == "B" for _n, k, _t in qui) else additifs).append((p, qui))

    L.append("-" * 78)
    L.append("  ETAPE 1 - fichiers partages que UKMM SAIT fusionner")
    L.append("  (les ajouts des mods s'additionnent : ordre sans importance)")
    L.append("-" * 78)
    L.append("")
    if not additifs:
        L.append("  Aucun.")
    for p, qui in sorted(additifs, key=lambda t: -len(t[1]))[:40]:
        L.append("  %-58s %d mod(s)" % (norm(p), len(qui)))
        for n, _k, _t in qui:
            L.append("      - %s" % n)
    L.append("")
    if len(additifs) > 40:
        L.append("  ... et %d autres fichiers fusionnables partages." % (len(additifs) - 40))
        L.append("")

    L.append("-" * 78)
    L.append("  ETAPE 2 - DANGER : fichiers partages que UKMM NE SAIT PAS")
    L.append("  fusionner. Ici l'ordre decide : le dernier mod ecrase les autres.")
    L.append("-" * 78)
    L.append("")
    if not destructeurs:
        L.append("  Aucun. Aucun couple de mods ne s'ecrase.")
    for p, qui in sorted(destructeurs, key=lambda t: -len(t[1])):
        tailles = set(t for _n, _k, t in qui if t)
        ecart = (max(tailles) - min(tailles)) if len(tailles) > 1 else 0
        L.append("")
        L.append("  !! %-58s  %d mod(s)" % (norm(p), len(qui)))
        for n, k, t in qui:
            L.append("      %-46s %s %9d o" % (n[:46], k, t))
        if ecart:
            L.append("      -> ecart %d octets : le plus petit est efface." % ecart)
    L.append("")

    # Resume par couple de mods, pour savoir qui mettre en dernier.
    par_mod = defaultdict(set)
    for p, qui in destructeurs:
        for n, _k, _t in qui:
            par_mod[n].add(p)
    L.append("-" * 78)
    L.append("  COUPES DANGEREUSES (fichiers non fusionnables en commun)")
    L.append("-" * 78)
    L.append("")
    paires = set()
    noms = [m["nom"] for m in mods]
    for i in range(len(noms)):
        for j in range(i + 1, len(noms)):
            commun = par_mod[noms[i]] & par_mod[noms[j]]
            if commun:
                paires.add((noms[i], noms[j], len(commun)))
    if not paires:
        L.append("  Aucune.")
    for a, b, n in sorted(paires, key=lambda t: -t[2]):
        L.append("  %-44s %s %-44s : %d" % (a[:44], "VS", b[:44], n))
    L.append("")

    js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conflits.json")
    with io.open(js, "w", encoding="utf-8") as f:
        json.dump({"mods": [{"zip": m["zip"], "nom": m["nom"],
                             "fichiers": dict((k, list(v))
                                             for k, v in m["fichiers"].items())}
                            for m in mods],
                   "destructeurs": [[p, [(n, k, t) for n, k, t in qui]]
                                    for p, qui in destructeurs],
                   "additifs": [[p, [n for n, _k, _t in qui]] for p, qui in additifs]},
                  f, indent=1)

    text = "\n".join(L) + "\n"
    if out_txt:
        with io.open(out_txt, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("rapport ecrit : %s" % out_txt)
    print(text)
    print("JSON ecrit : %s" % js)
    print()
    print("BILAN : %d fichiers fusionnables partages, %d DANGEREUX, "
          "%d couples de mods en conflit."
          % (len(additifs), len(destructeurs), len(paires)))


if __name__ == "__main__":
    main()