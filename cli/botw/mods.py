"""Bibliotheque de mods : liste, recherche, telechargement, installation.

Trois sources de mods, dans cet ordre de preference :

1. la bibliotheque locale (dossier Mods\\ du lanceur), ou UKMM lui-meme copie
   chaque mod installe : c'est donc la liste de tous les mods deja vus ;
2. le stockage UKMM (%LOCALAPPDATA%\\ukmm\\wiiu\\mods), source de verite ;
3. GameBanana, via son API publique, pour telecharger un mod qui manque.

Telecharger est separe d'installer, volontairement : on peut vouloir le zip
sous les yeux avant de le donner a UKMM. Chaque telechargement est verifie par
MD5 contre la somme publiee par GameBanana - un fichier corrompu passe
puis fait planter le jeu des heures plus tard.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from . import config, deploy, i18n, profiles

_ = i18n._

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
GB_MOD = "https://gamebanana.com/apiv11/Mod/{}?_csvProperties=_sName,_aFiles"
GB_SEARCH = ("https://gamebanana.com/apiv11/Util/Game/Module/Profile/Page/1"
             "?_csvProperties=_sName,_idCategory,_nFilesize"
             "&_sFilterFields=Name&filter=Search&search={}&rpp=30")


# --- utilitaires -------------------------------------------------------------

def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def _fetch_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# --- bibliotheque locale -----------------------------------------------------

def library(cfg=None):
    return config.library_dir(cfg)


def stock():
    return config.mods_store()


def _readable_name(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if "meta.yml" in zf.namelist():
                text = zf.read("meta.yml").decode("utf-8", "replace")
                m = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
                if m:
                    return m.group(1).strip(" '\"")
    except Exception:                                          # noqa: BLE001
        pass
    return os.path.splitext(os.path.basename(zip_path))[0]


def _zips_in(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if not name.lower().endswith(".zip"):
            continue
        p = os.path.join(root, name)
        try:
            out[name] = (_readable_name(p), os.path.getsize(p))
        except OSError:
            continue
    return out


def available(cfg=None):
    """Tous les mods connus, en privilegiant la bibliotheque locale.

    Retourne {nom de fichier: (nom lisible, taille, present_en_bibliotheque)}.
    """
    lib = _zips_in(library(cfg))
    store = _zips_in(stock())
    out = {}
    for name, (label, size) in store.items():
        out[name] = (label, size, name in lib)
    for name, (label, size) in lib.items():
        if name not in out:
            out[name] = (label, size, True)
        else:
            out[name] = (out[name][0], out[name][1], True)
    return out


def find(query, cfg=None):
    """Resout un nom lisible, un nom de fichier ou une partie en un nom de zip."""
    mods = available(cfg)
    q = (query or "").strip().lower()
    if not q:
        return None
    if q in mods:
        return q
    base = q[:-4] if q.lower().endswith(".zip") else q
    for name, (label, _s, _p) in mods.items():
        stem = os.path.splitext(name)[0]
        if label.lower() == base.lower() or stem.lower() == base.lower():
            return name
    for name, (label, _s, _p) in mods.items():
        if base in label.lower() or base in name.lower():
            return name
    return None


def listing(cfg=None):
    mods = available(cfg)
    if not mods:
        i18n.warn(_("mods.none", path=library(cfg)))
        return mods
    profiles_installed = {}
    for p in profiles.existing():
        prof = profiles.load(p)
        for _label, filename in prof.hashes.values():
            profiles_installed.setdefault(filename, []).append(p)
    act = profiles.active()
    print("  " + i18n.paint("%-46s %10s  %-10s %s"
                            % (_("mods.id"), _("mods.size"), _("mods.status"), ""),
                            "dim"))
    i18n.rule()
    for name in sorted(mods, key=lambda n: mods[n][0].lower()):
        label, size, in_lib = mods[name]
        used = profiles_installed.get(name, [])
        if act in used:
            status = i18n.paint(_("mods.live"), "green")
        elif used:
            status = i18n.paint(",".join(used), "dim")
        else:
            status = i18n.paint(_("mods.no"), "dim")
        if not in_lib:
            label = label + i18n.paint("  " + _("mods.not_in_library"), "yellow")
        print("  %-46s %10s  %-10s" % (label[:46], human(size), status))
        print("      %s" % i18n.paint(name, "dim"))
    i18n.info(_("mods.installed", n=len(mods)))
    return mods


# --- installation dans un profil --------------------------------------------

def _resout_un_zip(chemin):
    """Le dossier racine du zip, celui qui contient meta.yml.

    Un zip de mod commence parfois par un dossier, parfois non : UKMM
    refuse un zip sans meta.yml, et on ne le signalait pas avant de le lui donner.
    On regarde donc d'abord a la racine, puis sur UN niveau de sous-dossier -
    c'est la forme que presque tous les zip de GameBanana ont.
    """
    try:
        with zipfile.ZipFile(chemin) as z:
            noms = z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    if any(n.rstrip("/").split("/")[-1] == "meta.yml" for n in noms):
        return True
    racines = set(n.split("/")[0] for n in noms if "/" in n)
    for r in racines:
        if any(n.startswith(r + "/") and n.split("/")[-1] == "meta.yml"
               for n in noms):
            return True
    return False


def _telecharger(url, cfg=None):
    """Telecharge un zip dans la bibliotheque locale. Retourne son chemin.

    On refuse d'ecrire n'importe quoi dans la bibliotheque : le fichier doit
    finir en .zip et contenir un meta.yml. Un lien vers une page web donne un
    fichier HTML ; le refuser ici evite de le coincer dans la bibliotheque ou
    il rejouerait le meme echec a chaque recherche.
    """
    if not url.lower().startswith(("http://", "https://")):
        return None
    i18n.info(_("mods.fetching", url=url))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    nom = os.path.basename(urllib.parse.urlparse(url).path) or "mod.zip"
    if not nom.lower().endswith(".zip"):
        nom += ".zip"
    # Deux liens peuvent porter le meme nom : on ne doit jamais ecraser un
    # mod deja installe.
    cible = os.path.join(library(cfg), nom)
    i = 2
    while os.path.exists(cible):
        base, ext = os.path.splitext(nom)
        cible = os.path.join(library(cfg), "%s-%d%s" % (base, i, ext))
        i += 1
    os.makedirs(library(cfg), exist_ok=True)
    with open(cible, "wb") as f:
        f.write(data)
    i18n.ok(_("mods.fetched", path=cible, size=human(len(data))))
    if not _resout_un_zip(cible):
        os.remove(cible)
        raise ValueError(_("mods.not_a_mod", path=cible))
    return cible


def installer_fichier(profile, source, cfg=None):
    """Installe un mod depuis un fichier local ou un lien. Chemin complet.

    C'est la porte d'entree de `botw installmods` : elle amene le zip la ou
    UKMM sait le lire (la bibliotheque locale), puis appelle `install`, qui
    ecrit dans profile.yml - donc reversible, et sans toucher au stockage
    d'UKMM comme le fait `ukmm uninstall`.
    """
    zip_path = None
    copie = None          # le fichier que NOUS avons pose dans la bibliotheque
    if os.path.isfile(source):
        zip_path = os.path.abspath(source)
        i18n.info(_("mods.from_file", path=zip_path))
        dest = os.path.join(library(cfg), os.path.basename(zip_path))
        if os.path.abspath(dest) != zip_path:
            os.makedirs(library(cfg), exist_ok=True)
            i = 2
            base, ext = os.path.splitext(os.path.basename(zip_path))
            while os.path.exists(dest):
                dest = os.path.join(library(cfg), "%s-%d%s" % (base, i, ext))
                i += 1
            import shutil
            shutil.copy2(zip_path, dest)
            zip_path = dest
            copie = dest
    elif source.lower().startswith(("http://", "https://")):
        try:
            zip_path = _telecharger(source, cfg)
        except urllib.error.URLError as e:
            raise ValueError(_("mods.download_failed", url=source,
                               why=getattr(e, "reason", str(e))))
    else:
        raise ValueError(_("mods.unknown", n=source))

    if not zip_path or not os.path.isfile(zip_path):
        raise ValueError(_("mods.unknown", n=source))
    if not zip_path.lower().endswith(".zip"):
        if copie:
            os.remove(copie)
        raise ValueError(_("mods.not_a_zip", path=zip_path))
    if not _resout_un_zip(zip_path):
        # On vient de poser ce fichier dans la bibliotheque : on le retire.
        # La bibliotheque est ce que 'botw mods list' propose, et un zip qui
        # n'est pas un mod y reviendrait a chaque proposition.
        if copie:
            os.remove(copie)
        raise ValueError(_("mods.not_a_mod", path=copie or zip_path))
    return install(profile, os.path.basename(zip_path), cfg)


def install(profile, query, cfg=None):
    name = find(query, cfg)
    if not name:
        raise ValueError(_("mods.unknown", n=query))
    prof = profiles.load(profile)
    if any(fn == name for _l, fn in prof.hashes.values()):
        i18n.ok(_("mods.already", name=name, p=profile))
        return False
    src = os.path.join(library(cfg), name)
    if not os.path.isfile(src):
        src = os.path.join(stock(), name)
    if not os.path.isfile(src):
        raise ValueError(_("mods.unknown", n=query))
    avant = profiles.active()
    deploy.write_active_profile(profile)
    try:
        code, _out = deploy.run_ukmm(["install", src, profile], cfg)
    finally:
        if avant:
            deploy.write_active_profile(avant)
    if code != 0:
        i18n.ko(_("mods.refused", name=name, c=code))
        return False
    prof.load()
    prof.rewrite_order()
    i18n.ok(_("mods.added", name=name))
    return True


def uninstall(profile, query, cfg=None):
    """Retire un mod d'un profil.

    On ne se fie jamais a "ukmm uninstall" : cette commande ecrit dans le
    profil ACTIF et supprime le zip du stockage, ce qui est plus agreable que
    de ne rien faire mais casse les autres profils. On edite donc profile.yml,
    ce qui est reversible et local.
    """
    name = find(query, cfg)
    if not name:
        raise ValueError(_("mods.unknown", n=query))
    prof = profiles.load(profile)
    target = {h for h, (_l, fn) in prof.hashes.items() if fn == name}
    if not target:
        i18n.warn(_("mods.already", name=name, p=profile))
        return False
    with open(prof.profile_file, encoding="utf-8") as f:
        lines = f.read().split("\n")
    blocks = _blocks(lines)
    a_enlever = [(d, f) for (_h, d, f) in blocks if _h in target]
    # On parcourt les blocs de la FIN vers le debut : supprimer une plage de
    # lignes deplace tout ce qui suit, et supprimer par indices croissants
    # effacerait les mauvais blocs.
    for debut, fin in sorted(a_enlever, reverse=True):
        del lines[debut:fin]
    text = "\n".join(lines)
    text = re.sub(r"load_order:\n((?:- \d+\n?)+)",
                  lambda m: "load_order:\n" + "".join(
                      "- %s\n" % x for x in re.findall(r"- (\d+)", m.group(1))
                      if x not in target),
                  text)
    with open(prof.profile_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    i18n.ok(_("mods.removed", name=name))
    return True


def _blocks(lines):
    """(hash, ligne_debut, ligne_fin) de chaque mod declare dans profile.yml."""
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^  (\d+):\s*$", lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not re.match(r"^  \d+:\s*$", lines[j]) \
                and not re.match(r"^\S", lines[j]):
            j += 1
        out.append((m.group(1), i, j))
        i = j
    return out


# --- GameBanana --------------------------------------------------------------

def gb_info(mod_id):
    d = _fetch_json(GB_MOD.format(mod_id))
    if "_sErrorCode" in d:
        raise RuntimeError("GameBanana error: %s" % d.get("_sErrorCode"))
    files = [f for f in d.get("_aFiles", []) if not f.get("_bIsArchived")]
    if not files:
        raise RuntimeError("no active file for mod %s" % mod_id)
    files.sort(key=lambda f: f.get("_tsDateAdded", 0))
    return d.get("_sName"), files[-1]


def search(query, limit=30):
    """Recherche GameBanana. Retourne [(id, nom)]."""
    url = GB_SEARCH.format(urllib.parse.quote(query))
    try:
        d = _fetch_json(url)
    except (urllib.error.URLError, ValueError):
        return []
    rows = d if isinstance(d, list) else [d]
    out = []
    for r in rows[:limit]:
        if isinstance(r, dict) and r.get("_idSubmission"):
            out.append((r["_idSubmission"], r.get("_sName", "?")))
    return out


def download(mod_id, outdir=None, cfg=None):
    """Telecharge le dernier fichier d'un mod GameBanana et verifie le MD5."""
    outdir = outdir or library(cfg)
    name, f = gb_info(mod_id)
    url = f.get("_sDownloadUrl") or ""
    fname = f.get("_sFile") or os.path.basename(url) or ("%s.zip" % mod_id)
    os.makedirs(outdir, exist_ok=True)
    dest = os.path.join(outdir, fname)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    md5 = hashlib.md5()
    size = 0
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            md5.update(chunk)
            size += len(chunk)
    i18n.ok(_("mods.download.ok", name=name, size=human(size), path=dest))
    want = (f.get("_sMd5Checksum") or "").lower()
    got = md5.hexdigest().lower()
    if want and want != got:
        i18n.ko(_("mods.download.md5_bad", a=got, b=want))
        return None, False
    i18n.ok(_("mods.download.md5_ok", md5=got))
    return dest, True